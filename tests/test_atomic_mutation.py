from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook

from wps_ai_agent_cli.atomic_mutation import NO_ROLLBACK_CODES, atomic_mutation
from wps_ai_agent_cli.backups import create_backup, list_backups
from wps_ai_agent_cli.errors import ROLLBACK_BLOCKED, ROLLBACK_FAILED, ROLLED_BACK
from wps_ai_agent_cli.operations import record_operation, replay_operation
from wps_ai_agent_cli.sessions import register_document


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AtomicMutationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.workspace = root / "workspace"
        self.workspace.mkdir()
        self.document = root / "book.xlsx"
        Workbook().save(self.document)
        ok, record, _ = register_document("spreadsheets", str(self.document), self.workspace)
        self.assertTrue(ok)
        self.document_id = record["document_id"]
        ok, backup, _, _ = create_backup(self.document_id, "req-atomic-write:backup", workspace=self.workspace)
        self.assertTrue(ok)
        self.backup_path = backup["backup_path"]
        self.original_bytes = self.document.read_bytes()
        # By default WPS has nothing open; each test that needs another answer patches it.
        probe = patch("wps_ai_agent_cli.open_documents.list_open_documents", return_value=(True, {"documents": []}, []))
        self._probe = probe.start()
        self.addCleanup(probe.stop)

    def tearDown(self):
        self._tmp.cleanup()

    def _mutation(self, change_file: bool, ok: bool = False, raise_after_change: bool = False):
        document, backup_path, workspace = self.document, self.backup_path, self.workspace

        @atomic_mutation
        def write(document_id, request_id, workspace=".", **_):
            if change_file:
                document.write_bytes(b"WPS saved this")
            if raise_after_change:
                raise RuntimeError("COM dropped after save")
            return (
                ok,
                {"document_id": document_id, "backup": {"backup_path": backup_path}},
                [{"code": "VALIDATION_FAILED", "message": "read-back mismatch"}] if not ok else [],
                False,
            )

        return write(self.document_id, "req-atomic-write", workspace=workspace)

    def test_failed_write_that_changed_the_file_is_restored_byte_for_byte(self):
        ok, result, errors, replayed = self._mutation(change_file=True)

        self.assertFalse(ok)
        self.assertEqual(self.document.read_bytes(), self.original_bytes)
        self.assertEqual(result["rollback"]["performed"], True)
        self.assertEqual([error["code"] for error in errors], ["VALIDATION_FAILED", ROLLED_BACK])
        self.assertIn("not open in WPS", errors[-1]["message"])

    def test_rollback_says_whether_wps_still_has_the_document_open(self):
        open_document = {"full_name": str(self.document), "component": "spreadsheets"}
        self._probe.return_value = (True, {"documents": [open_document]}, [])

        ok, result, errors, _ = self._mutation(change_file=True)

        self.assertIs(result["rollback"]["open_in_wps"], True)
        self.assertIn("is open in WPS now", errors[-1]["message"])

    def test_rollback_reports_when_the_document_is_not_open_in_wps(self):
        ok, result, errors, _ = self._mutation(change_file=True)

        self.assertIs(result["rollback"]["open_in_wps"], False)
        self.assertIn("not open in WPS", errors[-1]["message"])

    def test_failed_wps_probe_does_not_change_the_rollback(self):
        self._probe.side_effect = RuntimeError("no WPS on this machine")

        ok, result, errors, _ = self._mutation(change_file=True)

        self.assertEqual(self.document.read_bytes(), self.original_bytes)
        self.assertIsNone(result["rollback"]["open_in_wps"])
        self.assertEqual(errors[-1]["code"], ROLLED_BACK)
        self.assertIn("Could not check", errors[-1]["message"])

    def test_probe_failure_keeps_its_reason_in_the_result(self):
        self._probe.side_effect = RuntimeError("attach failed")

        ok, result, errors, _ = self._mutation(change_file=True)

        self.assertIsNone(result["rollback"]["open_in_wps"])
        self.assertIn("RuntimeError", result["rollback"]["open_in_wps_error"])

    def test_locked_file_blocks_the_undo_and_says_how_to_restore(self):
        locked = {"code": "RESTORE_TARGET_WRITE_FAILED", "message": "Access denied", "reason": "file_locked"}
        with patch("wps_ai_agent_cli.atomic_mutation._restore_file_atomically", return_value=locked):
            ok, result, errors, _ = self._mutation(change_file=True)

        self.assertFalse(ok)
        self.assertEqual(result["rollback"], {"performed": False, "blocked": "file_locked", "open_in_wps": False})
        self.assertEqual(errors[-1]["code"], ROLLBACK_BLOCKED)
        self.assertIn("close the document", errors[-1]["message"].lower())
        self.assertIn("restore-backup", errors[-1]["message"])
        self.assertIn(self.backup_path, errors[-1]["message"])
        self.assertNotEqual(self.document.read_bytes(), self.original_bytes)

    def test_a_real_permission_error_on_replace_is_reported_as_locked(self):
        with patch("wps_ai_agent_cli.backups.os.replace", side_effect=PermissionError(13, "Access is denied")):
            ok, result, errors, _ = self._mutation(change_file=True)

        self.assertEqual(errors[-1]["code"], ROLLBACK_BLOCKED)
        self.assertNotEqual(self.document.read_bytes(), self.original_bytes)

    def test_failed_write_that_left_the_file_alone_is_not_rolled_back(self):
        ok, result, errors, _ = self._mutation(change_file=False)

        self.assertFalse(ok)
        self.assertEqual(
            result["rollback"], {"performed": False, "reason": "the file already matches the pre-write backup"}
        )
        self.assertEqual([error["code"] for error in errors], ["VALIDATION_FAILED"])

    def test_successful_write_is_left_as_written(self):
        document, backup_path = self.document, self.backup_path

        @atomic_mutation
        def write(document_id, request_id, workspace=".", **_):
            document.write_bytes(b"kept")
            return True, {"document_id": document_id, "backup": {"backup_path": backup_path}}, [], False

        ok, result, errors, _ = write(self.document_id, "req-atomic-ok", workspace=self.workspace)

        self.assertTrue(ok)
        self.assertEqual(self.document.read_bytes(), b"kept")
        self.assertNotIn("rollback", result)
        self.assertEqual(errors, [])

    def test_exception_after_the_save_is_reported_as_rolled_back(self):
        ok, result, errors, _ = self._mutation(change_file=True, raise_after_change=True)

        self.assertFalse(ok)
        self.assertEqual(self.document.read_bytes(), self.original_bytes)
        self.assertEqual(result["rollback"]["performed"], True)

    def test_exception_before_any_backup_is_still_raised(self):
        @atomic_mutation
        def write(document_id, request_id, workspace=".", **_):
            raise RuntimeError("failed before the backup")

        with self.assertRaises(RuntimeError):
            write(self.document_id, "req-never-backed-up", workspace=self.workspace)

    def test_restore_failure_is_reported_with_the_backup_to_use(self):
        failed_restore = {"code": "COM_OPERATION_FAILED", "message": "disk full"}
        with patch("wps_ai_agent_cli.atomic_mutation._restore_file_atomically", return_value=failed_restore):
            ok, result, errors, _ = self._mutation(change_file=True)

        self.assertFalse(ok)
        self.assertEqual(errors[-1]["code"], ROLLBACK_FAILED)
        self.assertIn(self.backup_path, errors[-1]["message"])
        self.assertIn("disk full", errors[-1]["message"])
        self.assertNotEqual(_sha(self.document), _sha(Path(self.backup_path)))

    def _failing_with(self, code: str):
        backup_path = self.backup_path

        @atomic_mutation
        def write(document_id, request_id, workspace=".", **_):
            return (
                False,
                {"document_id": document_id, "backup": {"backup_path": backup_path}},
                [{"code": code, "message": "not this command's file"}],
                False,
            )

        return write

    def test_a_file_this_command_did_not_write_is_never_restored(self):
        for code in sorted(NO_ROLLBACK_CODES):
            with self.subTest(code=code):
                self.document.write_bytes(b"someone else's change")
                ok, result, errors, _ = self._failing_with(code)(self.document_id, "req-x", workspace=self.workspace)
                self.assertFalse(ok)
                self.assertEqual(self.document.read_bytes(), b"someone else's change")
                self.assertEqual(
                    result["rollback"],
                    {
                        "performed": False,
                        "skipped_for": code,
                        "reason": "the file is not in the state this command left it, so the backup was not copied over it",
                        "backup_path": self.backup_path,
                    },
                )
                self.assertEqual([error["code"] for error in errors], [code])

    def test_retrying_a_committed_write_after_the_user_edited_the_file_keeps_both(self):
        document, workspace = self.document, self.workspace

        @atomic_mutation
        def write(document_id, request_id, workspace=".", **_):
            replay = replay_operation(request_id, "fake-write", {"document_id": document_id}, workspace)
            if replay is not None:
                return replay
            ok, backup, errors, _ = create_backup(document_id, f"{request_id}:backup", workspace=workspace)
            self.assertTrue(ok, errors)
            document.write_bytes(b"the committed write")
            result = {"document_id": document_id, "backup": backup}
            record_operation(request_id, "fake-write", result, workspace)
            return True, result, [], False

        ok, _, errors, _ = write(self.document_id, "req-retry", workspace=workspace)
        self.assertTrue(ok, errors)
        document.write_bytes(b"the committed write, then the user's edit")

        ok, result, errors, _ = write(self.document_id, "req-retry", workspace=workspace)

        self.assertFalse(ok)
        self.assertEqual(document.read_bytes(), b"the committed write, then the user's edit")
        self.assertIn(errors[0]["code"], NO_ROLLBACK_CODES)
        self.assertNotIn(ROLLED_BACK, [error["code"] for error in errors])

    def test_an_exception_after_the_operation_was_recorded_leaves_the_committed_write(self):
        document, backup_path = self.document, self.backup_path

        @atomic_mutation
        def write(document_id, request_id, workspace=".", **_):
            document.write_bytes(b"the committed write")
            record_operation(
                request_id, "fake-write", {"document_id": document_id, "backup_path": backup_path}, workspace
            )
            raise OSError("identity capture failed after the record")

        with self.assertRaises(OSError):
            write(self.document_id, "req-atomic-write", workspace=self.workspace)
        self.assertEqual(document.read_bytes(), b"the committed write")


class BackupFileTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.workspace = root / "workspace"
        self.workspace.mkdir()
        self.document = root / "book.xlsx"
        Workbook().save(self.document)
        ok, record, _ = register_document("spreadsheets", str(self.document), self.workspace)
        self.assertTrue(ok)
        self.document_id = record["document_id"]

    def test_a_copy_taken_while_the_file_changed_is_removed_and_not_offered(self):
        real_copy = __import__("shutil").copy2

        def copy_then_change(source, target):
            real_copy(source, target)
            Path(source).write_bytes(b"changed during the copy")

        with patch("wps_ai_agent_cli.backups.shutil.copy2", side_effect=copy_then_change):
            ok, result, errors, _ = create_backup(self.document_id, "req-unstable:backup", workspace=self.workspace)

        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "DOCUMENT_CHANGED_DURING_BACKUP")
        self.assertIsNone(result["backup_path"])
        ok, listed, _ = list_backups(self.document_id, self.workspace)
        self.assertEqual(listed["backups"], [])

    def test_two_backups_with_the_same_timestamp_get_their_own_files(self):
        with patch("wps_ai_agent_cli.backups.datetime") as clock:
            clock.now.return_value.strftime.return_value = "20261029T050000000000Z"
            first = create_backup(self.document_id, "req-a:backup", workspace=self.workspace)
            self.document.write_bytes(self.document.read_bytes())  # same bytes, a second backup request
            second = create_backup(self.document_id, "req-b:backup", workspace=self.workspace)

        self.assertTrue(first[0], first[2])
        self.assertTrue(second[0], second[2])
        paths = {first[1]["backup_path"], second[1]["backup_path"]}
        self.assertEqual(len(paths), 2)
        self.assertTrue(second[1]["backup_path"].endswith("20261029T050000000000Z-1.xlsx"))
        ok, listed, _ = list_backups(self.document_id, self.workspace)
        self.assertEqual(len(listed["backups"]), 2)
        self.assertTrue(all(item["created_at"] for item in listed["backups"]))


if __name__ == "__main__":
    unittest.main()
