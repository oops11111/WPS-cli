import tempfile
import unittest
import os
from pathlib import Path

from wps_ai_agent_cli.sessions import file_identity, get_document, list_documents, register_document, stable_document_id


class SessionRegistryTests(unittest.TestCase):
    def test_stable_document_id_is_repeatable(self):
        first = stable_document_id("writer", "sample.docx")
        second = stable_document_id("writer", "sample.docx")

        self.assertEqual(first, second)
        self.assertTrue(first.startswith("doc_"))

    def test_register_document_persists_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            document = Path(tmp) / "sample.docx"
            document.write_text("placeholder", encoding="utf-8")

            ok, record, errors = register_document(
                component="writer",
                path=str(document),
                workspace=workspace,
            )

            self.assertTrue(ok)
            self.assertEqual(errors, [])
            self.assertEqual(record["component"], "writer")
            self.assertEqual(list_documents(workspace)[0]["document_id"], record["document_id"])
            self.assertEqual({key: record[key] for key in file_identity(document)}, file_identity(document))

    def test_same_path_replacement_requires_explicit_reregistration(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            document = Path(tmp) / "sample.docx"
            replacement = Path(tmp) / "replacement.docx"
            document.write_bytes(b"original")
            ok, first, errors = register_document("writer", str(document), workspace)
            self.assertTrue(ok, errors)
            replacement.write_bytes(b"original")
            os.replace(replacement, document)
            self.assertNotEqual(first["file_inode"], file_identity(document)["file_inode"])
            ok, second, errors = register_document("writer", str(document), workspace)
            self.assertTrue(ok, errors)
            self.assertEqual(first["document_id"], second["document_id"])
            self.assertEqual(get_document(second["document_id"], workspace)["file_inode"], file_identity(document)["file_inode"])


if __name__ == "__main__":
    unittest.main()
