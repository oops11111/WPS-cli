from __future__ import annotations

import io
import json
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_REGRESSION_MANIFEST = "config/regression_manifest.json"
REPO_ROOT = Path(__file__).resolve().parents[2]
MCP_AUDIT_TEMPLATE = "config/mcp_client_config.regression.template.json"
# Scenario arguments may name an output file as "{output_dir}/name". Each run replaces the placeholder with
# its own directory under REGRESSION_OUTPUT_ROOT, which git ignores, so a run never rewrites tracked files.
OUTPUT_DIR_PLACEHOLDER = "{output_dir}"
REGRESSION_OUTPUT_ROOT = REPO_ROOT / "artifacts" / "regression" / "outputs"


def _render_mcp_audit_config(template: Path, destination_dir: Path) -> Path:
    """Write the audit config for the interpreter running this regression.

    The template names no interpreter, because `python` on Windows can be the Store alias, which exits without
    running anything. The server is launched by sys.executable, from this repository, with its src directory on
    PYTHONPATH. Both paths are absolute, so the audit does not depend on where it was started from.
    """
    config = json.loads(template.read_text(encoding="utf-8"))
    for server in config["mcpServers"].values():
        server["command"] = sys.executable
        server["cwd"] = str(REPO_ROOT)
        server["env"] = {"PYTHONPATH": str(REPO_ROOT / "src")}
    rendered = destination_dir / "mcp_client_config.json"
    rendered.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return rendered


def _new_output_dir() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return REGRESSION_OUTPUT_ROOT / f"{stamp}-{uuid.uuid4().hex[:8]}"


def _render_output_path(part: str, output_dir: Path) -> str:
    # Join through Path so the result uses the platform's separator: a COM call on Windows gets a plain
    # "C:\...\name" path, not one that mixes in the manifest's forward slash.
    prefix = OUTPUT_DIR_PLACEHOLDER + "/"
    if part.startswith(prefix):
        return str(output_dir.joinpath(*part[len(prefix) :].split("/")))
    return part.replace(OUTPUT_DIR_PLACEHOLDER, str(output_dir))


def _scenario_command(command: list[str], destination_dir: Path, output_dir: Path | None = None) -> list[str]:
    """Render a scenario command for this run.

    "{output_dir}" in an argument becomes this run's output directory. The audit's template config is replaced
    with one rendered for this run. Every other argument is unchanged.
    """
    if output_dir is not None:
        command = [_render_output_path(part, output_dir) for part in command]
    if not command or command[0] != "mcp-config-audit" or "--config" not in command:
        return command
    index = command.index("--config") + 1
    if index >= len(command) or command[index] != MCP_AUDIT_TEMPLATE:
        return command
    rendered = _render_mcp_audit_config(REPO_ROOT / MCP_AUDIT_TEMPLATE, destination_dir)
    return [*command[:index], str(rendered), *command[index + 1 :]]


# A manifest is data supplied by the caller (including over MCP, where regression-run is advertised as
# non-mutating), so scenarios may only run the read-only and smoke commands the shipped manifest uses.
REGRESSION_ALLOWED_COMMANDS = frozenset(
    {
        "calc-smoke",
        "com-smoke",
        "convert-smoke",
        "mcp-catalog-drift",
        "mcp-config-audit",
        "mcp-smoke",
        "mcp-tools",
        "plan",
        "security-audit",
        "tasks",
        "writer-table-smoke",
    }
)


def load_regression_manifest(
    path: str | Path = DEFAULT_REGRESSION_MANIFEST,
) -> tuple[bool, dict[str, Any], list[dict[str, Any]]]:
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
    scratch = tempfile.TemporaryDirectory(prefix="wps-regression-")
    output_dir: Path | None = None
    for scenario in scenarios:
        command = scenario.get("command")
        if (
            not isinstance(command, list)
            or not command
            or not all(isinstance(part, str) for part in command)
            or command[0] not in REGRESSION_ALLOWED_COMMANDS
        ):
            exit_code, payload, raw_output = (
                1,
                {
                    "ok": False,
                    "summary": "Regression scenario command is not allowed.",
                    "errors": [
                        {
                            "code": "REGRESSION_COMMAND_NOT_ALLOWED",
                            "message": "Scenarios may only run the read-only and smoke commands used by the shipped manifest; nothing was executed.",
                            "command": command[0]
                            if isinstance(command, list) and command and isinstance(command[0], str)
                            else None,
                        }
                    ],
                },
                "",
            )
        else:
            if output_dir is None and any(OUTPUT_DIR_PLACEHOLDER in part for part in command):
                output_dir = _new_output_dir()
                output_dir.mkdir(parents=True, exist_ok=True)
            exit_code, payload, raw_output = _run_cli(_scenario_command(list(command), Path(scratch.name), output_dir))
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

    scratch.cleanup()
    passed_count = sum(1 for result in results if result["ok"])
    failed = [result for result in results if not result["ok"]]
    result = {
        "manifest_path": str(manifest_path),
        "version": manifest.get("version"),
        "profile": resolved_profile,
        "include_wps": include_wps,
        "output_dir": str(output_dir) if output_dir is not None else None,
        "scenario_count": len(results),
        "passed_count": passed_count,
        "failed_count": len(failed),
        "results": results,
    }
    errors = (
        []
        if not failed
        else [
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
    )
    return not failed, result, errors
