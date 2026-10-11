import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from wps_ai_agent_cli.powershell_runner import run_powershell_script


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
        self.assertEqual(seen["script"], "Write-Output 1")
        self.assertFalse(seen["path"].exists(), "temporary script must be removed")
        return outcome

    def test_success_returns_payload(self):
        payload, failure = self.run_with(Completed(0, json.dumps({"ok": True, "x": 1})))
        self.assertIsNone(failure)
        self.assertEqual(payload["x"], 1)

    def test_timeout_is_structured_and_merges_data(self):
        payload, failure = self.run_with(error=subprocess.TimeoutExpired("ps", 5), timeout_seconds=5, timeout_data={"k": "v"})
        self.assertIsNone(payload)
        self.assertEqual(failure["errors"][0]["code"], "COM_OPERATION_TIMEOUT")
        self.assertTrue(failure["data"]["timed_out"])
        self.assertEqual(failure["data"]["k"], "v")

    def test_missing_powershell_is_structured(self):
        _, failure = self.run_with(error=FileNotFoundError("powershell"))
        self.assertEqual(failure["errors"][0]["code"], "COM_OPERATION_FAILED")

    def test_nonzero_exit_uses_error_message_from_json(self):
        _, failure = self.run_with(Completed(2, json.dumps({"ok": False, "error_message": "boom"})), failure_data={"component": "writer"})
        self.assertEqual(failure["errors"][0]["message"], "boom")
        self.assertEqual(failure["data"]["component"], "writer")
        self.assertEqual(failure["data"]["diagnostic"]["error_message"], "boom")

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

        caps = {"components": {"spreadsheets": {"selected_prog_id": "ket.Application"}, "writer": {"selected_prog_id": "kwps.Application"}}}
        timeout = subprocess.TimeoutExpired("ps", 120)
        with patch.object(spreadsheet_ops, "probe_wps_capabilities", return_value=caps), \
                patch.object(writer_ops, "probe_wps_capabilities", return_value=caps), \
                patch("wps_ai_agent_cli.powershell_runner.subprocess.run", side_effect=timeout):
            result = spreadsheet_ops._run_spreadsheet_rename_sheet_com("book.xlsx", "a", "b")
            self.assertEqual(result["errors"][0]["code"], "COM_OPERATION_TIMEOUT")
            self.assertTrue(result["data"]["timed_out"])
            with self.assertRaises(subprocess.TimeoutExpired):
                writer_ops._run_writer_replace_com("doc.docx", "a", "b")


if __name__ == "__main__":
    unittest.main()
