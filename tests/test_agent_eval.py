from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wps_ai_agent_cli.backups import create_backup, list_backups, restore_backup
from wps_ai_agent_cli.operations import record_operation
from wps_ai_agent_cli.sessions import register_document, stable_document_id

REPO_ROOT = Path(__file__).resolve().parents[1]
TASKS_PATH = REPO_ROOT / "config" / "agent_eval_tasks.json"

_spec = importlib.util.spec_from_file_location(
    "run_agent_eval", REPO_ROOT / "scripts" / "agent_eval" / "run_agent_eval.py"
)
run_agent_eval = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_agent_eval)

KNOWN_CHECK_KINDS = {
    "document_registered",
    "operation_recorded",
    "no_operation",
    "backup_count",
    "file_unchanged",
    "file_matches_seed",
    "tool_called",
    "tool_not_called",
    "tool_error_seen",
    "max_tool_calls",
    "xlsx_cell",
    "file_text",
    "xlsx_sheets",
    "docx_table_cell",
    "pdf_file",
}
WPS_WRITE_TASKS = (
    "wps-spreadsheet-write",
    "wps-writer-replace",
    "wps-presentation-replace",
    "wps-held-spreadsheet-write",
    "wps-spreadsheet-rename-sheet",
    "wps-spreadsheet-create-sheet",
    "wps-writer-table-write",
    "wps-docx-to-pdf",
    "wps-open-document-export-text",
    "wps-open-writer-selection-replace",
    "wps-open-writer-selection-insert",
    "wps-open-presentation-selection-replace",
    "wps-open-save-document",
    "wps-open-writer-selection-delete",
    "wps-open-presentation-selection-insert",
    "wps-open-presentation-selection-delete",
    "wps-open-spreadsheet-selection-replace",
    "wps-open-spreadsheet-selection-delete",
    "wps-open-save-as-untitled",
)
# Every tool that writes to a document open in WPS; Phase 7 (H2) asks for an evaluation task for each.
OPEN_DOCUMENT_WRITE_TOOLS = {
    "writer_selection_replace",
    "writer_selection_insert",
    "writer_selection_delete",
    "presentation_selection_replace",
    "presentation_selection_insert",
    "presentation_selection_delete",
    "spreadsheet_selection_replace",
    "spreadsheet_selection_delete",
    "save_open_document",
    "save_as_open_document",
}
KNOWN_SETUP_STEPS = {
    "register",
    "backup",
    "modify",
    "html_table",
    "hold",
    "open_in_wps",
    "select_text",
    "append_unsaved",
    "untitled_document",
}
# Setup steps that leave the fixture held or open for the agent. Only steps that work on the open document
# may follow open_in_wps; nothing may follow hold.
FINAL_SETUP_STEPS = {"hold", "open_in_wps"}
OPEN_DOCUMENT_STEPS = {"select_text", "append_unsaved", "untitled_document"}


def _task(task_id: str) -> dict:
    spec = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    return next(task for task in spec["tasks"] if task["id"] == task_id)


def _fake_agent(actions, tool_calls=None):
    """A stand-in for the claude CLI: it performs the given actions on the workspace, then reports ran."""

    def runner(prompt, mcp_config, workspace, model, max_turns, timeout):
        actions(workspace)
        return {"ran": True, "exit_code": 0, "result_excerpt": "", "tool_calls": tool_calls or []}

    return runner


def _call(tool, error_codes=(), **arguments):
    return {
        "name": f"mcp__wps-agent__wps_agent_{tool}",
        "input": arguments,
        "is_error": bool(error_codes),
        "error_codes": list(error_codes),
    }


def _document_id(workspace: Path) -> str:
    return stable_document_id("spreadsheets", str(workspace / "book.xlsx"))


def _latest_backup(workspace: Path) -> str:
    ok, data, errors = list_backups(_document_id(workspace), workspace)
    assert ok, errors
    return data["backups"][0]["backup_name"]


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

    def test_every_task_names_real_expected_tools_that_cover_its_tool_checks(self):
        from wps_ai_agent_cli.mcp_schema import list_mcp_tool_schemas

        tools = {schema["name"].removeprefix("wps_agent_") for schema in list_mcp_tool_schemas()}
        spec = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
        for task in spec["tasks"]:
            with self.subTest(task=task["id"]):
                expected = task.get("expected_tools")
                self.assertTrue(expected, "every task lists the tools a correct run needs")
                self.assertLessEqual(set(expected), tools)
                for check in task["checks"]:
                    if check["kind"] == "tool_called":
                        self.assertIn(check["tool"], expected)
                    if check["kind"] == "tool_not_called":
                        self.assertNotIn(check["tool"], expected)

    def test_wps_write_tasks_require_wps_and_name_a_supported_fixture(self):
        spec = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
        tasks = {task["id"]: task for task in spec["tasks"]}
        for task_id in WPS_WRITE_TASKS:
            task = tasks[task_id]
            self.assertTrue(task.get("requires_wps"), task_id)
            fixture = task.get("fixture", spec["fixture"])
            self.assertIn(Path(fixture).suffix, {".xlsx", ".docx", ".pptx"}, task_id)
            self.assertIn(task.get("component", spec["component"]), {"spreadsheets", "writer", "presentation"}, task_id)

    def test_every_open_document_write_tool_has_a_wps_task_that_must_call_it(self):
        spec = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
        covered = {
            check["tool"]
            for task in spec["tasks"]
            if task.get("requires_wps") and "open_in_wps" in task.get("setup", [])
            for check in task["checks"]
            if check["kind"] == "tool_called"
        }
        self.assertLessEqual(OPEN_DOCUMENT_WRITE_TOOLS, covered)

    def test_docx_and_pptx_fixtures_hold_the_text_the_tasks_replace(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("report.docx", "deck.pptx"):
                run_agent_eval.write_fixture(Path(tmp), name)
                text = run_agent_eval.document_text(Path(tmp) / name)
                self.assertIn("Status: DRAFT", text, name)

    def test_setup_steps_are_known_and_hold_comes_last(self):
        spec = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
        for task in spec["tasks"]:
            steps = task.get("setup", [])
            self.assertLessEqual(set(steps), KNOWN_SETUP_STEPS, task["id"])
            final = [step for step in steps if step in FINAL_SETUP_STEPS]
            self.assertLessEqual(len(final), 1, task["id"])
            if final:
                after = steps[steps.index(final[0]) + 1 :]
                allowed = OPEN_DOCUMENT_STEPS if final[0] == "open_in_wps" else set()
                self.assertLessEqual(set(after), allowed, task["id"])
            if "open_in_wps" in steps:
                self.assertTrue(task.get("requires_wps"), task["id"])
            if "select_text" in steps:
                self.assertIn("open_in_wps", steps, task["id"])
                # Spreadsheets select a cell range; Writer and Presentation select text (P7-003).
                key = "range" if task.get("component", spec["component"]) == "spreadsheets" else "text"
                self.assertTrue(task.get("selection", {}).get(key), task["id"])
            if "untitled_document" in steps:
                self.assertIn("open_in_wps", steps, task["id"])
                self.assertIn("{untitled_name}", task["prompt"], task["id"])
            if "append_unsaved" in steps:
                self.assertIn("open_in_wps", steps, task["id"])
                self.assertTrue(task.get("unsaved_text"), task["id"])

    def test_the_selected_text_is_in_the_fixture(self):
        spec = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            for task in spec["tasks"]:
                if "text" not in task.get("selection", {}):
                    continue
                with self.subTest(task=task["id"]):
                    run_agent_eval.write_fixture(Path(tmp), task["fixture"])
                    self.assertIn(task["selection"]["text"], run_agent_eval.document_text(Path(tmp) / task["fixture"]))

    def test_the_status_workbook_holds_the_table_on_its_own_sheet(self):
        from openpyxl import load_workbook

        with tempfile.TemporaryDirectory() as tmp:
            run_agent_eval.write_fixture(Path(tmp), "status.xlsx")
            workbook = load_workbook(Path(tmp) / "status.xlsx")
            sheet = workbook["Status"]
            rows = [list(row) for row in sheet.iter_rows(values_only=True)]
            workbook.close()
        self.assertEqual(rows, [["Region", "Q1", "Status"], ["North", 120, "DRAFT"], ["South", 95, "DRAFT"]])

    def test_the_table_fixture_holds_the_table_the_task_edits(self):
        from docx import Document

        with tempfile.TemporaryDirectory() as tmp:
            run_agent_eval.write_fixture(Path(tmp), "table_report.docx")
            table = Document(Path(tmp) / "table_report.docx").tables[0]
            rows = [[cell.text for cell in row.cells] for row in table.rows]
        self.assertEqual(rows, [list(row) for row in run_agent_eval.WRITER_TABLE_ROWS])
        self.assertEqual(rows[1], ["North", "120", "DRAFT"])


class TranscriptTests(unittest.TestCase):
    def test_tool_calls_and_error_codes_are_read_from_stream_json(self):
        envelope = json.dumps({"ok": False, "errors": [{"code": "DOCUMENT_HELD_OPEN", "message": "held"}]})
        lines = [
            json.dumps({"type": "system", "subtype": "init"}),
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {"type": "tool_use", "id": "t1", "name": "ToolSearch", "input": {"query": "select:x"}},
                        ]
                    },
                }
            ),
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "id": "t2",
                                "name": "mcp__wps-agent__wps_agent_backup_document",
                                "input": {"request_id": "r1"},
                            },
                        ]
                    },
                }
            ),
            json.dumps(
                {
                    "type": "user",
                    "message": {
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": "t2",
                                "content": [{"type": "text", "text": envelope}],
                            },
                        ]
                    },
                }
            ),
            "not json",
            json.dumps({"type": "result", "num_turns": 3, "total_cost_usd": 0.05, "result": "done"}),
        ]
        result, calls = run_agent_eval.parse_transcript(lines)

        self.assertEqual(result["num_turns"], 3)
        self.assertEqual([call["name"] for call in calls], ["ToolSearch", "mcp__wps-agent__wps_agent_backup_document"])
        self.assertEqual(calls[1]["error_codes"], ["DOCUMENT_HELD_OPEN"])
        self.assertTrue(calls[1]["is_error"])
        metrics = run_agent_eval.tool_metrics(calls)
        self.assertEqual(
            (metrics["wps_tool_calls"], metrics["wps_tool_errors"], metrics["other_tool_calls"]), (1, 1, 1)
        )
        self.assertEqual(metrics["tools_used"], ["backup_document"])


