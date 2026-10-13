from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from openpyxl import Workbook

from wps_ai_agent_cli.backups import create_backup
from wps_ai_agent_cli.sessions import file_identity, register_document


def _deny_reads_of(target: Path):
    """Refuse reads of one document path only, as WPS does, leaving the lock files alone."""
    original_open = Path.open

    def fake_open(self, *args, **kwargs):
        if self == target:
            raise PermissionError(13, "Permission denied", str(target))
        return original_open(self, *args, **kwargs)

    return patch.object(Path, "open", fake_open)


class HeldDocumentIdentityTests(unittest.TestCase):
    def test_permission_error_reads_as_held_by_another_handle(self):
        with tempfile.TemporaryDirectory() as tmp:
            document = Path(tmp) / "held.xlsx"
            document.write_bytes(b"not read")
            with _deny_reads_of(document):
                with self.assertRaises(OSError) as raised:
                    file_identity(document)

            self.assertIn("held open by another handle", str(raised.exception))
            self.assertIn("Nothing was written, saved or closed", str(raised.exception))
            self.assertIsInstance(raised.exception.__cause__, PermissionError)

    def test_backup_of_a_held_document_is_refused_with_the_held_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            document = Path(tmp) / "held.xlsx"
            Workbook().save(document)
            ok, record, _ = register_document("spreadsheets", str(document), workspace)

            with _deny_reads_of(document):
                ok, _result, errors, _replayed = create_backup(record["document_id"], "req-held-backup", workspace=workspace)

            self.assertFalse(ok)
            self.assertEqual(errors[0]["code"], "COM_OPERATION_FAILED")
            self.assertIn("held open by another handle", errors[0]["message"])
            self.assertFalse((workspace / "backups").exists() and any((workspace / "backups").iterdir()))


if __name__ == "__main__":
    unittest.main()
