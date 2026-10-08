from __future__ import annotations

import io
import json
import time
from typing import Any


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
        "command": ["mcp-smoke", "--expected-min-tools", "47", "--tool-name", "wps_agent_tasks"],
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
            "47",
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
