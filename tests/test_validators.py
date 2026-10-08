import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from tests.test_writer_ops import write_minimal_docx
from wps_ai_agent_cli.sessions import register_document
from wps_ai_agent_cli.validators import validate_document


class ValidatorTests(unittest.TestCase):
    def test_validate_writer_contains_body_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            document = Path(tmp) / "sample.docx"
            write_minimal_docx(document, "hello validation")
            ok, record, _errors = register_document("writer", str(document), workspace)
            self.assertTrue(ok)

            ok, result, errors = validate_document(
                record["document_id"],
                contains="validation",
                workspace=workspace,
            )

            self.assertTrue(ok)
            self.assertEqual(errors, [])
            self.assertEqual(result["count"], 1)

    def test_validate_spreadsheet_cell_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            document = Path(tmp) / "sample.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet["D4"] = 18
            workbook.save(document)
            ok, record, _errors = register_document("spreadsheets", str(document), workspace)
            self.assertTrue(ok)

            ok, result, errors = validate_document(
                record["document_id"],
                cell="D4",
                equals="18",
                workspace=workspace,
            )

            self.assertTrue(ok)
            self.assertEqual(errors, [])
            self.assertEqual(result["actual"], "18")


if __name__ == "__main__":
    unittest.main()
