from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any


DEFAULT_REGRESSION_MANIFEST = "config/regression_manifest.json"

# A manifest is data supplied by the caller (including over MCP, where regression-run is advertised as
# non-mutating), so scenarios may only run the read-only and smoke commands the shipped manifest uses.
REGRESSION_ALLOWED_COMMANDS = frozenset({
    "artifact-retention-summary",
    "calc-smoke",
    "com-smoke",
    "convert-smoke",
    "documentation-freshness",
    "local-handoff-summary",
    "mcp-catalog-drift",
    "mcp-config-audit",
    "mcp-smoke",
    "mcp-tools",
    "plan",
    "regression-evidence",
    "regression-history",
    "security-audit",
    "sync-package-coverage",
    "sync-package-inspect",
    "sync-package-manifest",
    "sync-package-readiness",
    "sync-package-summary",
    "tasks",
    "validation-runbook",
    "writer-table-smoke",
})


def load_regression_manifest(path: str | Path = DEFAULT_REGRESSION_MANIFEST) -> tuple[bool, dict[str, Any], list[dict[str, Any]]]:
    manifest_path = Path(path)
    if not manifest_path.exists():
        return False, {}, [{"code": "REGRESSION_MANIFEST_NOT_FOUND", "message": f"Manifest not found: {manifest_path}"}]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, {}, [{"code": "REGRESSION_MANIFEST_INVALID_JSON", "message": str(exc)}]
    scenarios = manifest.get("scenarios")
    if not isinstance(scenarios, list):
        return False, {}, [{"code": "REGRESSION_MANIFEST_INVALID", "message": "Manifest scenarios must be a list."}]
    return True, manifest, []


def list_regression_scenarios(
    manifest: dict[str, Any],
    profile: str | None = None,
    include_wps: bool = False,
) -> list[dict[str, Any]]:
    scenarios = [dict(scenario) for scenario in manifest.get("scenarios", [])]
    if profile:
        scenarios = [scenario for scenario in scenarios if scenario.get("profile") == profile]
    if not include_wps:
        scenarios = [scenario for scenario in scenarios if not scenario.get("requires_wps")]
    return scenarios


def _lookup_path(payload: Any, path: str) -> Any:
    current = payload
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _contains_item(items: Any, expected: dict[str, Any]) -> bool:
    if not isinstance(items, list):
        return False
    for item in items:
        if isinstance(item, dict) and all(item.get(key) == value for key, value in expected.items()):
            return True
    return False


def _evaluate_check(payload: dict[str, Any], check: dict[str, Any]) -> dict[str, Any]:
    value = _lookup_path(payload, check.get("path", ""))
    if "equals" in check:
        passed = value == check["equals"]
        details = {"actual": value, "expected": check["equals"]}
    elif "min_length" in check:
        passed = isinstance(value, list) and len(value) >= check["min_length"]
        details = {"actual": len(value) if isinstance(value, list) else None, "expected_min": check["min_length"]}
    elif "contains_item" in check:
        passed = _contains_item(value, check["contains_item"])
        details = {"expected_item": check["contains_item"]}
    else:
        passed = False
        details = {"unsupported_check": check}
    return {"path": check.get("path"), "passed": passed, "details": details}


def _run_cli(command: list[str]) -> tuple[int, dict[str, Any] | None, str]:
    from .cli import run

    output = io.StringIO()
    try:
        exit_code = run(command, output_stream=output)
    except Exception as exc:
        command_name = command[0] if command else "unknown"
        payload = {
            "ok": False,
            "command": command_name,
            "summary": "Regression scenario raised an exception.",
            "errors": [
                {
                    "code": "REGRESSION_SCENARIO_EXCEPTION",
                    "message": str(exc),
                    "exception_type": exc.__class__.__name__,
                }
            ],
        }
        return 1, payload, f"{exc.__class__.__name__}: {exc}"
    raw_output = output.getvalue().strip()
    try:
        payload = json.loads(raw_output) if raw_output else None
    except json.JSONDecodeError:
        payload = None
    return exit_code, payload, raw_output


def run_regression_manifest(
    manifest_path: str | Path = DEFAULT_REGRESSION_MANIFEST,
    profile: str | None = None,
    include_wps: bool = False,
) -> tuple[bool, dict[str, Any], list[dict[str, Any]]]:
    ok, manifest, errors = load_regression_manifest(manifest_path)
    if not ok:
        return False, {}, errors

    resolved_profile = profile or manifest.get("default_profile")
    scenarios = list_regression_scenarios(manifest, profile=resolved_profile, include_wps=include_wps)
    results: list[dict[str, Any]] = []
    for scenario in scenarios:
        command = scenario.get("command")
        if (
            not isinstance(command, list)
            or not command
            or not all(isinstance(part, str) for part in command)
            or command[0] not in REGRESSION_ALLOWED_COMMANDS
        ):
            exit_code, payload, raw_output = 1, {
                "ok": False,
                "summary": "Regression scenario command is not allowed.",
                "errors": [{
                    "code": "REGRESSION_COMMAND_NOT_ALLOWED",
                    "message": "Scenarios may only run the read-only and smoke commands used by the shipped manifest; nothing was executed.",
                    "command": command[0] if isinstance(command, list) and command and isinstance(command[0], str) else None,
                }],
            }, ""
        else:
            exit_code, payload, raw_output = _run_cli(list(command))
        checks = []
        if payload is not None:
            checks = [_evaluate_check(payload, check) for check in scenario.get("required_checks", [])]
        expected_ok = scenario.get("expected_ok", True)
        response_ok = bool(payload and payload.get("ok") == expected_ok)
        scenario_ok = exit_code == 0 and response_ok and all(check["passed"] for check in checks)
        results.append(
            {
                "id": scenario.get("id"),
                "title": scenario.get("title"),
                "category": scenario.get("category"),
                "profile": scenario.get("profile"),
                "requires_wps": bool(scenario.get("requires_wps")),
                "risk_level": scenario.get("risk_level"),
                "command": scenario.get("command"),
                "ok": scenario_ok,
                "exit_code": exit_code,
                "response_ok": response_ok,
                "checks": checks,
                "summary": payload.get("summary") if payload else None,
                "errors": payload.get("errors") if payload else None,
                "raw_output": raw_output if payload is None else None,
            }
        )

    passed_count = sum(1 for result in results if result["ok"])
    failed = [result for result in results if not result["ok"]]
    result = {
        "manifest_path": str(manifest_path),
        "version": manifest.get("version"),
        "profile": resolved_profile,
        "include_wps": include_wps,
        "scenario_count": len(results),
        "passed_count": passed_count,
        "failed_count": len(failed),
        "results": results,
    }
    errors = [] if not failed else [
        {
            "code": "REGRESSION_RUN_FAILED",
            "message": "One or more regression scenarios failed.",
            "details": [
                {
                    "id": item["id"],
                    "checks": item["checks"],
                    "summary": item["summary"],
                    "errors": item["errors"],
                }
                for item in failed
            ],
        }
    ]
    return not failed, result, errors
