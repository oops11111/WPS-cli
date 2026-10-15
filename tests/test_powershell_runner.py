import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from wps_ai_agent_cli.powershell_runner import UTF8_OUTPUT_PREAMBLE, run_powershell_command, run_powershell_script


class Completed:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


class RunnerTests(unittest.TestCase):
    def run_with(self, result=None, error=None, **kwargs):
        seen = {}

        def fake(command, **options):
            seen["script"] = Path(command[-1]).read_text(encoding="utf-8-sig")
            seen["path"] = Path(command[-1])
            if error:
                raise error
            return result

        with patch("wps_ai_agent_cli.powershell_runner.subprocess.run", side_effect=fake):
            outcome = run_powershell_script("Write-Output 1", **kwargs)
        self.assertEqual(seen["script"], UTF8_OUTPUT_PREAMBLE + "Write-Output 1")
        self.assertFalse(seen["path"].exists(), "temporary script must be removed")
        return outcome

    def test_every_script_and_command_writes_utf8(self):
        # P7-007: Windows PowerShell wrote stdout in the console code page and the untitled document's name
        # 文字文稿1 came back garbled. The preamble switches the output to UTF-8, which every caller decodes.
        self.assertIn("[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false", UTF8_OUTPUT_PREAMBLE)
        with patch("wps_ai_agent_cli.powershell_runner.subprocess.run") as run:
            run_powershell_command("Get-Process")
        self.assertEqual(run.call_args.args[0][-1], UTF8_OUTPUT_PREAMBLE + "Get-Process")
        self.assertEqual(run.call_args.kwargs["encoding"], "utf-8")

    def test_success_returns_payload(self):
        payload, failure = self.run_with(Completed(0, json.dumps({"ok": True, "x": 1})))
        self.assertIsNone(failure)
        self.assertEqual(payload["x"], 1)

    def test_timeout_is_structured_and_merges_data(self):
        payload, failure = self.run_with(
            error=subprocess.TimeoutExpired("ps", 5), timeout_seconds=5, timeout_data={"k": "v"}
        )
        self.assertIsNone(payload)
        self.assertEqual(failure["errors"][0]["code"], "COM_OPERATION_TIMEOUT")
        self.assertTrue(failure["data"]["timed_out"])
        self.assertEqual(failure["data"]["k"], "v")

    def test_missing_powershell_is_structured(self):
        _, failure = self.run_with(error=FileNotFoundError("powershell"))
        self.assertEqual(failure["errors"][0]["code"], "COM_OPERATION_FAILED")

    def test_nonzero_exit_uses_error_message_from_json(self):
        _, failure = self.run_with(
            Completed(2, json.dumps({"ok": False, "error_message": "boom"})), failure_data={"component": "writer"}
        )
        self.assertEqual(failure["errors"][0]["message"], "boom")
        self.assertEqual(failure["data"]["component"], "writer")
        self.assertEqual(failure["data"]["diagnostic"]["error_message"], "boom")

    def test_held_open_refusal_from_the_script_maps_to_document_held_open(self):
        from wps_ai_agent_cli.errors import HELD_OPEN_MARKER
        from wps_ai_agent_cli.wps_script_snippets import PRE_OPEN_GUARD

        # The marker must stay in Assert-WpsFileNotHeld's throw text, or the mapping below never fires on WPS.
        self.assertIn(HELD_OPEN_MARKER, PRE_OPEN_GUARD)
        message = f"The document {HELD_OPEN_MARKER} (sharing violation), most likely because it is open in WPS."
        _, failure = self.run_with(Completed(2, json.dumps({"ok": False, "error_message": message})))
        self.assertEqual(failure["errors"][0]["code"], "DOCUMENT_HELD_OPEN")
        self.assertEqual(failure["errors"][0]["message"], message)

    def test_non_json_output_is_failure(self):
        _, failure = self.run_with(Completed(0, "warning text", ""))
        self.assertEqual(failure["errors"][0]["code"], "COM_OPERATION_FAILED")
        self.assertIn("warning text", failure["errors"][0]["message"])

    def test_raise_process_errors_reraises_timeout_and_start_failure(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            self.run_with(error=subprocess.TimeoutExpired("ps", 5), raise_process_errors=True)
        with self.assertRaises(FileNotFoundError):
            self.run_with(error=FileNotFoundError("powershell"), raise_process_errors=True)

    def test_converted_com_helpers_keep_their_timeout_contracts(self):
        from wps_ai_agent_cli import spreadsheet_ops, writer_ops

        caps = {
            "components": {
                "spreadsheets": {"selected_prog_id": "ket.Application"},
                "writer": {"selected_prog_id": "kwps.Application"},
            }
        }
        timeout = subprocess.TimeoutExpired("ps", 120)
        with (
            patch.object(spreadsheet_ops, "probe_wps_capabilities", return_value=caps),
            patch.object(writer_ops, "probe_wps_capabilities", return_value=caps),
            patch("wps_ai_agent_cli.powershell_runner.subprocess.run", side_effect=timeout),
        ):
            result = spreadsheet_ops._run_spreadsheet_rename_sheet_com("book.xlsx", "a", "b")
            self.assertEqual(result["errors"][0]["code"], "COM_OPERATION_TIMEOUT")
            self.assertTrue(result["data"]["timed_out"])
            with self.assertRaises(subprocess.TimeoutExpired):
                writer_ops._run_writer_replace_com("doc.docx", "a", "b")


PWSH = os.environ.get("WPS_TEST_PWSH") or shutil.which("pwsh")


@unittest.skipUnless(PWSH, "PowerShell (pwsh) is required to run a script")
class Utf8OutputTests(unittest.TestCase):
    def test_a_chinese_document_name_comes_back_intact(self):
        with patch("wps_ai_agent_cli.powershell_runner.powershell_executable", return_value=PWSH):
            payload, failure = run_powershell_script("[pscustomobject]@{ name = '文字文稿1' } | ConvertTo-Json")
        self.assertIsNone(failure, failure)
        self.assertEqual(payload["name"], "文字文稿1")


if __name__ == "__main__":
    unittest.main()
