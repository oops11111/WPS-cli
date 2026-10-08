import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from tests.test_writer_ops import write_minimal_docx
from wps_ai_agent_cli.batch_report import build_batch_report
from wps_ai_agent_cli.sessions import register_document


class BatchReportTests(unittest.TestCase):
    def test_batch_report_combines_scan_registration_and_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            registered_doc = Path(tmp) / "registered.docx"
            unregistered_book = Path(tmp) / "unregistered.xlsx"
            write_minimal_docx(registered_doc, "alpha beta")
            workbook = Workbook()
            workbook.save(unregistered_book)
            ok, record, _errors = register_document("writer", str(registered_doc), workspace)
            self.assertTrue(ok)

            ok, result, errors = build_batch_report(tmp, workspace=workspace)

            self.assertTrue(ok)
            self.assertEqual(errors, [])
            self.assertEqual(result["summary"]["total_files"], 2)
            self.assertEqual(result["summary"]["registered_files"], 1)
            self.assertEqual(result["summary"]["unregistered_files"], 1)
            self.assertEqual(result["summary"]["snapshot_passed"], 1)
            self.assertEqual(result["summary"]["snapshot_skipped"], 1)
            by_name = {item["name"]: item for item in result["files"]}
            self.assertEqual(by_name["registered.docx"]["document_id"], record["document_id"])
            self.assertEqual(by_name["registered.docx"]["snapshot_status"], "passed")
            self.assertEqual(by_name["registered.docx"]["snapshot_summary"]["paragraph_count"], 1)
            self.assertEqual(by_name["unregistered.xlsx"]["snapshot_status"], "skipped")

    def test_batch_report_can_disable_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            registered_doc = Path(tmp) / "registered.docx"
            write_minimal_docx(registered_doc, "alpha beta")
            ok, _record, _errors = register_document("writer", str(registered_doc), workspace)
            self.assertTrue(ok)

            ok, result, errors = build_batch_report(
                tmp,
                include_snapshots=False,
                workspace=workspace,
            )

            self.assertTrue(ok)
            self.assertEqual(errors, [])
            self.assertFalse(result["summary"]["snapshots_enabled"])
            self.assertEqual(result["files"][0]["snapshot_status"], "disabled")


if __name__ == "__main__":
    unittest.main()
