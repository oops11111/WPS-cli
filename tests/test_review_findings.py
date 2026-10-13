import ast
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wps_ai_agent_cli import com_backend
from wps_ai_agent_cli.backups import create_backup, guarded_com_mutation, restore_backup
from wps_ai_agent_cli.cli import (
    _with_optional_task_status,
    convert_smoke_response,
    html_render_response,
    spreadsheet_read_response,
)
from wps_ai_agent_cli.models import CommandResponse
from wps_ai_agent_cli.sessions import register_document
from wps_ai_agent_cli.task_status import get_task_status


class RestoreHardeningTests(unittest.TestCase):
    def _backed_up_document(self, tmp):
        workspace = Path(tmp) / "workspace"
        workspace.mkdir()
        document = Path(tmp) / "sample.docx"
        document.write_bytes(b"original")
        _, record, _ = register_document("writer", str(document), workspace)
        ok, backup, errors, _ = create_backup(record["document_id"], "b1", workspace=workspace)
        self.assertTrue(ok, errors)
        document.write_bytes(b"modified-later")
        return workspace, document, record["document_id"], Path(backup["backup_path"])

    def test_restore_rejects_tampered_backup_without_touching_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, document, document_id, backup = self._backed_up_document(tmp)
            backup.write_bytes(b"GARBAGE")
            ok, _, errors, _ = restore_backup(document_id, "r1", backup_name=backup.name, workspace=workspace)
            self.assertFalse(ok)
            self.assertEqual(errors[0]["code"], "BACKUP_CHANGED_AFTER_CREATION")
            self.assertEqual(document.read_bytes(), b"modified-later")

    def test_restore_dry_run_also_rejects_tampered_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, _, document_id, backup = self._backed_up_document(tmp)
            backup.write_bytes(b"GARBAGE")
            ok, _, errors, _ = restore_backup(document_id, "r1d", backup_name=backup.name, dry_run=True, workspace=workspace)
            self.assertFalse(ok)
            self.assertEqual(errors[0]["code"], "BACKUP_CHANGED_AFTER_CREATION")

    def test_restore_reports_locked_target_as_structured_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, document, document_id, backup = self._backed_up_document(tmp)
            real_replace = os.replace

            def locked_replace(source, destination):
                if Path(destination) == document:
                    raise PermissionError("locked by WPS")
                return real_replace(source, destination)

            with patch("wps_ai_agent_cli.backups.os.replace", side_effect=locked_replace):
                ok, _, errors, _ = restore_backup(document_id, "r2", backup_name=backup.name, workspace=workspace)
            self.assertFalse(ok)
            self.assertEqual(errors[0]["code"], "RESTORE_TARGET_WRITE_FAILED")
            self.assertEqual(document.read_bytes(), b"modified-later")
            leftovers = [item for item in document.parent.iterdir() if item.name.endswith(".restore")]
            self.assertEqual(leftovers, [])

    def test_restore_success_replaces_target_with_backup_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, document, document_id, backup = self._backed_up_document(tmp)
            ok, result, errors, _ = restore_backup(document_id, "r3", backup_name=backup.name, workspace=workspace)
            self.assertTrue(ok, errors)
            self.assertTrue(result["backup_integrity_verified"])
            self.assertEqual(document.read_bytes(), b"original")


class GuardedMutationTimeoutTests(unittest.TestCase):
    def _backup(self, tmp):
        workspace = Path(tmp)
        document = workspace / "d.docx"
        document.write_bytes(b"data")
        _, record, _ = register_document("writer", str(document), workspace)
        ok, backup, errors, _ = create_backup(record["document_id"], "gb", workspace=workspace)
        self.assertTrue(ok, errors)
        return document, backup

    def test_timeout_becomes_structured_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            document, backup = self._backup(tmp)

            def operation():
                raise subprocess.TimeoutExpired("powershell", 120)

            result = guarded_com_mutation(document, backup, operation)
            self.assertFalse(result["ok"])
            self.assertEqual(result["errors"][0]["code"], "COM_OPERATION_TIMEOUT")
            self.assertTrue(result["data"]["timed_out"])

    def test_missing_powershell_becomes_structured_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            document, backup = self._backup(tmp)

            def operation():
                raise FileNotFoundError("powershell")

            result = guarded_com_mutation(document, backup, operation)
            self.assertFalse(result["ok"])
            self.assertEqual(result["errors"][0]["code"], "COM_OPERATION_FAILED")


