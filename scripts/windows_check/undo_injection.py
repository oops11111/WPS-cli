"""Make a selection write's read-back fail inside this process, so the undo in WPS runs on real WPS (P7-002).

H1 asks for the undo of a failed open-document write (P7-001) to be seen working on real WPS, for Writer and for
Presentation. A real read-back failure cannot be produced on demand, and the product has no switch for one. So
this module patches, in this process only, the function that runs the write script: the write runs in WPS as it
always does, then its reported read-back is replaced, the command rejects the write, and the real undo runs.

Each scenario opens a fixture in WPS the way the agent evaluation does (its registered open command), selects
"DRAFT" (or, for a worksheet shape or chart title, the object holding it; P10-005), runs the command and records the file hashes before the write, after the write and after the undo, the
errors, the rollback the command reported, and the text on disk afterwards.
"""

from __future__ import annotations

import contextlib
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import patch

INJECTED_READ_BACK = "<read-back replaced by undo_injection>"
WRITE_ACTIONS = {
    "selection-replace",
    "selection-insert",
    "selection-delete",
    "selection-shape-replace",
    "selection-shape-delete",
    "selection-chart-title-replace",
    "selection-chart-title-delete",
    "selection-axis-title-replace",
    "selection-axis-title-delete",
    "selection-series-values-replace",
    "selection-series-values-delete",
}
RUNNER_FUNCTIONS = {
    "writer": "_run_writer_attached_com",
    "presentation": "_run_presentation_attached_com",
    "spreadsheets": "_run_spreadsheet_attached_com",
}

# Each scenario: component, fixture name, the text to select, the command and its arguments.
SCENARIOS: dict[str, dict[str, Any]] = {
    "writer-replace": {
        "component": "writer",
        "fixture": "report.docx",
        "select": "DRAFT",
        "command": "replace_writer_selection",
        "arguments": {"text": "FINAL"},
    },
    "presentation-replace": {
        "component": "presentation",
        "fixture": "deck.pptx",
        "select": "DRAFT",
        "command": "replace_presentation_selection",
        "arguments": {"text": "FINAL"},
    },
    # A worksheet text box and a chart title (P10-005): the selection is the object, not text in it.
    "spreadsheet-shape-text-replace": {
        "component": "spreadsheets",
        "fixture": "chart_note.xlsx",
        "selection": {"sheet": "Status", "object": "Note 1"},
        "command": "replace_spreadsheet_selection",
        "arguments": {"text": "FINAL", "expected_selection_text": "DRAFT"},
    },
    "spreadsheet-chart-title-replace": {
        "component": "spreadsheets",
        "fixture": "chart_note.xlsx",
        "selection": {"sheet": "Status", "object": "Chart 1", "part": "chart_title"},
        "command": "replace_spreadsheet_selection",
        "arguments": {"text": "FINAL", "expected_selection_text": "DRAFT"},
    },
}


@contextlib.contextmanager
def read_back_failure(component: str) -> Iterator[dict[str, Any]]:
    """Within the block, a write that WPS reports as done reads back as INJECTED_READ_BACK.

    Yields a record of what was replaced. Nothing outside this process changes: the write and the undo still run
    in WPS through the real scripts.
    """
    from wps_ai_agent_cli import open_documents

    name = RUNNER_FUNCTIONS[component]
    real = getattr(open_documents, name)
    record: dict[str, Any] = {"injected": False, "actions": []}

    def wrapped(action: str, params: dict[str, Any]) -> dict[str, Any]:
        result = real(action, params)
        record["actions"].append(action)
        data = result.get("data") if isinstance(result, dict) else None
        if action in WRITE_ACTIONS and result.get("ok") and isinstance(data, dict) and data.get("status") == "ok":
            record["injected"] = True
            record["real_read_back_text"] = data.get("read_back_text")
            result = {**result, "data": {**data, "read_back_text": INJECTED_READ_BACK, "cells_matched": False}}
        return result

    with patch.object(open_documents, name, side_effect=wrapped):
        yield record


