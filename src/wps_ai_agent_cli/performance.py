from __future__ import annotations

import io
import json
import time
from typing import Any

MCP_BASELINE_EXPECTED_TOOL_COUNT = 70


PERFORMANCE_BASELINE_COMMANDS: tuple[dict[str, Any], ...] = (
    {
        "id": "mcp-tools",
        "category": "mcp",
        "command": ["mcp-tools"],
        "launches_wps": False,
    },
    {
        "id": "mcp-smoke",
        "category": "mcp",
        "command": [
            "mcp-smoke",
            "--expected-min-tools",
            str(MCP_BASELINE_EXPECTED_TOOL_COUNT),
            "--tool-name",
            "wps_agent_tasks",
        ],
        "launches_wps": False,
    },
    {
        "id": "mcp-config-audit",
        "category": "mcp",
        "command": [
            "mcp-config-audit",
            "--config",
            "config/mcp_client_config.example.json",
            "--server-name",
            "wps-ai-agent-cli",
            "--expected-min-tools",
            str(MCP_BASELINE_EXPECTED_TOOL_COUNT),
        ],
        "launches_wps": False,
    },
    {
        "id": "security-audit",
        "category": "security",
        "command": ["security-audit"],
        "launches_wps": False,
    },
    {
        "id": "batch-report-phase0-no-snapshots",
        "category": "batch",
        "command": ["batch-report", "--path", "fixtures/phase0", "--no-snapshots"],
        "launches_wps": False,
    },
    {
        "id": "regression-run-safe",
        "category": "regression",
        "command": ["regression-run", "--profile", "safe"],
        "launches_wps": False,
    },
)


def _run_cli(command: list[str]) -> tuple[int, dict[str, Any] | None, str, float]:
    from .cli import run

    output = io.StringIO()
    started = time.perf_counter()
    exit_code = run(command, output_stream=output)
    duration_ms = (time.perf_counter() - started) * 1000
    raw_output = output.getvalue().strip()
    try:
        payload = json.loads(raw_output) if raw_output else None
    except json.JSONDecodeError:
        payload = None
    return exit_code, payload, raw_output, duration_ms


def capture_performance_baseline() -> tuple[bool, dict[str, Any], list[dict[str, Any]]]:
    results = []
    for scenario in PERFORMANCE_BASELINE_COMMANDS:
        exit_code, payload, raw_output, duration_ms = _run_cli(list(scenario["command"]))
        output_bytes = len(raw_output.encode("utf-8"))
        response_ok = bool(payload and payload.get("ok"))
        validation_status = payload.get("validation", {}).get("status") if payload else None
        results.append(
            {
                "id": scenario["id"],
                "category": scenario["category"],
                "command": scenario["command"],
                "launches_wps": scenario["launches_wps"],
                "exit_code": exit_code,
                "ok": exit_code == 0 and response_ok,
                "response_ok": response_ok,
                "validation_status": validation_status,
                "duration_ms": round(duration_ms, 3),
                "output_bytes": output_bytes,
                "output_chars": len(raw_output),
                "summary": payload.get("summary") if payload else None,
            }
        )

    failed = [result for result in results if not result["ok"]]
    wps_launching = [result for result in results if result["launches_wps"]]
    total_duration_ms = round(sum(result["duration_ms"] for result in results), 3)
    result = {
        "scenario_count": len(results),
        "passed_count": len(results) - len(failed),
        "failed_count": len(failed),
        "total_duration_ms": total_duration_ms,
        "max_duration_ms": max((result["duration_ms"] for result in results), default=0),
        "total_output_bytes": sum(result["output_bytes"] for result in results),
        "launches_wps": bool(wps_launching),
        "results": results,
    }
    errors: list[dict[str, Any]] = []
    if failed:
        errors.append(
            {
                "code": "PERFORMANCE_BASELINE_COMMAND_FAILED",
                "message": "One or more baseline commands failed.",
                "details": [{"id": item["id"], "summary": item["summary"]} for item in failed],
            }
        )
    if wps_launching:
        errors.append(
            {
                "code": "PERFORMANCE_BASELINE_WPS_SCENARIO_INCLUDED",
                "message": "Performance baseline must not launch WPS.",
                "details": [item["id"] for item in wps_launching],
            }
        )
    return not errors, result, errors


# T-09: the fixed cost of one real WPS operation, the evidence C-10 (resident mode) is decided on. Only with
# performance-baseline --include-wps: the safe baseline above never starts WPS.
C10_FIXED_COST_THRESHOLD_MS = 2000
WPS_MEASURE_REPEAT = 3


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    return round(ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2, 3)


