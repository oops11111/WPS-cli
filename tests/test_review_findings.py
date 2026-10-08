import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wps_ai_agent_cli import com_backend
from wps_ai_agent_cli.backups import create_backup, guarded_com_mutation, restore_backup
from wps_ai_agent_cli.cli import _with_optional_task_status
from wps_ai_agent_cli.models import CommandResponse, ValidationResult
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


if __name__ == "__main__":
    unittest.main()
