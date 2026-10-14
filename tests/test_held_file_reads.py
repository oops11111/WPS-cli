"""Commands without their own held-file check answer with DOCUMENT_HELD_OPEN, not an uncaught error.

Found in the P4-007 Windows run: spreadsheet_read, spreadsheet_sheets, snapshot_document and batch_report on a
workbook held by another handle raised PermissionError, which MCP reported as MCP_TOOL_EXECUTION_FAILED.
snapshot_document reports the held file itself, so batch-report marks that file as held and goes on.
"""

import io
import json
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook

from tests.isolation import use_temporary_cwd
from wps_ai_agent_cli.cli import run
from wps_ai_agent_cli.mcp_adapter import call_mcp_tool
from wps_ai_agent_cli.sessions import register_document

_restore_cwd = None


def setUpModule():
    global _restore_cwd
    _restore_cwd = use_temporary_cwd()


def tearDownModule():
    _restore_cwd()


_REAL_ZIPFILE = zipfile.ZipFile
_SHARING_VIOLATION = "The process cannot access the file because it is being used by another process"


def _hold(target: Path):
    """Make every zip open of target fail the way a file held with no sharing does on Windows."""

    def zip_open(path, *args, **kwargs):
        if Path(path).resolve() == target.resolve():
            raise PermissionError(13, _SHARING_VIOLATION, str(path))
        return _REAL_ZIPFILE(path, *args, **kwargs)

    return [patch("zipfile.ZipFile", side_effect=zip_open), patch("wps_ai_agent_cli.ooxml.ZipFile", side_effect=zip_open)]


class HeldFileReadTests(unittest.TestCase):
    def setUp(self):
        self.book = Path("held-reads") / "book.xlsx"
        self.book.parent.mkdir(exist_ok=True)
        workbook = Workbook()
        workbook.active["A1"] = "seed"
        workbook.save(self.book)
        ok, record, errors = register_document("spreadsheets", str(self.book))
        self.assertTrue(ok, errors)
        self.document_id = record["document_id"]
        for patcher in _hold(self.book):
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_cli(self, argv):
        output = io.StringIO()
        exit_code = run(argv, output_stream=output)
        return exit_code, json.loads(output.getvalue())

    def test_read_commands_report_document_held_open(self):
        for argv in (
            ["spreadsheet-read", "--document-id", self.document_id, "--range", "A1:B2"],
            ["spreadsheet-sheets", "--document-id", self.document_id],
        ):
            with self.subTest(command=argv[0]):
                exit_code, envelope = self.run_cli(argv)

                self.assertEqual(exit_code, 0)
                self.assertFalse(envelope["ok"])
                self.assertEqual(envelope["command"], argv[0])
                self.assertEqual([error["code"] for error in envelope["errors"]], ["DOCUMENT_HELD_OPEN"])
                message = envelope["errors"][0]["message"]
                self.assertIn(_SHARING_VIOLATION, message)
                self.assertIn("no document was changed", message)
                self.assertFalse(envelope["data"]["mutates_document"])

    def test_snapshot_document_reports_document_held_open(self):
        exit_code, envelope = self.run_cli(["snapshot-document", "--document-id", self.document_id])

        self.assertEqual(exit_code, 0)
        self.assertFalse(envelope["ok"])
        self.assertEqual([error["code"] for error in envelope["errors"]], ["DOCUMENT_HELD_OPEN"])
        self.assertIn(_SHARING_VIOLATION, envelope["errors"][0]["message"])

    def test_batch_report_marks_the_held_file_and_reports_the_others(self):
        other = self.book.parent / "other.xlsx"
        workbook = Workbook()
        workbook.active["A1"] = "free"
        workbook.save(other)
        ok, _record, errors = register_document("spreadsheets", str(other))
        self.assertTrue(ok, errors)

        exit_code, envelope = self.run_cli(["batch-report", "--path", str(self.book.parent)])

        self.assertEqual(exit_code, 0)
        self.assertTrue(envelope["ok"])
        self.assertEqual(envelope["errors"], [])
        summary = envelope["data"]["summary"]
        self.assertEqual((summary["snapshot_passed"], summary["snapshot_held"], summary["snapshot_failed"]), (1, 1, 0))
        by_name = {item["name"]: item for item in envelope["data"]["files"]}
        self.assertEqual(by_name["other.xlsx"]["snapshot_status"], "passed")
        held = by_name["book.xlsx"]
        self.assertEqual(held["snapshot_status"], "held")
        self.assertEqual([error["code"] for error in held["snapshot_errors"]], ["DOCUMENT_HELD_OPEN"])
        # The report is complete but one snapshot is missing, so validation does not pass.
        self.assertEqual(envelope["validation"]["status"], "failed")
        check = {item["name"]: item for item in envelope["validation"]["checks"]}["snapshots_collected"]
        self.assertFalse(check["passed"])
        self.assertEqual(check["details"]["held"], 1)

    def test_strict_exit_returns_one(self):
        exit_code, envelope = self.run_cli(
            ["spreadsheet-read", "--document-id", self.document_id, "--range", "A1", "--strict-exit"]
        )

        self.assertEqual(exit_code, 1)
        self.assertEqual(envelope["errors"][0]["code"], "DOCUMENT_HELD_OPEN")

    def test_mcp_call_returns_the_envelope_instead_of_an_execution_failure(self):
        ok, result, errors = call_mcp_tool(
            "wps_agent_spreadsheet_read", {"document_id": self.document_id, "range": "A1"}
        )

        self.assertFalse(ok)
        self.assertEqual([error["code"] for error in errors], ["DOCUMENT_HELD_OPEN"])
        self.assertEqual(result["response"]["errors"][0]["code"], "DOCUMENT_HELD_OPEN")


class FallbackScopeTests(unittest.TestCase):
    def run_cli(self, argv):
        output = io.StringIO()
        run(argv, output_stream=output)
        return json.loads(output.getvalue())

    def test_a_command_that_can_change_documents_does_not_claim_nothing_changed(self):
        error = PermissionError(13, _SHARING_VIOLATION, "book.xlsx")
        with patch("wps_ai_agent_cli.cli.spreadsheet_write_response", side_effect=error):
            envelope = self.run_cli(
                ["spreadsheet-write", "--document-id", "doc_x", "--range", "A1", "--values-json", "[[1]]"]
            )

        self.assertEqual(envelope["errors"][0]["code"], "DOCUMENT_HELD_OPEN")
        self.assertTrue(envelope["data"]["mutates_document"])
        message = envelope["errors"][0]["message"]
        self.assertIn("mutation-request-inspect", message)
        self.assertNotIn("no document was changed", message)

    def test_other_os_errors_are_not_reported_as_held(self):
        with patch("wps_ai_agent_cli.cli.spreadsheet_sheets_response", side_effect=FileExistsError(17, "exists")):
            with self.assertRaises(FileExistsError):
                run(["spreadsheet-sheets", "--document-id", "doc_x"], output_stream=io.StringIO())


if __name__ == "__main__":
    unittest.main()