def _wps_process_count() -> int | None:
    from .process_audit import audit_wps_processes

    ok, data, _errors = audit_wps_processes()
    if not ok:
        return None
    return sum(1 for item in data.get("processes", []) if str(item.get("ProcessName", "")).lower() == "et")


def _process_start_ms(workspace: str) -> tuple[bool, float]:
    """One `python -m wps_ai_agent_cli documents` in a new process: what a CLI user pays before any work."""
    import subprocess
    import sys

    started = time.perf_counter()
    completed = subprocess.run(
        [sys.executable, "-m", "wps_ai_agent_cli", "documents"],
        cwd=workspace,
        capture_output=True,
        timeout=120,
        check=False,
    )
    return completed.returncode == 0, round((time.perf_counter() - started) * 1000, 3)


def measure_wps_operation_cost(repeat: int = WPS_MEASURE_REPEAT) -> tuple[bool, dict[str, Any], list[dict[str, Any]]]:
    """Time `repeat` spreadsheet-write calls through WPS on a new workbook in a temporary folder, and `repeat`
    new CLI processes; report the medians and whether one CLI call's fixed cost passes the C-10 threshold."""
    import os
    import tempfile
    from pathlib import Path

    from .document_new import create_document

    errors: list[dict[str, Any]] = []
    processes_before = _wps_process_count()
    previous = os.getcwd()
    with tempfile.TemporaryDirectory(prefix="wps-agent-perf-", ignore_cleanup_errors=True) as workspace:
        os.chdir(workspace)
        try:
            ok, created, create_errors = create_document(
                "spreadsheets", str(Path(workspace) / "perf.xlsx"), workspace=workspace
            )
            if not ok:
                return False, {"stage": "document-new"}, create_errors
            document_id = created["document_id"]
            calls = []
            for index in range(1, repeat + 1):
                command = [
                    "spreadsheet-write",
                    "--document-id",
                    document_id,
                    "--range",
                    "A1",
                    "--values-json",
                    json.dumps([[index]]),
                    "--request-id",
                    f"perf-{index}",
                ]
                exit_code, payload, _raw, duration_ms = _run_cli(command)
                call_ok = exit_code == 0 and bool(payload and payload.get("ok"))
                calls.append({"index": index, "ok": call_ok, "duration_ms": round(duration_ms, 3)})
                if not call_ok:
                    errors.append(
                        {
                            "code": "PERFORMANCE_WPS_CALL_FAILED",
                            "message": f"spreadsheet-write {index} failed: "
                            + (str((payload or {}).get("errors") or (payload or {}).get("summary"))[:300]),
                        }
                    )
                    break
            starts = [_process_start_ms(workspace) for _ in range(repeat)]
        finally:
            os.chdir(previous)
    processes_after = _wps_process_count()
    if not all(ok for ok, _ in starts):
        errors.append({"code": "PERFORMANCE_PROCESS_START_FAILED", "message": "python -m wps_ai_agent_cli failed."})

    call_durations = [call["duration_ms"] for call in calls if call["ok"]]
    start_durations = [duration for ok, duration in starts if ok]
    call_median = _median(call_durations)
    start_median = _median(start_durations)
    fixed_cost = round(call_median + start_median, 3) if call_median is not None and start_median is not None else None
    result = {
        "repeat": repeat,
        "operation": "spreadsheet-write A1 on a new workbook, through WPS",
        "wps_calls": calls,
        "wps_call_median_ms": call_median,
        "wps_first_call_ms": call_durations[0] if call_durations else None,
        "process_starts_ms": start_durations,
        "process_start_median_ms": start_median,
        "cli_call_fixed_cost_ms": fixed_cost,
        "c10_threshold_ms": C10_FIXED_COST_THRESHOLD_MS,
        "c10_threshold_exceeded": None if fixed_cost is None else fixed_cost > C10_FIXED_COST_THRESHOLD_MS,
        "spreadsheet_processes_before": processes_before,
        "spreadsheet_processes_after": processes_after,
        "note": "cli_call_fixed_cost_ms = median new-process start + median WPS call: what one CLI call costs. "
        "An MCP client pays only the WPS call (the server is resident). C-10 reopens only if this exceeds "
        "the threshold and real workloads call several times a minute.",
    }
    return not errors, result, errors


def capture_performance_baseline_with_wps(
    repeat: int = WPS_MEASURE_REPEAT,
) -> tuple[bool, dict[str, Any], list[dict[str, Any]]]:
    ok, result, errors = capture_performance_baseline()
    wps_ok, wps_result, wps_errors = measure_wps_operation_cost(repeat)
    result["wps_operation_cost"] = wps_result
    return ok and wps_ok, result, errors + wps_errors