class TaskStatusExceptionTests(unittest.TestCase):
    def test_unexpected_exception_marks_task_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous = os.getcwd()
            os.chdir(tmp)
            try:
                def boom():
                    raise RuntimeError("kaboom")

                with self.assertRaises(RuntimeError):
                    _with_optional_task_status(boom, "t-exc", "writer-replace", "req-exc", "doc_x")
                status = get_task_status("t-exc")
                self.assertEqual(status["state"], "failed")
                self.assertTrue(status["terminal"])
            finally:
                os.chdir(previous)


class SmokeOutputGuardTests(unittest.TestCase):
    def test_conversion_smoke_rejects_output_equal_to_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "doc.docx"
            source.write_bytes(b"x")
            with patch.object(com_backend.subprocess, "run") as run:
                result = com_backend.run_conversion_smoke("writer", str(source), str(source), "pdf")
            self.assertFalse(result["ok"])
            self.assertIn("must differ", result["errors"][0]["message"])
            run.assert_not_called()

    def test_com_smoke_rejects_output_equal_to_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "doc.docx"
            source.write_bytes(b"x")
            with patch.object(com_backend.subprocess, "run") as run:
                result = com_backend.run_com_smoke("writer", str(source), str(source))
            self.assertFalse(result["ok"])
            run.assert_not_called()

    def test_conversion_smoke_timeout_is_structured(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "doc.docx"
            source.write_bytes(b"x")
            target = Path(tmp) / "doc.pdf"
            caps = {"components": {"writer": {"selected_prog_id": "kwps.Application"}}}
            with patch.object(com_backend, "probe_wps_capabilities", return_value=caps), \
                    patch.object(com_backend.subprocess, "run", side_effect=subprocess.TimeoutExpired("powershell", 120)):
                result = com_backend.run_conversion_smoke("writer", str(source), str(target), "pdf")
            self.assertFalse(result["ok"])
            self.assertEqual(result["errors"][0]["code"], "COM_OPERATION_TIMEOUT")


class ResponseReturnTests(unittest.TestCase):
    def test_command_response_functions_contain_a_return(self):
        source = Path("src/wps_ai_agent_cli/cli.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        missing = []
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef) or node.returns is None:
                continue
            annotation = ast.unparse(node.returns)
            if "CommandResponse" not in annotation:
                continue
            if not any(isinstance(child, ast.Return) and child.value is not None for child in ast.walk(node)):
                missing.append(node.name)
        self.assertEqual(missing, [])

    def test_convert_smoke_and_html_render_return_command_responses(self):
        with patch("wps_ai_agent_cli.cli.run_conversion_smoke", return_value={
            "ok": True, "data": {"output_path": "out.pdf", "output_bytes": 12}, "errors": [],
        }):
            converted = convert_smoke_response("req", "writer", "in.docx", "out.pdf", "pdf")
        self.assertIsInstance(converted, CommandResponse)
        self.assertTrue(converted.ok)
        self.assertEqual(converted.command, "convert-smoke")
        self.assertEqual(converted.validation.status, "passed")

        with patch("wps_ai_agent_cli.cli.render_html", return_value=(True, {"output_path": "page.pdf"}, [])):
            rendered = html_render_response("req", "in.html", "page.pdf", "pdf", "A4", 800, 600, 30, False)
        self.assertIsInstance(rendered, CommandResponse)
        self.assertTrue(rendered.ok)
        self.assertEqual(rendered.command, "html-render")

        with patch("wps_ai_agent_cli.cli.read_spreadsheet_range", return_value=(
            True, {"range": "A1:B1", "values": [[1, 2]]}, [],
        )):
            read = spreadsheet_read_response("req", "doc_1", "A1:B1", None)
        self.assertIsInstance(read, CommandResponse)
        self.assertTrue(read.ok)
        self.assertEqual(read.command, "spreadsheet-read")
        self.assertEqual(read.data["values"], [[1, 2]])


if __name__ == "__main__":
    unittest.main()
