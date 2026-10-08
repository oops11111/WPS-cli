import tempfile
import unittest
import json
import io
from unittest.mock import patch
from pathlib import Path

from wps_ai_agent_cli.backups import create_backup, list_backups, restore_backup
from wps_ai_agent_cli.cli import run
from wps_ai_agent_cli.mcp_adapter import call_mcp_tool
from wps_ai_agent_cli.sessions import register_document


class BackupTests(unittest.TestCase):
    def test_create_backup_copies_file_and_replays_same_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            document = Path(tmp) / "sample.docx"
            document.write_text("content", encoding="utf-8")
            ok, record, errors = register_document("writer", str(document), workspace)
            self.assertTrue(ok)
            self.assertEqual(errors, [])

            ok, result, errors, replayed = create_backup(
                record["document_id"],
                request_id="req-1",
                workspace=workspace,
            )
            self.assertTrue(ok)
            self.assertFalse(replayed)
            self.assertEqual(errors, [])
            self.assertTrue(Path(result["backup_path"]).exists())

            ok, replay_result, errors, replayed = create_backup(
                record["document_id"],
                request_id="req-1",
                workspace=workspace,
            )
            self.assertTrue(ok)
            self.assertTrue(replayed)
            self.assertEqual(errors, [])
            self.assertEqual(replay_result["backup_path"], result["backup_path"])

    def test_create_backup_dry_run_does_not_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            document = Path(tmp) / "sample.docx"
            document.write_text("content", encoding="utf-8")
            ok, record, _errors = register_document("writer", str(document), workspace)
            self.assertTrue(ok)

            ok, result, errors, replayed = create_backup(
                record["document_id"],
                request_id="req-dry",
                dry_run=True,
                workspace=workspace,
            )

            self.assertTrue(ok)
            self.assertFalse(replayed)
            self.assertEqual(errors, [])
            self.assertFalse(result["created"])
            self.assertFalse(Path(result["backup_path"]).exists())

    def test_list_backups_returns_document_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            document = Path(tmp) / "sample.docx"
            document.write_text("content", encoding="utf-8")
            ok, record, _errors = register_document("writer", str(document), workspace)
            self.assertTrue(ok)
            ok, backup, _errors, _replayed = create_backup(
                record["document_id"],
                request_id="req-list",
                workspace=workspace,
            )
            self.assertTrue(ok)

            ok, result, errors = list_backups(record["document_id"], workspace)

            self.assertTrue(ok)
            self.assertEqual(errors, [])
            self.assertEqual(result["count"], 1)
            self.assertEqual(result["backups"][0]["backup_path"], backup["backup_path"])
            self.assertEqual(result["backups"][0]["document_id"], record["document_id"])

    def test_list_backups_parses_timestamp_for_multi_suffix_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            document = Path(tmp) / "sample.v1.docx"
            document.write_text("content", encoding="utf-8")
            ok, record, _errors = register_document("writer", str(document), workspace)
            self.assertTrue(ok)
            ok, _backup, _errors, _replayed = create_backup(
                record["document_id"],
                request_id="req-list-multi-suffix",
                workspace=workspace,
            )
            self.assertTrue(ok)

            ok, result, errors = list_backups(record["document_id"], workspace)

            self.assertTrue(ok)
            self.assertEqual(errors, [])
            self.assertIsNotNone(result["backups"][0]["created_at"])

    def test_restore_backup_dry_run_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            document = Path(tmp) / "sample.docx"
            document.write_text("original", encoding="utf-8")
            ok, record, _errors = register_document("writer", str(document), workspace)
            self.assertTrue(ok)
            ok, backup, _errors, _replayed = create_backup(
                record["document_id"],
                request_id="req-backup",
                workspace=workspace,
            )
            self.assertTrue(ok)
            document.write_text("changed", encoding="utf-8")

            ok, result, errors, replayed = restore_backup(
                record["document_id"],
                request_id="req-restore-dry",
                backup_name=Path(backup["backup_path"]).name,
                dry_run=True,
                workspace=workspace,
            )

            self.assertTrue(ok)
            self.assertFalse(replayed)
            self.assertEqual(errors, [])
            self.assertFalse(result["restored"])
            self.assertEqual(document.read_text(encoding="utf-8"), "changed")

    def test_restore_backup_copies_backup_and_protects_current_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            document = Path(tmp) / "sample.docx"
            document.write_text("original", encoding="utf-8")
            ok, record, _errors = register_document("writer", str(document), workspace)
            self.assertTrue(ok)
            ok, backup, _errors, _replayed = create_backup(
                record["document_id"],
                request_id="req-backup",
                workspace=workspace,
            )
            self.assertTrue(ok)
            document.write_text("changed", encoding="utf-8")

            ok, result, errors, replayed = restore_backup(
                record["document_id"],
                request_id="req-restore",
                backup_name=Path(backup["backup_path"]).name,
                workspace=workspace,
            )

            self.assertTrue(ok)
            self.assertFalse(replayed)
            self.assertEqual(errors, [])
            self.assertTrue(result["restored"])
            self.assertTrue(Path(result["pre_restore_backup"]["backup_path"]).exists())
            self.assertEqual(document.read_text(encoding="utf-8"), "original")

            ok, replay_result, errors, replayed = restore_backup(
                record["document_id"],
                request_id="req-restore",
                backup_name=Path(backup["backup_path"]).name,
                workspace=workspace,
            )
            self.assertTrue(ok)
            self.assertTrue(replayed)
            self.assertEqual(errors, [])
            self.assertEqual(replay_result["backup_path"], result["backup_path"])

    def test_restore_backup_rejects_path_outside_document_backup_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            document = Path(tmp) / "sample.docx"
            other = Path(tmp) / "other.docx"
            document.write_text("content", encoding="utf-8")
            other.write_text("other", encoding="utf-8")
            ok, record, _errors = register_document("writer", str(document), workspace)
            self.assertTrue(ok)

            ok, _result, errors, replayed = restore_backup(
                record["document_id"],
                request_id="req-restore-invalid",
                backup_path=str(other),
                workspace=workspace,
            )

            self.assertFalse(ok)
            self.assertFalse(replayed)
            self.assertEqual(errors[0]["code"], "INVALID_BACKUP_PATH")

    def test_external_edit_and_during_copy_change_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            document = Path(tmp) / "sample.docx"
            document.write_bytes(b"original")
            _, record, _ = register_document("writer", str(document), workspace)
            document.write_bytes(b"changed")
            ok, _, errors, _ = create_backup(record["document_id"], "external-change", workspace=workspace)
            self.assertFalse(ok)
            self.assertEqual(errors[0]["code"], "DOCUMENT_IDENTITY_CHANGED")

            register_document("writer", str(document), workspace)
            from shutil import copy2

            def change_while_copying(source, target):
                copy2(source, target)
                document.write_bytes(b"changed again")

            with patch("wps_ai_agent_cli.backups.shutil.copy2", side_effect=change_while_copying):
                ok, _, errors, _ = create_backup(record["document_id"], "during-copy", workspace=workspace)
            self.assertFalse(ok)
            self.assertEqual(errors[0]["code"], "DOCUMENT_CHANGED_DURING_BACKUP")

    def test_missing_and_legacy_unverified_registration_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            document = Path(tmp) / "sample.docx"
            document.write_bytes(b"original")
            _, record, _ = register_document("writer", str(document), workspace)
            state_path = workspace / ".wps-agent" / "documents.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            for key in ("source_sha256", "file_device", "file_inode"):
                state["documents"][record["document_id"]].pop(key)
            state_path.write_text(json.dumps(state), encoding="utf-8")
            ok, _, errors, _ = create_backup(record["document_id"], "legacy", workspace=workspace)
            self.assertFalse(ok)
            self.assertEqual(errors[0]["code"], "DOCUMENT_IDENTITY_UNVERIFIED")
            register_document("writer", str(document), workspace)
            document.rename(Path(tmp) / "renamed.docx")
            ok, _, errors, _ = create_backup(record["document_id"], "renamed", workspace=workspace)
            self.assertFalse(ok)
            self.assertEqual(errors[0]["code"], "INPUT_FILE_NOT_FOUND")

    def test_cli_mcp_reject_stale_document_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            document = Path(tmp) / "sample.docx"
            document.write_bytes(b"original")
            _, record, _ = register_document("writer", str(document), tmp)
            document.write_bytes(b"externally edited")
            with patch("wps_ai_agent_cli.backups.get_document", return_value=record):
                output = io.StringIO()
                self.assertEqual(run(["backup-document", "--document-id", record["document_id"],
                                      "--request-id", "stale-cli-backup"], output_stream=output), 0)
                cli = json.loads(output.getvalue())
                mcp_ok, mcp, mcp_errors = call_mcp_tool("wps_agent_backup_document", {
                    "document_id": record["document_id"], "request_id": "stale-mcp-backup",
                })
            self.assertFalse(cli["ok"])
            self.assertEqual(cli["errors"][0]["code"], "DOCUMENT_IDENTITY_CHANGED")
            self.assertFalse(mcp_ok)
            self.assertEqual(mcp_errors, [])
            self.assertFalse(mcp["response"]["ok"])
            self.assertEqual(mcp["response"]["errors"][0]["code"], "DOCUMENT_IDENTITY_CHANGED")


if __name__ == "__main__":
    unittest.main()
