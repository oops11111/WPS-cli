import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wps_ai_agent_cli.errors import (
    DOCUMENT_HELD_OPEN,
    DOCUMENT_IDENTITY_UNAVAILABLE,
    DocumentHeldOpenError,
    identity_error,
)
from wps_ai_agent_cli.file_hold import probe_unknown_error
from wps_ai_agent_cli.sessions import file_identity, register_document


class IdentityErrorTests(unittest.TestCase):
    def test_held_open_error_maps_to_document_held_open(self):
        error = identity_error(DocumentHeldOpenError("held"))
        self.assertEqual(error, {"code": DOCUMENT_HELD_OPEN, "message": "held"})

    def test_other_os_error_stays_identity_unavailable(self):
        self.assertEqual(identity_error(OSError("disk gone"))["code"], DOCUMENT_IDENTITY_UNAVAILABLE)

    def test_unknown_probe_result_is_not_reported_as_held(self):
        # Could not check is a precaution, not evidence that another handle holds the file.
        self.assertEqual(probe_unknown_error("document", "access check failed")["code"], "COM_OPERATION_FAILED")


class FileIdentityHeldTests(unittest.TestCase):
    def test_permission_error_raises_document_held_open_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            document = Path(tmp) / "held.docx"
            document.write_bytes(b"x")
            with patch.object(Path, "open", side_effect=PermissionError(13, "Permission denied")):
                with self.assertRaises(DocumentHeldOpenError) as raised:
                    file_identity(document)
            self.assertIsInstance(raised.exception, OSError)
            self.assertIsInstance(raised.exception.__cause__, PermissionError)

    def test_registration_of_a_held_file_reports_document_held_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            document = Path(tmp) / "held.docx"
            document.write_bytes(b"x")
            with patch(
                "wps_ai_agent_cli.sessions.file_identity",
                side_effect=DocumentHeldOpenError("held open by another handle"),
            ):
                ok, _record, errors = register_document("writer", str(document), workspace)
            self.assertFalse(ok)
            self.assertEqual(errors[0]["code"], DOCUMENT_HELD_OPEN)


if __name__ == "__main__":
    unittest.main()
