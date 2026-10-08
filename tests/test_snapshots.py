import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from tests.test_presentation_ops import write_minimal_pptx
from tests.test_writer_ops import write_minimal_docx_paragraphs
from wps_ai_agent_cli.sessions import register_document
from wps_ai_agent_cli.snapshots import snapshot_document


class SnapshotTests(unittest.TestCase):
    def test_snapshot_writer_returns_paragraph_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            document = Path(tmp) / "sample.docx"
            write_minimal_docx_paragraphs(document, ["alpha", "", "beta gamma"])
            ok, record, _errors = register_document("writer", str(document), workspace)
            self.assertTrue(ok)

            ok, result, errors = snapshot_document(record["document_id"], workspace)

            self.assertTrue(ok)
            self.assertEqual(errors, [])
            self.assertEqual(result["paragraph_count"], 3)
            self.assertEqual(result["non_empty_paragraph_count"], 2)
            self.assertEqual(result["paragraphs"][0]["preview"], "alpha")

    def test_snapshot_spreadsheet_returns_formula_and_error_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            document = Path(tmp) / "sample.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "Calculation"
            sheet["A1"] = 1
            sheet["B1"] = "=A1+1"
            sheet["C1"] = "#DIV/0!"
            workbook.save(document)
            ok, record, _errors = register_document("spreadsheets", str(document), workspace)
            self.assertTrue(ok)

            ok, result, errors = snapshot_document(record["document_id"], workspace)

            self.assertTrue(ok)
            self.assertEqual(errors, [])
            self.assertEqual(result["sheet_count"], 1)
            self.assertEqual(result["formula_count"], 1)
            self.assertEqual(result["formula_error_count"], 1)
            self.assertEqual(result["sheets"][0]["formula_cells"][0]["cell"], "B1")

    def test_snapshot_presentation_returns_text_object_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            document = Path(tmp) / "sample.pptx"
            write_minimal_pptx(document, ["alpha beta", "gamma"])
            ok, record, _errors = register_document("presentation", str(document), workspace)
            self.assertTrue(ok)

            ok, result, errors = snapshot_document(record["document_id"], workspace)

            self.assertTrue(ok)
            self.assertEqual(errors, [])
            self.assertEqual(result["slide_count"], 2)
            self.assertEqual(result["text_object_count"], 2)
            self.assertEqual(result["non_empty_text_object_count"], 2)
            self.assertEqual(result["slides"][0]["objects"][0]["preview"], "alpha beta")


if __name__ == "__main__":
    unittest.main()
