import tempfile
import unittest
import io
import json
from contextlib import chdir
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook

from wps_ai_agent_cli.operations import get_operation, inspect_mutation_request, list_operations, record_operation, replay_operation
from wps_ai_agent_cli.backups import create_backup
from wps_ai_agent_cli.sessions import get_document, register_document
from wps_ai_agent_cli.spreadsheet_ops import rename_spreadsheet_sheet
from wps_ai_agent_cli.cli import run
from wps_ai_agent_cli.mcp_adapter import call_mcp_tool


class OperationLedgerTests(unittest.TestCase):
    def test_mutation_request_inspection_cli_mcp_and_read_only_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.docx"
            path.write_bytes(b"before")
            ok, document, errors = register_document("writer", str(path), tmp)
            self.assertTrue(ok, errors)
            request_id = "req-inspect"
            self.assertEqual(inspect_mutation_request(request_id, tmp)["status"], "no_evidence")
            ok, _backup, errors, _ = create_backup(document["document_id"], f"{request_id}:backup", workspace=tmp)
            self.assertTrue(ok, errors)
            self.assertEqual(inspect_mutation_request(request_id, tmp)["status"], "retryable")
            path.write_bytes(b"changed")
            self.assertEqual(inspect_mutation_request(request_id, tmp)["status"], "ambiguous")
            before = {item: item.read_bytes() for item in (Path(tmp) / ".wps-agent").rglob("*.json")}
            with chdir(tmp):
                output = io.StringIO()
                self.assertEqual(run(["mutation-request-inspect", "--request", request_id], output_stream=output), 0)
                cli = json.loads(output.getvalue())
                ok, mcp, errors = call_mcp_tool("wps_agent_mutation_request_inspect", {"request": request_id})
            self.assertTrue(ok, errors)
            self.assertEqual(cli["data"]["mutation_request"], mcp["response"]["data"]["mutation_request"])
            self.assertEqual(cli["validation"]["status"], "warning")
            self.assertEqual(cli["data"]["mutation_request"]["status"], "ambiguous")
            guidance = cli["data"]["mutation_request"]["recovery_guidance"]
            self.assertTrue(any("Do not automatically retry" in item for item in guidance))
            self.assertEqual({item: item.read_bytes() for item in (Path(tmp) / ".wps-agent").rglob("*.json")}, before)

    def test_mutation_command_reports_unrecorded_save_before_target_lookup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.xlsx"
            workbook = Workbook()
            workbook.active.title = "Before"
            workbook.save(path)
            workbook.close()
            ok, document, errors = register_document("spreadsheets", str(path), tmp)
            self.assertTrue(ok, errors)
            request_id = "req-interrupted"
            ok, _backup, errors, _ = create_backup(document["document_id"], f"{request_id}:backup", workspace=tmp)
            self.assertTrue(ok, errors)
            workbook = Workbook()
            workbook.active.title = "After"
            workbook.save(path)
            workbook.close()
            result = rename_spreadsheet_sheet(document["document_id"], "Before", "After", request_id, workspace=tmp)
            self.assertFalse(result[0])
            self.assertEqual(result[2][0]["code"], "UNRECORDED_MUTATION_AMBIGUOUS")

    def test_backup_evidence_blocks_reapplication_after_unrecorded_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.docx"
            path.write_bytes(b"before")
            ok, document, errors = register_document("writer", str(path), tmp)
            self.assertTrue(ok, errors)
            request_id = "req-interrupted"
            ok, backup, errors, _ = create_backup(document["document_id"], f"{request_id}:backup", workspace=tmp)
            self.assertTrue(ok, errors)
            self.assertIsNone(replay_operation(request_id, "writer-replace", {"document_id": document["document_id"]}, tmp))
            path.write_bytes(b"saved but not recorded")
            replay = replay_operation(request_id, "writer-replace", {"document_id": document["document_id"]}, tmp)
            self.assertFalse(replay[0])
            self.assertEqual(replay[2][0]["code"], "UNRECORDED_MUTATION_AMBIGUOUS")
            self.assertEqual(replay[1]["backup"]["backup_path"], backup["backup_path"])
            self.assertIsNone(get_operation(request_id, tmp))

    def test_identity_capture_failure_records_ambiguous_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.docx"
            path.write_bytes(b"before")
            ok, document, errors = register_document("writer", str(path), tmp)
            self.assertTrue(ok, errors)
            path.write_bytes(b"saved")
            with patch("wps_ai_agent_cli.operations.file_identity", side_effect=OSError("unavailable")):
                with self.assertRaises(OSError):
                    record_operation("req-save", "writer-replace", {"document_id": document["document_id"], "saved": True}, tmp)
            self.assertEqual(get_operation("req-save", tmp)["identity_capture_error"], "unavailable")
            replay = replay_operation("req-save", "writer-replace", {"document_id": document["document_id"]}, tmp)
            self.assertFalse(replay[0])
            self.assertEqual(replay[2][0]["code"], "OPERATION_IDENTITY_UNVERIFIED")

    def test_replay_repairs_identity_after_recorded_refresh_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.docx"
            path.write_bytes(b"before")
            ok, document, errors = register_document("writer", str(path), tmp)
            self.assertTrue(ok, errors)
            path.write_bytes(b"after")
            with patch("wps_ai_agent_cli.operations.refresh_document_identity", side_effect=OSError("refresh failed")):
                with self.assertRaises(OSError):
                    record_operation("req-save", "writer-replace", {"document_id": document["document_id"], "saved": True}, tmp)
            self.assertEqual(get_document(document["document_id"], tmp)["source_sha256"], document["source_sha256"])
            self.assertIsNotNone(get_operation("req-save", tmp)["source_identity_at_commit"])
            inspection = inspect_mutation_request("req-save", tmp)
            self.assertEqual(inspection["status"], "recorded_repairable")
            self.assertTrue(any("without repeating the mutation" in item for item in inspection["recovery_guidance"]))
            self.assertFalse(inspection["operation_identity"]["registered_matches_current"])
            self.assertEqual(get_document(document["document_id"], tmp)["source_sha256"], document["source_sha256"])
            replay = replay_operation("req-save", "writer-replace", {"document_id": document["document_id"]}, tmp)
            self.assertEqual(replay[0::2], (True, []))
            self.assertTrue(replay[3])
            self.assertNotEqual(get_document(document["document_id"], tmp)["source_sha256"], document["source_sha256"])

    def test_replay_does_not_register_a_different_file_as_committed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.docx"
            path.write_bytes(b"before")
            ok, document, errors = register_document("writer", str(path), tmp)
            self.assertTrue(ok, errors)
            path.write_bytes(b"saved")
            with patch("wps_ai_agent_cli.operations.refresh_document_identity", side_effect=OSError("refresh failed")):
                with self.assertRaises(OSError):
                    record_operation("req-save", "writer-replace", {"document_id": document["document_id"], "saved": True}, tmp)
            path.write_bytes(b"external change")
            self.assertEqual(inspect_mutation_request("req-save", tmp)["status"], "recorded_changed")
            replay = replay_operation("req-save", "writer-replace", {"document_id": document["document_id"]}, tmp)
            self.assertFalse(replay[0])
            self.assertEqual(replay[2][0]["code"], "OPERATION_SOURCE_CHANGED")
            self.assertEqual(get_document(document["document_id"], tmp)["source_sha256"], document["source_sha256"])

    def test_record_get_and_list_operations(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()

            record_operation("req-1", "sample", {"ok": True}, workspace)

            self.assertEqual(get_operation("req-1", workspace)["command"], "sample")
            operations = list_operations(workspace)
            self.assertEqual(len(operations), 1)
            self.assertEqual(operations[0]["request_id"], "req-1")

    def test_replay_operation_binds_command_and_all_requested_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            self.assertIsNone(replay_operation("req-1", "write", {"document_id": "doc"}, workspace))
            record_operation("req-1", "write", {"document_id": "doc", "value": [[1, 2]], "dry_run": False}, workspace)

            self.assertEqual(replay_operation("req-1", "write", {"document_id": "doc", "value": [[1, 2]], "dry_run": False}, workspace), (True, {"document_id": "doc", "value": [[1, 2]], "dry_run": False}, [], True))
            conflict = replay_operation("req-1", "write", {"document_id": "doc", "value": [[1, 3]], "dry_run": False}, workspace)
            self.assertFalse(conflict[0])
            self.assertEqual(conflict[1]["conflicting_fields"], ["value"])
            command_conflict = replay_operation("req-1", "delete", {"document_id": "doc", "value": [[1, 2]], "dry_run": False}, workspace)
            self.assertFalse(command_conflict[0])
            self.assertIn("command", command_conflict[1]["conflicting_fields"])
            self.assertEqual(command_conflict[2][0]["code"], "IDEMPOTENCY_CONFLICT")


if __name__ == "__main__":
    unittest.main()
