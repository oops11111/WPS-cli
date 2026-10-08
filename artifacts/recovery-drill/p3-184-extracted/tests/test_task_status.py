import tempfile
import unittest
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from threading import Event, current_thread
from unittest.mock import patch
from pathlib import Path
from wps_ai_agent_cli import task_status

from wps_ai_agent_cli.task_status import (
    build_recovery_playbook,
    create_task_status,
    get_task_status,
    list_recovery_playbooks,
    list_task_statuses,
    update_task_status,
)


class TaskStatusTests(unittest.TestCase):
    def test_cancel_waits_for_progress_transaction_and_remains_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_task_status("batch", "request", task_id="task", workspace=tmp)
            progress_read, release, cancel_started = Event(), Event(), Event()
            now = task_status._now

            def pause_progress():
                if current_thread().name.startswith("progress"):
                    progress_read.set()
                    self.assertTrue(release.wait(5))
                return now()

            def cancel():
                cancel_started.set()
                return update_task_status("task", "cancelled", workspace=tmp)

            with patch.object(task_status, "_now", side_effect=pause_progress):
                with ThreadPoolExecutor(1, thread_name_prefix="progress") as worker, ThreadPoolExecutor(1) as canceller:
                    progress = worker.submit(update_task_status, "task", "running", workspace=tmp)
                    try:
                        self.assertTrue(progress_read.wait(5))
                        cancellation = canceller.submit(cancel)
                        self.assertTrue(cancel_started.wait(5))
                        with self.assertRaises(FutureTimeoutError):
                            cancellation.result(timeout=0.15)
                    finally:
                        release.set()
                    self.assertTrue(progress.result(timeout=5)[0])
                    self.assertTrue(cancellation.result(timeout=5)[0])
            self.assertEqual(get_task_status("task", tmp)["state"], "cancelled")
            self.assertFalse(update_task_status("task", "running", workspace=tmp)[0])

    def test_concurrent_process_creation_preserves_every_record(self):
        script = """
import sys, time
from wps_ai_agent_cli import task_status as status
original = status._now
def delayed_now():
    time.sleep(0.01)
    return original()
status._now = delayed_now
for index in range(12):
    key = sys.argv[2] + '-' + str(index)
    status.create_task_status('test', key, task_id=key, workspace=sys.argv[1])
"""
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
            processes = []
            try:
                for index in range(4):
                    processes.append(subprocess.Popen([sys.executable, "-c", script, tmp, str(index)],
                                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env))
                for process in processes:
                    _, stderr = process.communicate(timeout=25)
                    self.assertEqual(process.returncode, 0, stderr.decode(errors="replace"))
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.kill()
                    process.communicate(timeout=5)
            self.assertEqual(len(list_task_statuses(tmp)), 48)

    def test_failed_atomic_replace_preserves_previous_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_task_status("test", "request", task_id="task", workspace=tmp)
            path = task_status.task_status_state_path(tmp)
            original = path.read_bytes()
            with patch.object(task_status.os, "replace", side_effect=OSError("simulated failure")):
                with self.assertRaises(OSError):
                    update_task_status("task", "running", workspace=tmp)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(path.parent.glob(".task-status-*.tmp")), [])
            self.assertTrue(update_task_status("task", "cancelled", workspace=tmp)[0])

    def test_create_update_get_and_list_task_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()

            ok, created, errors, replayed = create_task_status(
                command="convert-smoke",
                request_id="op-1",
                task_id="task-1",
                document_id="doc_1",
                message="Queued",
                recovery_guidance=["Retry after checking WPS availability."],
                workspace=workspace,
            )
            self.assertTrue(ok)
            self.assertFalse(replayed)
            self.assertEqual(errors, [])
            self.assertEqual(created["state"], "pending")
            self.assertFalse(created["terminal"])

            ok, running, errors = update_task_status(
                "task-1",
                "running",
                progress_percent=40,
                message="Opening WPS.",
                workspace=workspace,
            )
            self.assertTrue(ok)
            self.assertEqual(errors, [])
            self.assertEqual(running["state"], "running")
            self.assertEqual(running["progress_percent"], 40)
            self.assertIsNotNone(running["started_at"])

            ok, finished, errors = update_task_status(
                "task-1",
                "succeeded",
                result_ref="op-1",
                workspace=workspace,
            )
            self.assertTrue(ok)
            self.assertEqual(errors, [])
            self.assertTrue(finished["terminal"])
            self.assertEqual(finished["progress_percent"], 100)
            self.assertEqual(finished["result_ref"], "op-1")
            self.assertIsNotNone(finished["completed_at"])

            self.assertEqual(get_task_status("task-1", workspace)["state"], "succeeded")
            self.assertEqual(list_task_statuses(workspace)[0]["task_id"], "task-1")

    def test_create_task_status_replays_existing_task_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            create_task_status("sample", "op-1", task_id="task-1", workspace=workspace)

            ok, result, errors, replayed = create_task_status(
                "sample",
                "op-1",
                task_id="task-1",
                workspace=workspace,
            )

            self.assertTrue(ok)
            self.assertTrue(replayed)
            self.assertEqual(errors, [])
            self.assertEqual(result["request_id"], "op-1")

    def test_task_ownership_conflict_preserves_record(self):
        for terminal in (False, True):
            for field, value in (("command", "other"), ("request_id", "other"), ("document_id", "other")):
                with self.subTest(terminal=terminal, field=field), tempfile.TemporaryDirectory() as tmp:
                    owner = {"command": "sample", "request_id": "op-1", "document_id": "doc-1"}
                    create_task_status(**owner, task_id="task", workspace=tmp)
                    if terminal:
                        update_task_status("task", "succeeded", workspace=tmp)
                    path = task_status.task_status_state_path(tmp)
                    before = path.read_bytes()
                    owner[field] = value
                    ok, result, errors, replayed = create_task_status(**owner, task_id="task", workspace=tmp)
                    self.assertFalse(ok)
                    self.assertFalse(replayed)
                    self.assertEqual(errors[0]["code"], "TASK_ID_CONFLICT")
                    self.assertEqual(path.read_bytes(), before)

    def test_update_task_status_rejects_invalid_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            create_task_status("sample", "op-1", task_id="task-1", workspace=workspace)

            ok, result, errors = update_task_status(
                "task-1",
                "running",
                progress_percent=101,
                workspace=workspace,
            )

            self.assertFalse(ok)
            self.assertEqual(result, {})
            self.assertEqual(errors[0]["code"], "INVALID_PROGRESS")

    def test_update_task_status_rejects_terminal_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            create_task_status("sample", "op-1", task_id="task-1", workspace=workspace)
            update_task_status("task-1", "failed", workspace=workspace)

            ok, result, errors = update_task_status(
                "task-1",
                "running",
                workspace=workspace,
            )

            self.assertFalse(ok)
            self.assertEqual(result["state"], "failed")
            self.assertEqual(errors[0]["code"], "TASK_ALREADY_TERMINAL")

    def test_recovery_playbook_for_running_task_is_ambiguous(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            create_task_status(
                "spreadsheet-write",
                "op-1",
                task_id="task-1",
                document_id="doc_1",
                workspace=workspace,
            )
            update_task_status("task-1", "running", progress_percent=50, workspace=workspace)

            playbook = build_recovery_playbook("task-1", workspace=workspace)

            self.assertEqual(playbook["scenario"], "interrupted_or_running")
            self.assertFalse(playbook["safe_to_retry"])
            self.assertEqual(playbook["evidence"]["document_id"], "doc_1")
            self.assertIn("python -m wps_ai_agent_cli operation --request op-1", playbook["commands"])
            self.assertIn("python -m wps_ai_agent_cli list-backups --document-id doc_1", playbook["commands"])

    def test_recovery_playbook_for_failed_task_preserves_guidance(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            create_task_status("writer-replace", "op-1", task_id="task-1", workspace=workspace)
            update_task_status(
                "task-1",
                "failed",
                recovery_guidance=["Inspect response errors before retrying."],
                workspace=workspace,
            )

            playbook = build_recovery_playbook("task-1", workspace=workspace)

            self.assertEqual(playbook["scenario"], "failed")
            self.assertFalse(playbook["safe_to_retry"])
            self.assertEqual(
                playbook["task_recovery_guidance"],
                ["Inspect response errors before retrying."],
            )

    def test_recovery_playbook_for_missing_task_is_ambiguous(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()

            playbook = build_recovery_playbook("missing-task", workspace=workspace)

            self.assertEqual(playbook["scenario"], "ambiguous_missing_status")
            self.assertFalse(playbook["safe_to_retry"])
            self.assertFalse(playbook["evidence"]["task_status_found"])

    def test_recovery_playbooks_list_exposes_required_scenarios(self):
        scenarios = {playbook["scenario"] for playbook in list_recovery_playbooks()}

        self.assertIn("interrupted_or_running", scenarios)
        self.assertIn("failed", scenarios)
        self.assertIn("ambiguous_missing_status", scenarios)


if __name__ == "__main__":
    unittest.main()