class AgentEvalJudgeTests(unittest.TestCase):
    def test_passes_when_the_expected_state_is_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def agent(workspace):
                document_id = _register(workspace)
                ok, _result, errors, _ = create_backup(document_id, "eval-backup-1", workspace=workspace)
                assert ok, errors

            result = run_agent_eval.run_task(
                _task("register-and-backup"), "book.xlsx", "spreadsheets", root, None, 15, 60, runner=_fake_agent(agent)
            )

        self.assertTrue(result["passed"], result)
        self.assertTrue(all(check["passed"] for check in result["checks"]))

    def test_fails_when_the_agent_does_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_agent_eval.run_task(
                _task("register-and-backup"),
                "book.xlsx",
                "spreadsheets",
                Path(tmp),
                None,
                15,
                60,
                runner=_fake_agent(lambda workspace: None),
            )

        self.assertFalse(result["passed"])
        failed = {check["kind"] for check in result["checks"] if not check["passed"]}
        self.assertIn("document_registered", failed)
        self.assertIn("operation_recorded", failed)

    def test_a_refused_restore_leaves_no_operation_and_no_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def agent(workspace):
                document_id = _register(workspace)
                ok, _result, _errors, _ = restore_backup(
                    document_id, "eval-restore-1", backup_name="missing.xlsx", workspace=workspace
                )
                assert not ok

            result = run_agent_eval.run_task(
                _task("restore-missing-backup"),
                "book.xlsx",
                "spreadsheets",
                root,
                None,
                15,
                60,
                runner=_fake_agent(agent),
            )

        self.assertTrue(result["passed"], result)

    def test_a_timed_out_agent_is_a_failure_even_if_the_state_looks_right(self):
        def timeout_runner(prompt, mcp_config, workspace, model, max_turns, timeout):
            _register(workspace)
            return {"ran": False, "error": "timed out after 60s"}

        with tempfile.TemporaryDirectory() as tmp:
            result = run_agent_eval.run_task(
                _task("list-backups-readonly"),
                "book.xlsx",
                "spreadsheets",
                Path(tmp),
                None,
                15,
                60,
                runner=timeout_runner,
            )

        self.assertFalse(result["passed"])

    def test_a_retried_backup_with_the_same_request_id_makes_one_backup(self):
        with tempfile.TemporaryDirectory() as tmp:

            def agent(workspace):
                document_id = _register(workspace)
                for _ in range(2):
                    ok, _result, errors, _ = create_backup(document_id, "eval-retry-1", workspace=workspace)
                    assert ok, errors

            calls = [_call("backup_document", request_id="eval-retry-1", document_id="d")] * 2
            result = run_agent_eval.run_task(
                _task("idempotent-backup-retry"),
                "book.xlsx",
                "spreadsheets",
                Path(tmp),
                None,
                15,
                60,
                runner=_fake_agent(agent, calls),
            )

        self.assertTrue(result["passed"], result)

    def test_a_single_backup_call_fails_the_retry_task(self):
        with tempfile.TemporaryDirectory() as tmp:

            def agent(workspace):
                create_backup(_register(workspace), "eval-retry-1", workspace=workspace)

            calls = [_call("backup_document", request_id="eval-retry-1")]
            result = run_agent_eval.run_task(
                _task("idempotent-backup-retry"),
                "book.xlsx",
                "spreadsheets",
                Path(tmp),
                None,
                15,
                60,
                runner=_fake_agent(agent, calls),
            )

        self.assertFalse(result["passed"])
        self.assertEqual([check["kind"] for check in result["checks"] if not check["passed"]], ["tool_called"])

    def test_restoring_the_latest_backup_brings_back_the_seed(self):
        with tempfile.TemporaryDirectory() as tmp:

            def agent(workspace):
                ok, _result, errors, _ = restore_backup(
                    _document_id(workspace),
                    "eval-restore-2",
                    backup_name=_latest_backup(workspace),
                    workspace=workspace,
                )
                assert ok, errors

            calls = [_call("list_backups"), _call("restore_backup", request_id="eval-restore-2")]
            result = run_agent_eval.run_task(
                _task("restore-latest-backup"),
                "book.xlsx",
                "spreadsheets",
                Path(tmp),
                None,
                15,
                60,
                runner=_fake_agent(agent, calls),
            )

        self.assertTrue(result["passed"], result)

    def test_the_restore_task_fails_when_the_mistaken_change_is_left_in_place(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_agent_eval.run_task(
                _task("restore-latest-backup"),
                "book.xlsx",
                "spreadsheets",
                Path(tmp),
                None,
                15,
                60,
                runner=_fake_agent(lambda workspace: None),
            )

        failed = {check["kind"] for check in result["checks"] if not check["passed"]}
        self.assertEqual(failed, {"operation_recorded", "file_matches_seed"})

    def test_too_many_tool_calls_fail_the_restore_task(self):
        with tempfile.TemporaryDirectory() as tmp:

            def agent(workspace):
                restore_backup(
                    _document_id(workspace),
                    "eval-restore-2",
                    backup_name=_latest_backup(workspace),
                    workspace=workspace,
                )

            calls = [_call("documents")] * 6 + [_call("restore_backup", request_id="eval-restore-2")]
            result = run_agent_eval.run_task(
                _task("restore-latest-backup"),
                "book.xlsx",
                "spreadsheets",
                Path(tmp),
                None,
                15,
                60,
                runner=_fake_agent(agent, calls),
            )

        self.assertEqual([check["kind"] for check in result["checks"] if not check["passed"]], ["max_tool_calls"])

    def test_dry_run_passes_and_a_real_restore_fails_the_preview_task(self):
        with tempfile.TemporaryDirectory() as tmp:

            def preview(workspace):
                ok, _result, errors, _ = restore_backup(
                    _document_id(workspace),
                    "p1",
                    backup_name=_latest_backup(workspace),
                    dry_run=True,
                    workspace=workspace,
                )
                assert ok, errors

            dry = run_agent_eval.run_task(
                _task("restore-dry-run"),
                "book.xlsx",
                "spreadsheets",
                Path(tmp) / "a",
                None,
                15,
                60,
                runner=_fake_agent(preview, [_call("restore_backup", dry_run=True)]),
            )

            def restore(workspace):
                restore_backup(
                    _document_id(workspace), "p2", backup_name=_latest_backup(workspace), workspace=workspace
                )

            real = run_agent_eval.run_task(
                _task("restore-dry-run"),
                "book.xlsx",
                "spreadsheets",
                Path(tmp) / "b",
                None,
                15,
                60,
                runner=_fake_agent(restore, [_call("restore_backup")]),
            )

        self.assertTrue(dry["passed"], dry)
        # A real restore also takes a safety backup of the current file, so the backup count changes too.
        self.assertEqual(
            {check["kind"] for check in real["checks"] if not check["passed"]},
            {"tool_called", "file_unchanged", "backup_count"},
        )

    def test_held_document_task_is_skipped_when_the_file_cannot_be_held(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(run_agent_eval, "hold_file", return_value=(None, "cannot hold here")),
        ):
            result = run_agent_eval.run_task(
                _task("held-document-backup"),
                "book.xlsx",
                "spreadsheets",
                Path(tmp),
                None,
                15,
                60,
                runner=_fake_agent(lambda workspace: self.fail("agent must not run")),
            )

        self.assertEqual(result["skipped"], "cannot hold here")
        self.assertFalse(result["passed"])

    def test_held_document_task_passes_on_a_reported_refusal_and_releases_the_hold(self):
        released = []
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(run_agent_eval, "hold_file", return_value=(lambda: released.append(True), None)),
        ):
            calls = [_call("backup_document", error_codes=["DOCUMENT_HELD_OPEN"], request_id="eval-held-1")]
            result = run_agent_eval.run_task(
                _task("held-document-backup"),
                "book.xlsx",
                "spreadsheets",
                Path(tmp),
                None,
                15,
                60,
                runner=_fake_agent(lambda workspace: None, calls),
            )

        self.assertTrue(result["passed"], result)
        self.assertEqual(released, [True])

    def test_held_document_task_fails_when_the_refusal_was_never_seen(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(run_agent_eval, "hold_file", return_value=(lambda: None, None)),
        ):
            result = run_agent_eval.run_task(
                _task("held-document-backup"),
                "book.xlsx",
                "spreadsheets",
                Path(tmp),
                None,
                15,
                60,
                runner=_fake_agent(lambda workspace: None, [_call("restore_backup")]),
            )

        self.assertEqual(
            {check["kind"] for check in result["checks"] if not check["passed"]}, {"tool_error_seen", "tool_not_called"}
        )

    @unittest.skipIf(os.name == "nt" or os.geteuid() == 0, "chmod hold needs a non-root POSIX user")
    def test_chmod_hold_makes_the_file_unreadable_until_released(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "book.xlsx"
            path.write_bytes(b"x")
            release, reason = run_agent_eval.hold_file(path)
            self.assertIsNone(reason)
            with self.assertRaises(PermissionError):
                path.read_bytes()
            release()
            self.assertEqual(path.read_bytes(), b"x")

    def test_html_table_conversion_is_judged_from_the_output_workbook(self):
        from wps_ai_agent_cli.html_office import convert_html_to_office

        with tempfile.TemporaryDirectory() as tmp:

            def agent(workspace):
                convert_html_to_office(workspace / "table.html", workspace / "table.xlsx", "xlsx")

            result = run_agent_eval.run_task(
                _task("html-table-to-xlsx"),
                "book.xlsx",
                "spreadsheets",
                Path(tmp),
                None,
                15,
                60,
                runner=_fake_agent(agent, [_call("html_editable", format="xlsx")]),
            )
            missing = run_agent_eval.run_task(
                _task("html-table-to-xlsx"),
                "book.xlsx",
                "spreadsheets",
                Path(tmp) / "none",
                None,
                15,
                60,
                runner=_fake_agent(lambda workspace: None),
            )

        self.assertTrue(result["passed"], result)
        self.assertEqual(
            [check["detail"] for check in missing["checks"] if check["kind"] == "xlsx_cell"], ["output missing"] * 2
        )

    def test_off_path_calls_are_counted_against_the_expected_tools(self):
        calls = [
            _call("register_document"),
            _call("documents"),
            _call("backup_document"),
            _call("documents"),
            {"name": "ToolSearch", "input": {}, "is_error": False, "error_codes": []},
        ]

        metrics = run_agent_eval.tool_metrics(calls, ["register_document", "backup_document"])

        self.assertEqual(metrics["wps_tool_calls"], 4)
        self.assertEqual(metrics["other_tool_calls"], 1)
        self.assertEqual(metrics["off_path_calls"], 2)
        self.assertEqual(metrics["off_path_tools"], ["documents"])
        self.assertEqual(metrics["expected_tools"], ["backup_document", "register_document"])

    def test_without_expected_tools_off_path_calls_are_not_counted(self):
        metrics = run_agent_eval.tool_metrics([_call("documents")])

        self.assertIsNone(metrics["off_path_calls"])
        self.assertIsNone(metrics["off_path_tools"])

    def test_off_path_calls_are_reported_but_do_not_fail_a_task(self):
        def agent(workspace):
            document_id = _register(workspace)
            create_backup(document_id, "eval-backup-1", workspace=workspace)

        calls = [_call("register_document"), _call("operations"), _call("backup_document", request_id="eval-backup-1")]
        with tempfile.TemporaryDirectory() as tmp:
            result = run_agent_eval.run_task_repeated(
                _task("register-and-backup"),
                "book.xlsx",
                "spreadsheets",
                Path(tmp),
                None,
                15,
                60,
                repeat=2,
                min_passes=2,
                runner=_fake_agent(agent, calls),
            )
        summary = run_agent_eval.summarize([result], "stamp", None)

        self.assertTrue(result["passed"])
        self.assertEqual([run["metrics"]["off_path_calls"] for run in result["runs"]], [1, 1])
        self.assertEqual(result["metrics"]["off_path_calls"], 2)
        self.assertEqual(result["metrics"]["off_path_tools"], ["operations"])
        self.assertEqual(summary["off_path_calls"], 2)
        self.assertEqual(summary["tasks_without_expected_tools"], [])

    def test_summary_counts_skipped_tasks_separately(self):
        results = [
            {"id": "a", "passed": True, "metrics": {"wps_tool_calls": 2, "wps_tool_errors": 0}},
            {"id": "b", "passed": False, "metrics": {"wps_tool_calls": 3, "wps_tool_errors": 1}},
            {"id": "c", "passed": False, "skipped": "cannot hold here"},
        ]
        summary = run_agent_eval.summarize(results, "stamp", None)

        self.assertEqual((summary["passed"], summary["total"], summary["skipped"]), (1, 2, 1))
        self.assertEqual((summary["wps_tool_calls"], summary["wps_tool_errors"]), (5, 1))

    def test_a_wps_task_is_skipped_without_wps_and_the_agent_never_runs(self):
        task = {**_task("register-and-backup"), "requires_wps": True}
        with tempfile.TemporaryDirectory() as tmp:
            result = run_agent_eval.run_task(
                task,
                "book.xlsx",
                "spreadsheets",
                Path(tmp),
                None,
                15,
                60,
                runner=_fake_agent(lambda workspace: self.fail("agent must not run")),
                has_wps=lambda component: False,
            )

        self.assertIn("needs WPS spreadsheets", result["skipped"])
        self.assertFalse(result["passed"])

    def test_a_wps_task_runs_when_wps_is_available(self):
        task = {**_task("register-and-backup"), "requires_wps": True}
        seen = []
        with tempfile.TemporaryDirectory() as tmp:

            def agent(workspace):
                document_id = _register(workspace)
                create_backup(document_id, "eval-backup-1", workspace=workspace)

            result = run_agent_eval.run_task(
                task,
                "book.xlsx",
                "spreadsheets",
                Path(tmp),
                None,
                15,
                60,
                runner=_fake_agent(agent),
                has_wps=lambda component: seen.append(component) or True,
            )

        self.assertEqual(seen, ["spreadsheets"])
        self.assertTrue(result["passed"], result)

    def test_a_task_without_requires_wps_never_probes(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_agent_eval.run_task(
                _task("list-backups-readonly"),
                "book.xlsx",
                "spreadsheets",
                Path(tmp),
                None,
                15,
                60,
                runner=_fake_agent(lambda workspace: None),
                has_wps=lambda component: self.fail("must not probe"),
            )

    def test_repeated_runs_use_separate_workspaces_and_count_passes(self):
        workspaces = []
        outcomes = iter([True, False, True])

        def agent(workspace):
            workspaces.append(workspace)
            if next(outcomes):
                document_id = _register(workspace)
                create_backup(document_id, "eval-backup-1", workspace=workspace)

        with tempfile.TemporaryDirectory() as tmp:
            result = run_agent_eval.run_task_repeated(
                _task("register-and-backup"),
                "book.xlsx",
                "spreadsheets",
                Path(tmp),
                None,
                15,
                60,
                repeat=3,
                min_passes=2,
                runner=_fake_agent(agent),
            )

        self.assertEqual(len(set(workspaces)), 3)
        self.assertEqual((result["passes"], result["repeat"], result["min_passes"]), (2, 3, 2))
        self.assertAlmostEqual(result["pass_rate"], 2 / 3)
        self.assertTrue(result["passed"])
        self.assertEqual([run["passed"] for run in result["runs"]], [True, False, True])

    def test_too_few_passes_fail_the_repeated_task(self):
        outcomes = iter([True, False, False])

        def agent(workspace):
            if next(outcomes):
                create_backup(_register(workspace), "eval-backup-1", workspace=workspace)

        with tempfile.TemporaryDirectory() as tmp:
            result = run_agent_eval.run_task_repeated(
                _task("register-and-backup"),
                "book.xlsx",
                "spreadsheets",
                Path(tmp),
                None,
                15,
                60,
                repeat=3,
                min_passes=2,
                runner=_fake_agent(agent),
            )

        self.assertEqual(result["passes"], 1)
        self.assertFalse(result["passed"])

    def test_a_skip_ends_the_repeated_task_after_one_attempt(self):
        task = {**_task("register-and-backup"), "requires_wps": True}
        probes = []
        with tempfile.TemporaryDirectory() as tmp:
            result = run_agent_eval.run_task_repeated(
                task,
                "book.xlsx",
                "spreadsheets",
                Path(tmp),
                None,
                15,
                60,
                repeat=3,
                min_passes=2,
                runner=_fake_agent(lambda workspace: self.fail("agent must not run")),
                has_wps=lambda component: probes.append(component) or False,
            )

        self.assertEqual(len(probes), 1)
        self.assertIn("skipped", result)
        summary = run_agent_eval.summarize([result], "stamp", None)
        self.assertEqual((summary["total"], summary["skipped"]), (0, 1))

    def test_a_setup_that_fails_on_a_later_run_is_a_failed_run_and_keeps_the_earlier_ones(self):
        # On Windows, a WPS Writer from run 1 can stay registered and hide the document run 2 opens (P5-006).
        reasons = iter([None, "WPS did not list report.docx as open within 45 s", None])
        released = []

        def setup(steps, workspace, fixture, component, options=None, state=None):
            reason = next(reasons)
            sha = run_agent_eval.file_sha256(fixture)
            if reason:
                return sha, None, reason
            return sha, (lambda: released.append(workspace)), None

        def agent(workspace):
            create_backup(_register(workspace), "eval-backup-1", workspace=workspace)

        with tempfile.TemporaryDirectory() as tmp, patch.object(run_agent_eval, "run_setup", side_effect=setup):
            result = run_agent_eval.run_task_repeated(
                _task("register-and-backup"),
                "book.xlsx",
                "spreadsheets",
                Path(tmp),
                None,
                15,
                60,
                repeat=3,
                min_passes=2,
                runner=_fake_agent(agent),
            )

        self.assertNotIn("skipped", result)
        self.assertEqual([run["passed"] for run in result["runs"]], [True, False, True])
        self.assertIn("did not list", result["runs"][1]["setup_failed"])
        self.assertEqual(result["runs"][1]["metrics"]["wps_tool_calls"], 0)
        self.assertEqual((result["passes"], result["passed"]), (2, True))
        self.assertEqual(len(released), 2)
        summary = run_agent_eval.summarize([result], "stamp", None)
        self.assertEqual((summary["passed"], summary["total"], summary["skipped"]), (1, 1, 0))

    def test_repeat_options_are_validated(self):
        for argv in (["--repeat", "0"], ["--repeat", "2", "--min-passes", "3"], ["--min-passes", "0"]):
            with self.subTest(argv=argv), self.assertRaises(SystemExit) as raised:
                run_agent_eval.main(argv)
            self.assertEqual(raised.exception.code, 2)

    def run_wps_task(self, task_id, root, actions, calls):
        task = _task(task_id)
        fixture = task.get("fixture", "book.xlsx")
        component = task.get("component", "spreadsheets")
        return run_agent_eval.run_task(
            task,
            fixture,
            component,
            root,
            None,
            15,
            60,
            runner=_fake_agent(actions, calls),
            has_wps=lambda component: True,
        )

    @staticmethod
    def simulate_write(workspace, component, fixture, request_id, command, edit):
        """What a successful WPS write leaves behind: a backup, the edited file and an operation record."""
        ok, record, errors = register_document(component, str(workspace / fixture), workspace)
        assert ok, errors
        document_id = record["document_id"]
        ok, _result, errors, _ = create_backup(document_id, f"{request_id}:backup", workspace=workspace)
        assert ok, errors
        edit(workspace / fixture)
        record_operation(request_id, command, {"document_id": document_id}, workspace)

    @staticmethod
    def replace_in_docx(path, old, new):
        from docx import Document

        document = Document(path)
        for paragraph in document.paragraphs:
            if old in paragraph.text:
                paragraph.text = paragraph.text.replace(old, new)
        document.save(path)

    @staticmethod
    def replace_in_pptx(path, old, new):
        from pptx import Presentation

        presentation = Presentation(path)
        for slide in presentation.slides:
            for shape in slide.shapes:
                if shape.has_text_frame and old in shape.text_frame.text:
                    shape.text_frame.text = shape.text_frame.text.replace(old, new)
        presentation.save(path)

    def test_wps_spreadsheet_write_passes_when_b2_is_written_after_a_backup(self):
        from openpyxl import load_workbook

        def edit(path):
            workbook = load_workbook(path)
            workbook.active["B2"] = 42
            workbook.save(path)

        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_wps_task(
                "wps-spreadsheet-write",
                Path(tmp),
                lambda ws: self.simulate_write(
                    ws, "spreadsheets", "book.xlsx", "eval-write-1", "spreadsheet-write", edit
                ),
                [_call("spreadsheet_write", request_id="eval-write-1", range="B2", values_json="[[42]]")],
            )
        self.assertTrue(result["passed"], result)

    def test_wps_spreadsheet_write_fails_when_a1_is_overwritten(self):
        from openpyxl import load_workbook

        def edit(path):
            workbook = load_workbook(path)
            workbook.active["A1"] = 42
            workbook.save(path)

        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_wps_task(
                "wps-spreadsheet-write",
                Path(tmp),
                lambda ws: self.simulate_write(
                    ws, "spreadsheets", "book.xlsx", "eval-write-1", "spreadsheet-write", edit
                ),
                [_call("spreadsheet_write", request_id="eval-write-1")],
            )
        failed = [(check["kind"], check.get("cell")) for check in result["checks"] if not check["passed"]]
        self.assertEqual(failed, [("xlsx_cell", "B2"), ("xlsx_cell", "A1")])

    def run_open_task(self, task_id, root, actions, calls):
        """Run a task whose setup opens the fixture in WPS, with the WPS steps stood in for."""
        released = []
        with (
            patch.object(run_agent_eval, "open_in_wps", return_value=(lambda: released.append(task_id), None)),
            patch.object(run_agent_eval, "prepare_open_document", return_value=None) as prepared,
        ):
            result = self.run_wps_task(task_id, root, actions, calls)
        self.assertEqual(released, [task_id])
        self.assertEqual(prepared.call_count, 1)
        return result

    def test_open_writer_selection_replace_passes_and_keeps_the_other_paragraphs(self):
        calls = [
            _call("open_documents"),
            _call("writer_selection_replace", request_id="eval-selection-1", text="FINAL"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            passed = self.run_open_task(
                "wps-open-writer-selection-replace",
                Path(tmp),
                lambda ws: self.simulate_write(
                    ws,
                    "writer",
                    "report.docx",
                    "eval-selection-1",
                    "writer-selection-replace",
                    lambda path: self.replace_in_docx(path, "DRAFT", "FINAL"),
                ),
                calls,
            )
            file_based = self.run_open_task(
                "wps-open-writer-selection-replace",
                Path(tmp) / "b",
                lambda ws: self.simulate_write(
                    ws,
                    "writer",
                    "report.docx",
                    "eval-selection-1",
                    "writer-selection-replace",
                    lambda path: self.replace_in_docx(path, "DRAFT", "FINAL"),
                ),
                [*calls, _call("writer_replace", request_id="other")],
            )
        self.assertTrue(passed["passed"], passed)
        self.assertEqual([c["kind"] for c in file_based["checks"] if not c["passed"]], ["tool_not_called"])

    def test_open_writer_selection_insert_needs_the_text_right_after_the_owner_line(self):
        calls = [_call("writer_selection_insert", request_id="eval-insert-1", text=" (reviewed)")]

        def insert(text):
            return lambda ws: self.simulate_write(
                ws,
                "writer",
                "report.docx",
                "eval-insert-1",
                "writer-selection-insert",
                lambda path: self.replace_in_docx(path, "Owner: Finance", text),
            )

        with tempfile.TemporaryDirectory() as tmp:
            passed = self.run_open_task(
                "wps-open-writer-selection-insert", Path(tmp), insert("Owner: Finance (reviewed)"), calls
            )
            no_space = self.run_open_task(
                "wps-open-writer-selection-insert", Path(tmp) / "b", insert("Owner: Finance(reviewed)"), calls
            )
        self.assertTrue(passed["passed"], passed)
        self.assertEqual([c["kind"] for c in no_space["checks"] if not c["passed"]], ["file_text"])

    def test_open_presentation_selection_replace_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_open_task(
                "wps-open-presentation-selection-replace",
                Path(tmp),
                lambda ws: self.simulate_write(
                    ws,
                    "presentation",
                    "deck.pptx",
                    "eval-slide-selection-1",
                    "presentation-selection-replace",
                    lambda path: self.replace_in_pptx(path, "DRAFT", "FINAL"),
                ),
                [_call("presentation_selection_replace", request_id="eval-slide-selection-1", text="FINAL")],
            )
        self.assertTrue(result["passed"], result)

    def test_open_save_document_passes_only_when_the_unsaved_text_reaches_the_file(self):
        from docx import Document

        def append(path):
            document = Document(path)
            document.add_paragraph("Reviewed in WPS")
            document.save(path)

        calls = [_call("save_open_document", request_id="eval-save-1")]
        with tempfile.TemporaryDirectory() as tmp:
            saved = self.run_open_task(
                "wps-open-save-document",
                Path(tmp),
                lambda ws: self.simulate_write(
                    ws, "writer", "report.docx", "eval-save-1", "save-open-document", append
                ),
                calls,
            )
            not_saved = self.run_open_task(
                "wps-open-save-document",
                Path(tmp) / "b",
                lambda ws: self.simulate_write(
                    ws, "writer", "report.docx", "eval-save-1", "save-open-document", lambda path: None
                ),
                calls,
            )
        self.assertTrue(saved["passed"], saved)
        self.assertEqual([c["kind"] for c in not_saved["checks"] if not c["passed"]], ["file_text"])

    @staticmethod
    def set_cells(path, values):
        from openpyxl import load_workbook

        workbook = load_workbook(path)
        for cell, value in values.items():
            workbook["Status"][cell] = value
        workbook.save(path)

    def run_open_write(self, task_id, root, component, fixture, request_id, command, edit, calls):
        return self.run_open_task(
            task_id,
            root,
            lambda ws: self.simulate_write(ws, component, fixture, request_id, command, edit),
            calls,
        )

    def test_open_writer_selection_delete_needs_draft_gone_and_the_rest_kept(self):
        task = "wps-open-writer-selection-delete"
        calls = [_call("writer_selection_delete", request_id="eval-delete-1")]
        args = ("writer", "report.docx", "eval-delete-1", "writer-selection-delete")
        with tempfile.TemporaryDirectory() as tmp:
            passed = self.run_open_write(
                task, Path(tmp), *args, lambda path: self.replace_in_docx(path, "DRAFT", ""), calls
            )
            left = self.run_open_write(task, Path(tmp) / "b", *args, lambda path: None, calls)
            too_much = self.run_open_write(
                task, Path(tmp) / "c", *args, lambda path: self.replace_in_docx(path, "Status: DRAFT", ""), calls
            )
        self.assertTrue(passed["passed"], passed)
        self.assertEqual([c["kind"] for c in left["checks"] if not c["passed"]], ["file_text"])
        self.assertEqual([c["kind"] for c in too_much["checks"] if not c["passed"]], ["file_text"])

    def test_open_presentation_selection_insert_needs_the_text_right_after_draft(self):
        task = "wps-open-presentation-selection-insert"
        calls = [_call("presentation_selection_insert", request_id="eval-slide-insert-1", text=" (v2)")]
        args = ("presentation", "deck.pptx", "eval-slide-insert-1", "presentation-selection-insert")
        with tempfile.TemporaryDirectory() as tmp:
            passed = self.run_open_write(
                task,
                Path(tmp),
                *args,
                lambda path: self.replace_in_pptx(path, "Status: DRAFT", "Status: DRAFT (v2)"),
                calls,
            )
            no_space = self.run_open_write(
                task,
                Path(tmp) / "b",
                *args,
                lambda path: self.replace_in_pptx(path, "Status: DRAFT", "Status: DRAFT(v2)"),
                calls,
            )
        self.assertTrue(passed["passed"], passed)
        self.assertEqual([c["kind"] for c in no_space["checks"] if not c["passed"]], ["file_text"])

    def test_open_presentation_selection_delete_must_not_use_the_file_based_replace(self):
        task = "wps-open-presentation-selection-delete"
        calls = [_call("presentation_selection_delete", request_id="eval-slide-delete-1")]
        args = ("presentation", "deck.pptx", "eval-slide-delete-1", "presentation-selection-delete")
        with tempfile.TemporaryDirectory() as tmp:
            passed = self.run_open_write(
                task, Path(tmp), *args, lambda path: self.replace_in_pptx(path, "DRAFT", ""), calls
            )
            file_based = self.run_open_write(
                task,
                Path(tmp) / "b",
                *args,
                lambda path: self.replace_in_pptx(path, "DRAFT", ""),
                [*calls, _call("presentation_replace", request_id="other")],
            )
        self.assertTrue(passed["passed"], passed)
        self.assertEqual([c["kind"] for c in file_based["checks"] if not c["passed"]], ["tool_not_called"])

    def test_open_spreadsheet_selection_replace_needs_both_cells_and_nothing_else(self):
        task = "wps-open-spreadsheet-selection-replace"
        calls = [_call("spreadsheet_selection_replace", request_id="eval-cells-1", text="FINAL")]
        args = ("spreadsheets", "status.xlsx", "eval-cells-1", "spreadsheet-selection-replace")
        with tempfile.TemporaryDirectory() as tmp:
            passed = self.run_open_write(
                task, Path(tmp), *args, lambda path: self.set_cells(path, {"C2": "FINAL", "C3": "FINAL"}), calls
            )
            one_cell = self.run_open_write(
                task, Path(tmp) / "b", *args, lambda path: self.set_cells(path, {"C2": "FINAL"}), calls
            )
            spilled = self.run_open_write(
                task,
                Path(tmp) / "c",
                *args,
                lambda path: self.set_cells(path, {"B2": "FINAL", "C2": "FINAL", "C3": "FINAL"}),
                calls,
            )
        self.assertTrue(passed["passed"], passed)
        self.assertEqual(
            [(c["kind"], c.get("cell")) for c in one_cell["checks"] if not c["passed"]], [("xlsx_cell", "C3")]
        )
        self.assertEqual(
            [(c["kind"], c.get("cell")) for c in spilled["checks"] if not c["passed"]], [("xlsx_cell", "B2")]
        )

    def test_open_spreadsheet_selection_delete_clears_only_c3(self):
        task = "wps-open-spreadsheet-selection-delete"
        calls = [_call("spreadsheet_selection_delete", request_id="eval-clear-1")]
        args = ("spreadsheets", "status.xlsx", "eval-clear-1", "spreadsheet-selection-delete")
        with tempfile.TemporaryDirectory() as tmp:
            passed = self.run_open_write(task, Path(tmp), *args, lambda path: self.set_cells(path, {"C3": None}), calls)
            both = self.run_open_write(
                task, Path(tmp) / "b", *args, lambda path: self.set_cells(path, {"C2": None, "C3": None}), calls
            )
        self.assertTrue(passed["passed"], passed)
        self.assertEqual([(c["kind"], c.get("cell")) for c in both["checks"] if not c["passed"]], [("xlsx_cell", "C2")])

    def test_open_save_as_untitled_needs_the_new_file_with_the_untitled_text(self):
        from docx import Document

        def save_as(workspace):
            document = Document()
            document.add_paragraph("Meeting notes: budget approved")
            document.save(workspace / "notes.docx")
            record_operation("eval-save-as-1", "save-as-open-document", {"output": "notes.docx"}, workspace)

        calls = [_call("save_as_open_document", request_id="eval-save-as-1", output="notes.docx")]
        task = "wps-open-save-as-untitled"
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(run_agent_eval, "close_workspace_documents", return_value="closed") as closed,
        ):
            passed = self.run_open_task(task, Path(tmp), save_as, calls)
            nothing = self.run_open_task(task, Path(tmp) / "b", lambda ws: None, calls)
            saved_fixture = self.run_open_task(
                task,
                Path(tmp) / "c",
                save_as,
                [*calls, _call("save_open_document", request_id="eval-save-1")],
            )
        self.assertTrue(passed["passed"], passed)
        self.assertEqual(closed.call_count, 3)
        self.assertEqual([c["kind"] for c in nothing["checks"] if not c["passed"]], ["operation_recorded", "file_text"])
        self.assertEqual([c["kind"] for c in saved_fixture["checks"] if not c["passed"]], ["tool_not_called"])

    def test_a_presentation_caret_must_be_a_collapsed_text_selection(self):
        deck = self.workspace_for_caret()
        options = {"selection": {"text": "Status: DRAFT", "collapse": "end"}}
        cases = (
            ({"status": "ok", "selection_type": 3, "start": 14, "end": 14}, None),
            ({"status": "ok", "selection_type": 3, "start": 1, "end": 14}, "expected a caret"),
            ({"status": "ok", "selection_type": 2, "start": 14, "end": 14}, "not a caret in text"),
        )
        for payload, problem in cases:
            with (
                self.subTest(payload=payload),
                patch.object(run_agent_eval, "open_in_wps", return_value=(lambda: "closed", None)),
                patch.object(run_agent_eval, "wps_document_action", return_value=payload),
            ):
                _sha, _release, reason = run_agent_eval.run_setup(
                    ["open_in_wps", "select_text"], deck.parent, deck, "presentation", options
                )
            if problem is None:
                self.assertIsNone(reason)
            else:
                self.assertIn(problem, reason)

    def workspace_for_caret(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        run_agent_eval.write_fixture(Path(tmp.name), "deck.pptx")
        return Path(tmp.name) / "deck.pptx"

    def test_wps_writer_replace_passes_and_keeps_the_other_paragraphs(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_wps_task(
                "wps-writer-replace",
                Path(tmp),
                lambda ws: self.simulate_write(
                    ws,
                    "writer",
                    "report.docx",
                    "eval-writer-1",
                    "writer-replace",
                    lambda path: self.replace_in_docx(path, "DRAFT", "FINAL"),
                ),
                [_call("writer_replace", request_id="eval-writer-1", find="DRAFT", replace="FINAL")],
            )
        self.assertTrue(result["passed"], result)

    def test_wps_writer_replace_fails_when_draft_is_left(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_wps_task(
                "wps-writer-replace",
                Path(tmp),
                lambda ws: self.simulate_write(
                    ws, "writer", "report.docx", "eval-writer-1", "writer-replace", lambda path: None
                ),
                [_call("writer_replace", request_id="eval-writer-1")],
            )
        text_check = next(check for check in result["checks"] if check["kind"] == "file_text")
        self.assertFalse(text_check["passed"])
        self.assertEqual(text_check["detail"], {"missing": ["Status: FINAL"], "present": ["DRAFT"]})

    def test_wps_presentation_replace_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_wps_task(
                "wps-presentation-replace",
                Path(tmp),
                lambda ws: self.simulate_write(
                    ws,
                    "presentation",
                    "deck.pptx",
                    "eval-presentation-1",
                    "presentation-replace",
                    lambda path: self.replace_in_pptx(path, "DRAFT", "FINAL"),
                ),
                [_call("presentation_replace", request_id="eval-presentation-1", find="DRAFT", replace="FINAL")],
            )
        self.assertTrue(result["passed"], result)

    def test_wps_presentation_replace_fails_when_the_title_is_lost(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_wps_task(
                "wps-presentation-replace",
                Path(tmp),
                lambda ws: self.simulate_write(
                    ws,
                    "presentation",
                    "deck.pptx",
                    "eval-presentation-1",
                    "presentation-replace",
                    lambda path: self.replace_in_pptx(path, "Quarterly review", "FINAL"),
                ),
                [_call("presentation_replace", request_id="eval-presentation-1")],
            )
        text_check = next(check for check in result["checks"] if check["kind"] == "file_text")
        self.assertEqual(text_check["detail"]["missing"], ["Quarterly review", "Status: FINAL"])

    def test_wps_held_write_passes_on_a_reported_refusal(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(run_agent_eval, "hold_file", return_value=(lambda: None, None)),
        ):
            result = self.run_wps_task(
                "wps-held-spreadsheet-write",
                Path(tmp),
                lambda ws: None,
                [_call("spreadsheet_write", error_codes=["DOCUMENT_HELD_OPEN"], request_id="eval-held-write-1")],
            )
        self.assertTrue(result["passed"], result)

    def test_wps_tasks_are_skipped_without_wps(self):
        with tempfile.TemporaryDirectory() as tmp:
            for task_id in WPS_WRITE_TASKS:
                task = _task(task_id)
                result = run_agent_eval.run_task(
                    task,
                    task.get("fixture", "book.xlsx"),
                    task.get("component", "spreadsheets"),
                    Path(tmp),
                    None,
                    15,
                    60,
                    runner=_fake_agent(lambda ws: self.fail("agent must not run")),
                    has_wps=lambda component: False,
                )
                self.assertIn("needs WPS", result["skipped"], task_id)

    def test_sheets_and_read_passes_when_both_reads_were_made_and_nothing_changed(self):
        calls = [_call("register_document"), _call("spreadsheet_sheets"), _call("spreadsheet_read", range="A1")]
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_wps_task("spreadsheet-sheets-and-read", Path(tmp), _register, calls)
            missing_read = self.run_wps_task("spreadsheet-sheets-and-read", Path(tmp) / "b", _register, calls[:2])
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["metrics"]["off_path_calls"], 0)
        self.assertEqual(
            [check["tool"] for check in missing_read["checks"] if not check["passed"]], ["spreadsheet_read"]
        )

    def test_html_table_to_docx_is_judged_from_the_output_document(self):
        from docx import Document

        def convert(workspace, rows):
            document = Document()
            table = document.add_table(rows=len(rows), cols=2)
            for row, values in zip(table.rows, rows, strict=True):
                for cell, value in zip(row.cells, values, strict=True):
                    cell.text = value
            document.save(workspace / "table.docx")

        calls = [_call("html_editable", format="docx")]
        rows = [("Region", "Q1"), ("North", "120"), ("South", "95")]
        with tempfile.TemporaryDirectory() as tmp:
            passed = self.run_wps_task("html-table-to-docx", Path(tmp), lambda ws: convert(ws, rows), calls)
            lost_row = self.run_wps_task("html-table-to-docx", Path(tmp) / "b", lambda ws: convert(ws, rows[:2]), calls)
        self.assertTrue(passed["passed"], passed)
        failed = [check for check in lost_row["checks"] if not check["passed"]]
        self.assertEqual([check["kind"] for check in failed], ["file_text"])
        self.assertEqual(failed[0]["detail"]["missing"], ["South", "95"])

    def test_rename_sheet_passes_when_only_the_sheet_name_changed(self):
        from openpyxl import load_workbook

        def rename(path, value="seed"):
            workbook = load_workbook(path)
            workbook.active.title = "Summary"
            workbook.active["A1"] = value
            workbook.save(path)

        calls = [_call("spreadsheet_rename_sheet", request_id="eval-rename-1", old_name="Sheet", new_name="Summary")]
        with tempfile.TemporaryDirectory() as tmp:
            passed = self.run_wps_task(
                "wps-spreadsheet-rename-sheet",
                Path(tmp),
                lambda ws: self.simulate_write(
                    ws, "spreadsheets", "book.xlsx", "eval-rename-1", "spreadsheet-rename-sheet", rename
                ),
                calls,
            )
            changed_cell = self.run_wps_task(
                "wps-spreadsheet-rename-sheet",
                Path(tmp) / "b",
                lambda ws: self.simulate_write(
                    ws,
                    "spreadsheets",
                    "book.xlsx",
                    "eval-rename-1",
                    "spreadsheet-rename-sheet",
                    lambda path: rename(path, "lost"),
                ),
                calls,
            )
        self.assertTrue(passed["passed"], passed)
        self.assertEqual([c["kind"] for c in changed_cell["checks"] if not c["passed"]], ["xlsx_cell"])

    def test_create_sheet_needs_the_new_sheet_after_the_existing_one(self):
        from openpyxl import load_workbook

        def add(path, index=None):
            workbook = load_workbook(path)
            workbook.create_sheet("Q4", index)
            workbook.save(path)

        calls = [_call("spreadsheet_create_sheet", request_id="eval-create-1", name="Q4")]
        with tempfile.TemporaryDirectory() as tmp:
            passed = self.run_wps_task(
                "wps-spreadsheet-create-sheet",
                Path(tmp),
                lambda ws: self.simulate_write(
                    ws, "spreadsheets", "book.xlsx", "eval-create-1", "spreadsheet-create-sheet", add
                ),
                calls,
            )
            first = self.run_wps_task(
                "wps-spreadsheet-create-sheet",
                Path(tmp) / "b",
                lambda ws: self.simulate_write(
                    ws,
                    "spreadsheets",
                    "book.xlsx",
                    "eval-create-1",
                    "spreadsheet-create-sheet",
                    lambda path: add(path, 0),
                ),
                calls,
            )
        self.assertTrue(passed["passed"], passed)
        failed = [check for check in first["checks"] if not check["passed"]]
        self.assertEqual([check["kind"] for check in failed], ["xlsx_sheets"])
        self.assertEqual(failed[0]["detail"], ["Q4", "Sheet"])

    def test_writer_table_write_passes_when_only_the_north_status_changed(self):
        from docx import Document

        def set_cells(path, cells):
            document = Document(path)
            for row, column in cells:
                document.tables[0].cell(row, column).text = "FINAL"
            document.save(path)

        calls = [_call("writer_table_write", request_id="eval-table-1", table_index=1, row=2, column=3)]
        with tempfile.TemporaryDirectory() as tmp:
            passed = self.run_wps_task(
                "wps-writer-table-write",
                Path(tmp),
                lambda ws: self.simulate_write(
                    ws,
                    "writer",
                    "table_report.docx",
                    "eval-table-1",
                    "writer-table-write",
                    lambda path: set_cells(path, [(1, 2)]),
                ),
                calls,
            )
            too_much = self.run_wps_task(
                "wps-writer-table-write",
                Path(tmp) / "b",
                lambda ws: self.simulate_write(
                    ws,
                    "writer",
                    "table_report.docx",
                    "eval-table-1",
                    "writer-table-write",
                    lambda path: set_cells(path, [(1, 2), (2, 2)]),
                ),
                calls,
            )
        self.assertTrue(passed["passed"], passed)
        failed = [(check["kind"], check.get("row")) for check in too_much["checks"] if not check["passed"]]
        self.assertEqual(failed, [("docx_table_cell", 3)])

    def test_docx_to_pdf_needs_a_real_pdf_and_an_unchanged_source(self):
        calls = [_call("convert_smoke", component="writer", format="pdf")]

        def write(workspace, data):
            (workspace / "report.pdf").write_bytes(data)

        with tempfile.TemporaryDirectory() as tmp:
            passed = self.run_wps_task(
                "wps-docx-to-pdf", Path(tmp), lambda ws: write(ws, b"%PDF-1.7\n" + b"0" * 2000), calls
            )
            not_pdf = self.run_wps_task(
                "wps-docx-to-pdf", Path(tmp) / "b", lambda ws: write(ws, b"<html>" * 400), calls
            )
            too_small = self.run_wps_task(
                "wps-docx-to-pdf", Path(tmp) / "c", lambda ws: write(ws, b"%PDF-1.7\n"), calls
            )
        self.assertTrue(passed["passed"], passed)
        for result in (not_pdf, too_small):
            self.assertEqual([check["kind"] for check in result["checks"] if not check["passed"]], ["pdf_file"])

    def test_open_document_text_export_is_read_as_unicode_text(self):
        text = "\r\n".join(run_agent_eval.WRITER_FIXTURE_PARAGRAPHS)
        calls = [_call("open_documents"), _call("export_open_document_text", output="report.txt")]

        def export(workspace, data):
            (workspace / "report.txt").write_bytes(data)

        task = _task("wps-open-document-export-text")
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(run_agent_eval, "open_in_wps", return_value=(lambda: None, None)) as opened,
        ):
            utf16 = self.run_wps_task(
                task["id"],
                Path(tmp),
                lambda ws: export(ws, "\ufeff".encode("utf-16-le") + text.encode("utf-16-le")),
                calls,
            )
            ansi = self.run_wps_task(task["id"], Path(tmp) / "b", lambda ws: export(ws, text.encode("ascii")), calls)
            saved = self.run_wps_task(
                task["id"],
                Path(tmp) / "c",
                lambda ws: export(ws, text.encode("ascii")),
                [*calls, _call("save_open_document")],
            )
        self.assertTrue(utf16["passed"], utf16)
        self.assertTrue(ansi["passed"], ansi)
        self.assertEqual([c["kind"] for c in saved["checks"] if not c["passed"]], ["tool_not_called"])
        self.assertEqual(opened.call_count, 3)

    def test_open_in_wps_is_a_skip_off_windows(self):
        if os.name == "nt":
            self.skipTest("Windows opens the file for real")
        with tempfile.TemporaryDirectory() as tmp:
            result = run_agent_eval.run_task(
                _task("wps-open-document-export-text"),
                "report.docx",
                "writer",
                Path(tmp),
                None,
                15,
                60,
                runner=_fake_agent(lambda ws: self.fail("agent must not run")),
                has_wps=lambda component: True,
            )
        self.assertIn("needs Windows", result["skipped"])

    def test_the_open_document_is_closed_after_the_agent_ran(self):
        released = []
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(run_agent_eval, "open_in_wps", return_value=(lambda: released.append(True), None)),
        ):
            self.run_wps_task("wps-open-document-export-text", Path(tmp), lambda ws: None, [])
        self.assertEqual(released, [True])

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


class OpenDocumentSetupTests(unittest.TestCase):
    """P6-005: steps that work on a document the runner opened in WPS."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.workspace = Path(tmp.name)
        self.fixture = self.workspace / "report.docx"
        run_agent_eval.write_fixture(self.workspace, "report.docx")
        self.released = []

    def open_ok(self, path, component):
        return (lambda: self.released.append(path.name)), None

    def test_select_text_after_open_keeps_the_document_open_for_the_agent(self):
        options = {"selection": {"text": "DRAFT"}}
        with (
            patch.object(run_agent_eval, "open_in_wps", side_effect=self.open_ok),
            patch.object(
                run_agent_eval, "wps_document_action", return_value={"status": "ok", "selection_text": "DRAFT"}
            ) as action,
        ):
            sha, release, reason = run_agent_eval.run_setup(
                ["open_in_wps", "select_text"], self.workspace, self.fixture, "writer", options
            )
        self.assertIsNone(reason)
        self.assertEqual(sha, run_agent_eval.file_sha256(self.fixture))
        action.assert_called_once_with("writer", self.fixture, "select", text="DRAFT", collapse=None)
        self.assertEqual(self.released, [])
        release()
        self.assertEqual(self.released, ["report.docx"])

    def test_a_selection_that_does_not_read_back_is_a_setup_failure_and_closes_the_document(self):
        options = {"selection": {"text": "DRAFT"}}
        with (
            patch.object(run_agent_eval, "open_in_wps", side_effect=self.open_ok),
            patch.object(
                run_agent_eval, "wps_document_action", return_value={"status": "ok", "selection_text": "DRAF"}
            ),
        ):
            _sha, release, reason = run_agent_eval.run_setup(
                ["open_in_wps", "select_text"], self.workspace, self.fixture, "writer", options
            )
        self.assertIsNone(release)
        self.assertIn("expected 'DRAFT'", reason)
        self.assertEqual(self.released, ["report.docx"])

    def test_a_presentation_selection_must_be_a_text_selection(self):
        deck = self.workspace / "deck.pptx"
        run_agent_eval.write_fixture(self.workspace, "deck.pptx")
        options = {"selection": {"text": "DRAFT"}}
        payloads = [
            {"status": "ok", "selection_text": "DRAFT", "selection_type": 3},
            {"status": "ok", "selection_text": "DRAFT", "selection_type": 2},
        ]
        outcomes = []
        for payload in payloads:
            with (
                patch.object(run_agent_eval, "open_in_wps", side_effect=self.open_ok),
                patch.object(run_agent_eval, "wps_document_action", return_value=payload),
            ):
                outcomes.append(
                    run_agent_eval.run_setup(
                        ["open_in_wps", "select_text"], self.workspace, deck, "presentation", options
                    )
                )
        self.assertIsNone(outcomes[0][2])
        self.assertIn("selection type 2", outcomes[1][2])

    def test_a_collapsed_caret_is_checked_by_position(self):
        options = {"selection": {"text": "Owner: Finance", "collapse": "end"}}
        with (
            patch.object(run_agent_eval, "open_in_wps", side_effect=self.open_ok),
            patch.object(
                run_agent_eval,
                "wps_document_action",
                side_effect=[
                    {"status": "ok", "selection_text": "\r", "start": 40, "end": 40},
                    {"status": "ok", "selection_text": "Owner: Finance", "start": 26, "end": 40},
                ],
            ),
        ):
            _sha, caret, reason = run_agent_eval.run_setup(
                ["open_in_wps", "select_text"], self.workspace, self.fixture, "writer", options
            )
            _sha, not_a_caret, not_a_caret_reason = run_agent_eval.run_setup(
                ["open_in_wps", "select_text"], self.workspace, self.fixture, "writer", options
            )
        self.assertIsNone(reason)
        self.assertIsNotNone(caret)
        self.assertIsNone(not_a_caret)
        self.assertIn("expected a caret", not_a_caret_reason)

    def test_a_spreadsheet_range_is_selected_and_its_address_read_back(self):
        book = self.workspace / "status.xlsx"
        run_agent_eval.write_fixture(self.workspace, "status.xlsx")
        options = {"selection": {"range": "$c$2:C3", "sheet": "Status"}}
        cases = (
            ({"status": "ok", "address": "C2:C3", "sheet": "Status"}, None),
            ({"status": "ok", "address": "A1", "sheet": "Status"}, "WPS selected 'A1', expected 'C2:C3'"),
            ({"status": "ok", "address": "C2:C3", "sheet": "Sheet1"}, "on sheet 'Sheet1', expected 'Status'"),
            ({"status": "not_open"}, "select_text: not_open"),
        )
        for payload, problem in cases:
            self.released = []
            with (
                self.subTest(payload=payload),
                patch.object(run_agent_eval, "open_in_wps", side_effect=self.open_ok),
                patch.object(run_agent_eval, "wps_document_action", return_value=payload) as action,
            ):
                _sha, release, reason = run_agent_eval.run_setup(
                    ["open_in_wps", "select_text"], self.workspace, book, "spreadsheets", options
                )
            action.assert_called_once_with("spreadsheets", book, "select", range="C2:C3", sheet="Status")
            if problem is None:
                self.assertIsNone(reason)
                self.assertIsNotNone(release)
            else:
                self.assertIn(problem, reason)
                self.assertEqual(self.released, ["status.xlsx"])

    def test_an_untitled_document_is_made_named_in_the_state_and_closed_with_the_run(self):
        from wps_ai_agent_cli import open_documents

        saved_as = self.workspace / "notes.docx"
        actions = []

        def action(component, path, step, **params):
            actions.append((step, Path(path).name, params))
            if step == "new_untitled":
                return {"status": "ok", "name": "文字文稿2", "saved": False}
            return {"status": "closed"}

        listed = [{"full_name": str(self.fixture)}, {"full_name": str(saved_as)}, {"full_name": "C:\\elsewhere.docx"}]
        state = {}
        with (
            patch.object(run_agent_eval, "open_in_wps", side_effect=self.open_ok),
            patch.object(run_agent_eval, "wps_document_action", side_effect=action),
            patch.object(open_documents, "list_open_documents", return_value=(True, {"documents": listed}, [])),
        ):
            _sha, release, reason = run_agent_eval.run_setup(
                ["open_in_wps", "untitled_document"],
                self.workspace,
                self.fixture,
                "writer",
                {"untitled_text": "Meeting notes"},
                state,
            )
            self.assertIsNone(reason)
            self.assertEqual(state, {"untitled_name": "文字文稿2"})
            outcome = release()
        self.assertEqual(
            actions,
            [
                ("new_untitled", "report.docx", {"text": "Meeting notes"}),
                ("close_untitled", "report.docx", {"name": "文字文稿2"}),
                ("close_discard", "notes.docx", {}),
            ],
        )
        self.assertEqual(self.released, ["report.docx"])
        self.assertIn("untitled 文字文稿2 closed; notes.docx closed", outcome)

    def test_a_failed_untitled_document_is_a_setup_failure(self):
        with (
            patch.object(run_agent_eval, "open_in_wps", side_effect=self.open_ok),
            patch.object(run_agent_eval, "wps_document_action", return_value={"status": "no_instance"}),
            patch.object(run_agent_eval, "close_workspace_documents", return_value="nothing"),
        ):
            _sha, release, reason = run_agent_eval.run_setup(
                ["open_in_wps", "untitled_document"], self.workspace, self.fixture, "writer", {}
            )
        self.assertIsNone(release)
        self.assertEqual(reason, "untitled_document: no_instance")
        self.assertEqual(self.released, ["report.docx"])

    def test_the_prompt_names_the_untitled_document_wps_made(self):
        task = {
            "id": "untitled",
            "requires_wps": True,
            "setup": ["open_in_wps", "untitled_document"],
            "prompt": "Save the untitled document {untitled_name} as notes.docx.",
            "checks": [],
        }
        prompts = []

        def setup(steps, workspace, fixture, component, options, state=None):
            state["untitled_name"] = "文字文稿3"
            return "sha", (lambda: "closed"), None

        def agent(prompt, *args):
            prompts.append(prompt)
            return {"ran": True, "tool_calls": []}

        with tempfile.TemporaryDirectory() as tmp, patch.object(run_agent_eval, "run_setup", side_effect=setup):
            result = run_agent_eval.run_task(
                task, "report.docx", "writer", Path(tmp), None, 15, 60, runner=agent, has_wps=lambda c: True
            )
        self.assertEqual(prompts, ["Save the untitled document 文字文稿3 as notes.docx."])
        self.assertEqual(result["untitled_name"], "文字文稿3")
        self.assertEqual(result["cleanup"], "closed")

    def test_append_unsaved_must_leave_the_document_unsaved(self):
        options = {"unsaved_text": "Reviewed in WPS"}
        for payload, fails in (({"status": "ok", "saved": False}, False), ({"status": "ok", "saved": True}, True)):
            with (
                self.subTest(payload=payload),
                patch.object(run_agent_eval, "open_in_wps", side_effect=self.open_ok),
                patch.object(run_agent_eval, "wps_document_action", return_value=payload),
            ):
                _sha, release, reason = run_agent_eval.run_setup(
                    ["open_in_wps", "append_unsaved"], self.workspace, self.fixture, "writer", options
                )
            self.assertEqual(reason is not None, fails, reason)

    def test_only_open_document_steps_may_follow_open_in_wps_and_nothing_may_follow_hold(self):
        for steps in (["open_in_wps", "register"], ["hold", "select_text"]):
            with self.subTest(steps=steps), self.assertRaises(ValueError):
                run_agent_eval.run_setup(steps, self.workspace, self.fixture, "writer", {})

    def test_a_fixture_left_unsaved_is_closed_without_saving_before_its_process_is_ended(self):
        from wps_ai_agent_cli import open_documents

        unsaved = (None, {"code": "DOCUMENT_HAS_UNSAVED_CHANGES", "message": "unsaved"})
        for closed, discarded in ((("closed", None), False), (unsaved, True)):
            with (
                self.subTest(closed=closed),
                patch.object(open_documents, "close_unchanged_document", return_value=closed),
                patch.object(run_agent_eval, "wps_document_action") as action,
                patch.object(run_agent_eval, "stop_started_wps") as stop,
            ):
                stop.return_value = "stopped 42"
                action.return_value = {"status": "closed"}
                outcome = run_agent_eval.release_opened_fixture("writer", self.fixture, {42})
            self.assertEqual(action.called, discarded)
            self.assertIn("processes stopped 42", outcome)
            self.assertIn("discarded: closed" if discarded else "fixture closed", outcome)
            if discarded:
                action.assert_called_once_with("writer", self.fixture, "close_discard")
            stop.assert_called_once_with("writer", {42})

    def test_started_wps_processes_are_ended_only_when_wps_lists_no_document(self):
        from wps_ai_agent_cli import open_documents, powershell_runner

        for documents, stopped in (([{"full_name": "C:\\other.docx"}], False), ([], True)):
            with (
                self.subTest(documents=documents),
                patch.object(open_documents, "list_open_documents", return_value=(True, {"documents": documents}, [])),
                patch.object(powershell_runner, "run_powershell_command") as command,
            ):
                outcome = run_agent_eval.stop_started_wps("writer", {42, 7})
            self.assertEqual(command.called, stopped, outcome)
            if stopped:
                self.assertIn("Stop-Process -Id 7,42", command.call_args.args[0])
        with patch.object(powershell_runner, "run_powershell_command") as command:
            self.assertEqual(run_agent_eval.stop_started_wps("writer", set()), "none started")
        command.assert_not_called()

    def test_the_registered_open_command_becomes_the_launch_command_line(self):
        path = Path("C:/Users/a b/report.docx")
        cases = {
            ('"C:\\WPS\\office6\\wps.exe" "%1"', False): f'"C:\\WPS\\office6\\wps.exe" "{path}"',
            ('"C:\\WPS\\office6\\wps.exe" "%1"', True): f'"C:\\WPS\\office6\\wps.exe" /Automation "{path}"',
            ('"C:\\WPS\\office6\\et.exe" "%1" %*', False): f'"C:\\WPS\\office6\\et.exe" "{path}"',
            ("C:\\WPS\\wpp.exe %1", True): f"C:\\WPS\\wpp.exe /Automation {path}",
            ('"C:\\WPS\\wps.exe"', False): f'"C:\\WPS\\wps.exe" "{path}"',
        }
        for (template, automation), expected in cases.items():
            with self.subTest(template=template, automation=automation):
                self.assertEqual(run_agent_eval.launch_command_line(template, path, automation), expected)

    def test_the_cli_is_started_by_its_resolved_path_and_read_as_utf8(self):
        import subprocess

        completed = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with (
            patch.object(run_agent_eval.shutil, "which", return_value="C:\\npm\\claude.CMD"),
            patch.object(run_agent_eval.subprocess, "run", return_value=completed) as run,
        ):
            run_agent_eval.run_claude("prompt", Path("mcp.json"), Path("."), None, 5, 60)
        command = run.call_args.args[0]
        self.assertEqual(command[0], "C:\\npm\\claude.CMD")
        self.assertEqual(run.call_args.kwargs["encoding"], "utf-8")
        self.assertEqual(run.call_args.kwargs["errors"], "replace")

    def test_an_api_error_of_the_cli_is_flagged_as_an_agent_error(self):
        self.assertEqual(
            run_agent_eval.agent_error({"is_error": True, "result_excerpt": "API Error: 402 Insufficient Balance"}),
            "API Error: 402 Insufficient Balance",
        )
        self.assertIsNone(run_agent_eval.agent_error({"is_error": False, "result_excerpt": "Done."}))
        self.assertIsNone(run_agent_eval.agent_error({"is_error": True, "result_excerpt": "Reached max turns"}))

    def test_the_cleanup_of_an_opened_fixture_is_recorded_with_the_run(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(
                run_agent_eval, "open_in_wps", return_value=(lambda: "fixture closed; processes none started", None)
            ),
        ):
            result = run_agent_eval.run_task(
                _task("wps-open-document-export-text"),
                "report.docx",
                "writer",
                Path(tmp),
                None,
                15,
                60,
                runner=_fake_agent(lambda ws: None),
                has_wps=lambda component: True,
            )
        self.assertEqual(result["cleanup"], "fixture closed; processes none started")

    def test_the_wps_launch_mode_is_an_option_and_recorded_in_the_summary(self):
        with self.assertRaises(SystemExit):
            run_agent_eval.main(["--wps-launch", "elsewhere"])
        self.assertIn("wps_launch", run_agent_eval.summarize([], "stamp", None))


PWSH = os.environ.get("WPS_TEST_PWSH") or __import__("shutil").which("pwsh")


@unittest.skipUnless(PWSH, "PowerShell (pwsh) is required to parse the runner's WPS scripts")
class OpenDocumentScriptParseTests(unittest.TestCase):
    def test_the_runner_scripts_parse(self):
        import subprocess

        from wps_ai_agent_cli.wps_script_snippets import ATTACH_RUNNING_INSTANCE

        scripts = {
            "document": run_agent_eval._WPS_DOCUMENT_SCRIPT.replace("__ATTACH__", ATTACH_RUNNING_INSTANCE),
        }
        for name, script in scripts.items():
            with self.subTest(script=name), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / f"{name}.ps1"
                path.write_text(script, encoding="utf-8")
                check = (
                    "$errors = $null; [void][System.Management.Automation.Language.Parser]::ParseFile("
                    f"'{path}', [ref]$null, [ref]$errors); $errors.Count"
                )
                completed = subprocess.run(
                    [PWSH, "-NoProfile", "-Command", check], capture_output=True, text=True, timeout=120, check=False
                )
                self.assertEqual(completed.stdout.strip(), "0", completed.stdout + completed.stderr)
class OpenDocumentScriptStdoutTests(unittest.TestCase):
    def test_the_script_swallows_the_return_value_of_activate(self):
        # The Windows check on 564d103 skipped both spreadsheet selection tasks: their select_text
        # preparation ran $doc.Activate() and $sheet.Activate() bare, PowerShell wrote "True" to stdout
        # ahead of the JSON, and _run_script read the whole output as script_failed / COM_OPERATION_FAILED
        # even though the payload it printed said the range was selected.
        script = run_agent_eval._WPS_DOCUMENT_SCRIPT
        for call in ("$doc.Activate()", "$sheet.Activate()"):
            with self.subTest(call=call):
                self.assertEqual(script.count(call), 1)
                self.assertIn(f"[void]{call}", script)
