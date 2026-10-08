import tempfile
import unittest
from pathlib import Path

from wps_ai_agent_cli.file_scan import infer_component, scan_directory
from wps_ai_agent_cli.sessions import register_document


class FileScanTests(unittest.TestCase):
    def test_infer_component_from_extension(self):
        self.assertEqual(infer_component("a.docx"), "writer")
        self.assertEqual(infer_component("a.xlsx"), "spreadsheets")
        self.assertEqual(infer_component("a.pptx"), "presentation")
        self.assertIsNone(infer_component("a.txt"))

    def test_scan_directory_marks_registered_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            document = Path(tmp) / "sample.docx"
            document.write_text("placeholder", encoding="utf-8")
            Path(tmp, "ignore.txt").write_text("ignore", encoding="utf-8")
            ok, record, _errors = register_document("writer", str(document), workspace)
            self.assertTrue(ok)

            ok, result, errors = scan_directory(tmp, workspace=workspace)

            self.assertTrue(ok)
            self.assertEqual(errors, [])
            self.assertEqual(result["count"], 1)
            self.assertEqual(result["files"][0]["document_id"], record["document_id"])


if __name__ == "__main__":
    unittest.main()
