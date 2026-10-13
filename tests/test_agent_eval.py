from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from wps_ai_agent_cli.backups import create_backup, restore_backup
from wps_ai_agent_cli.sessions import register_document

REPO_ROOT = Path(__file__).resolve().parents[1]
TASKS_PATH = REPO_ROOT / "config" / "agent_eval_tasks.json"

_spec = importlib.util.spec_from_file_location("run_agent_eval", REPO_ROOT / "scripts" / "agent_eval" / "run_agent_eval.py")
run_agent_eval = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_agent_eval)

KNOWN_CHECK_KINDS = {"document_registered", "operation_recorded", "no_operation", "backup_count", "file_unchanged"}


def _task(task_id: str) -> dict:
    spec = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    return next(task for task in spec["tasks"] if task["id"] == task_id)


def _fake_agent(actions):
    """A stand-in for the claude CLI: it performs the given actions on the workspace, then reports ran."""
    def runner(prompt, mcp_config, workspace, model, max_turns, timeout):
        actions(workspace)
        return {"ran": True, "exit_code": 0, "result_excerpt": ""}
    return runner


def _register(workspace: Path):
    ok, record, _ = register_document("spreadsheets", str(workspace / "book.xlsx"), workspace)
    assert ok, record
    return record["document_id"]


class AgentEvalTaskFileTests(unittest.TestCase):
    def test_every_check_kind_in_the_task_file_is_known(self):
        spec = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
        kinds = {check["kind"] for task in spec["tasks"] for check in task["checks"]}
        self.assertLessEqual(kinds, KNOWN_CHECK_KINDS)
        self.assertEqual(len({task["id"] for task in spec["tasks"]}), len(spec["tasks"]))


class AgentEvalJudgeTests(unittest.TestCase):
    def test_passes_when_the_expected_state_is_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def agent(workspace):
                document_id = _register(workspace)
                ok, _result, errors, _ = create_backup(document_id, "eval-backup-1", workspace=workspace)
                assert ok, errors

            result = run_agent_eval.run_task(_task("register-and-backup"), "book.xlsx", "spreadsheets", root, None, 15, 60, runner=_fake_agent(agent))

        self.assertTrue(result["passed"], result)
        self.assertTrue(all(check["passed"] for check in result["checks"]))

    def test_fails_when_the_agent_does_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_agent_eval.run_task(_task("register-and-backup"), "book.xlsx", "spreadsheets", Path(tmp), None, 15, 60, runner=_fake_agent(lambda workspace: None))

        self.assertFalse(result["passed"])
        failed = {check["kind"] for check in result["checks"] if not check["passed"]}
        self.assertIn("document_registered", failed)
        self.assertIn("operation_recorded", failed)

    def test_a_refused_restore_leaves_no_operation_and_no_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def agent(workspace):
                document_id = _register(workspace)
                ok, _result, _errors, _ = restore_backup(document_id, "eval-restore-1", backup_name="missing.xlsx", workspace=workspace)
                assert not ok

            result = run_agent_eval.run_task(_task("restore-missing-backup"), "book.xlsx", "spreadsheets", root, None, 15, 60, runner=_fake_agent(agent))

        self.assertTrue(result["passed"], result)

    def test_a_timed_out_agent_is_a_failure_even_if_the_state_looks_right(self):
        def timeout_runner(prompt, mcp_config, workspace, model, max_turns, timeout):
            _register(workspace)
            return {"ran": False, "error": "timed out after 60s"}

        with tempfile.TemporaryDirectory() as tmp:
            result = run_agent_eval.run_task(_task("list-backups-readonly"), "book.xlsx", "spreadsheets", Path(tmp), None, 15, 60, runner=timeout_runner)

        self.assertFalse(result["passed"])

    def test_mcp_config_runs_the_server_in_the_task_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "task"
            workspace.mkdir()
            config = json.loads(run_agent_eval.write_mcp_config(workspace).read_text(encoding="utf-8"))

        server = config["mcpServers"]["wps-agent"]
        self.assertEqual(server["cwd"], str(workspace))
        self.assertEqual(server["args"], ["-m", "wps_ai_agent_cli", "mcp-server"])
        self.assertEqual(server["env"]["PYTHONPATH"], str(REPO_ROOT / "src"))


if __name__ == "__main__":
    unittest.main()
