from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from openpyxl import Workbook

from wps_ai_agent_cli.atomic_mutation import atomic_mutation
from wps_ai_agent_cli.backups import create_backup
from wps_ai_agent_cli.errors import ROLLBACK_FAILED, ROLLED_BACK
from wps_ai_agent_cli.sessions import register_document


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AtomicMutationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.workspace = root / "workspace"
        self.workspace.mkdir()
        self.document = root / "book.xlsx"
        Workbook().save(self.document)
        ok, record, _ = register_document("spreadsheets", str(self.document), self.workspace)
        self.assertTrue(ok)
        self.document_id = record["document_id"]
        ok, backup, _, _ = create_backup(self.document_id, "req-atomic-write:backup", workspace=self.workspace)
        self.assertTrue(ok)
        self.backup_path = backup["backup_path"]
        self.original_bytes = self.document.read_bytes()

    def tearDown(self):
        self._tmp.cleanup()

    def _mutation(self, change_file: bool, ok: bool = False, raise_after_change: bool = False):
        document, backup_path, workspace = self.document, self.backup_path, self.workspace

        @atomic_mutation
        def write(document_id, request_id, workspace=".", **_):
            if change_file:
                document.write_bytes(b"WPS saved this")
            if raise_after_change:
                raise RuntimeError("COM dropped after save")
            return ok, {"document_id": document_id, "backup": {"backup_path": backup_path}}, [
                {"code": "VALIDATION_FAILED", "message": "read-back mismatch"}
            ] if not ok else [], False

        return write(self.document_id, "req-atomic-write", workspace=workspace)

    def test_failed_write_that_changed_the_file_is_restored_byte_for_byte(self):
        ok, result, errors, replayed = self._mutation(change_file=True)

        self.assertFalse(ok)
        self.assertEqual(self.document.read_bytes(), self.original_bytes)
        self.assertEqual(result["rollback"]["performed"], True)
        self.assertEqual([error["code"] for error in errors], ["VALIDATION_FAILED", ROLLED_BACK])
        self.assertIn("close it without saving", errors[-1]["message"])

    def test_failed_write_that_left_the_file_alone_is_not_rolled_back(self):
        ok, result, errors, _ = self._mutation(change_file=False)

        self.assertFalse(ok)
        self.assertEqual(result["rollback"], {"performed": False, "reason": "the file already matches the pre-write backup"})
        self.assertEqual([error["code"] for error in errors], ["VALIDATION_FAILED"])

    def test_successful_write_is_left_as_written(self):
        document, backup_path = self.document, self.backup_path

        @atomic_mutation
        def write(document_id, request_id, workspace=".", **_):
            document.write_bytes(b"kept")
            return True, {"document_id": document_id, "backup": {"backup_path": backup_path}}, [], False

        ok, result, errors, _ = write(self.document_id, "req-atomic-ok", workspace=self.workspace)

        self.assertTrue(ok)
        self.assertEqual(self.document.read_bytes(), b"kept")
        self.assertNotIn("rollback", result)
        self.assertEqual(errors, [])

    def test_exception_after_the_save_is_reported_as_rolled_back(self):
        ok, result, errors, _ = self._mutation(change_file=True, raise_after_change=True)

        self.assertFalse(ok)
        self.assertEqual(self.document.read_bytes(), self.original_bytes)
        self.assertEqual(result["rollback"]["performed"], True)

    def test_exception_before_any_backup_is_still_raised(self):
        @atomic_mutation
        def write(document_id, request_id, workspace=".", **_):
            raise RuntimeError("failed before the backup")

        with self.assertRaises(RuntimeError):
            write(self.document_id, "req-never-backed-up", workspace=self.workspace)

    def test_restore_failure_is_reported_with_the_backup_to_use(self):
        failed_restore = {"code": "COM_OPERATION_FAILED", "message": "disk full"}
        with patch("wps_ai_agent_cli.atomic_mutation._restore_file_atomically", return_value=failed_restore):
            ok, result, errors, _ = self._mutation(change_file=True)

        self.assertFalse(ok)
        self.assertEqual(errors[-1]["code"], ROLLBACK_FAILED)
        self.assertIn(self.backup_path, errors[-1]["message"])
        self.assertIn("disk full", errors[-1]["message"])
        self.assertNotEqual(_sha(self.document), _sha(Path(self.backup_path)))


if __name__ == "__main__":
    unittest.main()
