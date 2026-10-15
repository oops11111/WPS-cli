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


class ValidatorGuidanceTests(unittest.TestCase):
    """P7-006: agents called validate_document with only a document_id and were not told what to pass."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()

    def register(self, component, name):
        path = self.root / name
        if component == "writer":
            write_minimal_docx(path, "Owner: Finance (reviewed)")
        elif component == "spreadsheets":
            workbook = Workbook()
            workbook.active["B2"] = 42
            workbook.save(path)
        else:
            from tests.test_presentation_ops import write_minimal_pptx

            write_minimal_pptx(path, ["Status: DRAFT"])
        ok, record, errors = register_document(component, str(path), self.workspace)
        self.assertTrue(ok, errors)
        return record["document_id"]

    def validate(self, document_id, **arguments):
        return validate_document(document_id, workspace=self.workspace, **arguments)

    def test_a_writer_document_id_alone_says_what_to_pass_and_where_to_read_instead(self):
        document_id = self.register("writer", "report.docx")
        ok, _result, errors = self.validate(document_id)
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "INVALID_ARGUMENT")
        message = errors[0]["message"]
        self.assertIn("contains (--contains)", message)
        self.assertIn('contains="Status: FINAL"', message)
        self.assertIn("snapshot_document", message)
        _ok, _result, errors = self.validate(document_id, cell="B2", equals="42")
        self.assertIn("cell and equals are for spreadsheets", errors[0]["message"])

    def test_a_spreadsheet_check_names_what_is_missing(self):
        document_id = self.register("spreadsheets", "book.xlsx")
        cases = (
            ({}, "Missing: cell and equals."),
            ({"cell": "B2"}, "Missing: equals."),
            ({"equals": "42"}, "Missing: cell."),
            ({"contains": "42"}, "contains is for Writer documents"),
        )
        for arguments, expected in cases:
            with self.subTest(arguments=arguments):
                ok, _result, errors = self.validate(document_id, **arguments)
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "INVALID_ARGUMENT")
                self.assertIn(expected, errors[0]["message"])
                self.assertIn('cell="B2" equals="42"', errors[0]["message"])

    def test_a_cell_that_is_not_one_a1_address_is_an_invalid_argument_not_a_crash(self):
        document_id = self.register("spreadsheets", "book.xlsx")
        for cell in ("Sheet1!B2", "B2:C3", "R2C2", "B0"):
            with self.subTest(cell=cell):
                ok, _result, errors = self.validate(document_id, cell=cell, equals="42")
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "INVALID_ARGUMENT")
                self.assertIn("not an A1 address", errors[0]["message"])
        ok, result, errors = self.validate(document_id, cell="$b$2", equals="42")
        self.assertTrue(ok, errors)
        self.assertEqual(result["actual"], "42")

    def test_a_failed_check_says_what_was_there(self):
        writer = self.register("writer", "report.docx")
        _ok, _result, errors = self.validate(writer, contains="Finance  (reviewed)")
        self.assertEqual(errors[0]["code"], "VALIDATION_FAILED")
        self.assertIn("'Finance  (reviewed)' was not found", errors[0]["message"])
        self.assertIn("spaces included", errors[0]["message"])
        book = self.register("spreadsheets", "book.xlsx")
        _ok, _result, errors = self.validate(book, cell="B2", equals="41")
        self.assertEqual(errors[0]["message"], "Cell B2 on sheet 'Sheet' holds '42', not '41'.")

    def test_presentation_is_not_supported_and_points_to_snapshot(self):
        document_id = self.register("presentation", "deck.pptx")
        _ok, _result, errors = self.validate(document_id, contains="DRAFT")
        self.assertEqual(errors[0]["code"], "UNSUPPORTED_COMPONENT")
        self.assertIn("snapshot_document", errors[0]["message"])

    def test_the_mcp_schema_says_document_id_alone_is_not_enough(self):
        from wps_ai_agent_cli.mcp_schema import list_mcp_tool_schemas

        schema = next(item for item in list_mcp_tool_schemas() if item["name"] == "wps_agent_validate_document")
        self.assertIn("document_id alone is not enough", schema["description"])
        self.assertIn("snapshot_document", schema["description"])
        properties = schema["input_schema"]["properties"]
        self.assertTrue(properties["contains"]["description"].startswith("Writer: required."))
        self.assertTrue(properties["cell"]["description"].startswith("Spreadsheets: required with equals."))
        self.assertTrue(properties["equals"]["description"].startswith("Spreadsheets: required with cell."))


if __name__ == "__main__":
    unittest.main()