def wps_saved(component: str, path: Path) -> bool | None:
    """Whether WPS reports the document as saved, or None when WPS does not list it."""
    from wps_ai_agent_cli.open_documents import list_open_documents

    target = str(path.resolve()).casefold()
    _ok, data, _errors = list_open_documents(component)
    for item in data.get("documents", []):
        if str(Path(item.get("full_name") or "").resolve()).casefold() == target:
            saved = item.get("saved")
            return None if saved is None else bool(saved)
    return None


def verdict(result: dict[str, Any]) -> tuple[bool, list[str]]:
    """The conditions H1 sets for one scenario, each as a line that says whether it held."""
    if result.get("setup_failed"):
        return False, [f"- FAILED: setup: {result['setup_failed']}"]
    rollback = result.get("rollback") or {}
    codes = result.get("error_codes") or []
    hashes = result.get("hashes") or {}
    conditions = [
        ("the read-back failure was injected after WPS reported the write done", result.get("injected") is True),
        (
            "WPS saved the write (the file changed before the undo)",
            bool(hashes.get("before_write")) and hashes.get("before_undo") not in (None, hashes.get("before_write")),
        ),
        (
            "the command reported VALIDATION_FAILED, then MUTATION_ROLLED_BACK",
            codes[-2:] == ["VALIDATION_FAILED", "MUTATION_ROLLED_BACK"],
        ),
        ("no MUTATION_ROLLBACK_BLOCKED", "MUTATION_ROLLBACK_BLOCKED" not in codes),
        ("rollback.rolled_back_in_wps is true", rollback.get("rolled_back_in_wps") is True),
        ("rollback.content_matches_backup is true", rollback.get("content_matches_backup") is True),
        ("the text on disk is the text before the write", result.get("text_after") == result.get("text_before")),
        ("WPS reports the document saved after the undo", result.get("wps_saved_after") is True),
    ]
    lines = [f"- {'ok' if held else 'FAILED'}: {name}" for name, held in conditions]
    return all(held for _name, held in conditions), lines


def run_scenario(name: str, runner: Any, root: Path | None = None) -> dict[str, Any]:
    """Run one scenario in a new workspace and return what it recorded; the document is closed afterwards."""
    from wps_ai_agent_cli import open_documents
    from wps_ai_agent_cli.sessions import stable_document_id

    scenario = SCENARIOS[name]
    component = scenario["component"]
    base = root or Path(tempfile.gettempdir()) / "wps-undo-injection"
    base.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix=f"{name}-", dir=base))
    fixture = workspace / scenario["fixture"]
    result: dict[str, Any] = {"scenario": name, "component": component, "workspace": str(workspace)}
    runner.write_fixture(workspace, scenario["fixture"])
    result["text_before"] = runner.document_text(fixture)
    before_write, release, reason = runner.run_setup(
        ["register", "open_in_wps", "select_text"],
        workspace,
        fixture,
        component,
        {"selection": scenario.get("selection") or {"text": scenario["select"]}},
    )
    result["hashes"] = {"before_write": before_write}
    if release is None:
        result["setup_failed"] = reason
        return result
    try:
        command = getattr(open_documents, scenario["command"])
        with read_back_failure(component) as injection:
            ok, data, errors, _replayed = command(
                document_id=stable_document_id(component, str(fixture)),
                request_id=f"undo-injection-{name}",
                workspace=workspace,
                **scenario["arguments"],
            )
        rollback = data.get("rollback") or {}
        result.update(
            {
                "ok": ok,
                "injected": injection["injected"],
                "real_read_back_text": injection.get("real_read_back_text"),
                "com_actions": injection["actions"],
                "error_codes": [error.get("code") for error in errors],
                "errors": errors,
                "rollback": rollback,
            }
        )
        result["hashes"].update(
            {
                "before_undo": rollback.get("file_sha256_before_undo"),
                "after_undo": rollback.get("file_sha256_after_undo"),
                "now": runner.file_sha256(fixture),
            }
        )
        result["text_after"] = runner.document_text(fixture)
        result["wps_saved_after"] = wps_saved(component, fixture)
    finally:
        result["cleanup"] = release()
    return result
