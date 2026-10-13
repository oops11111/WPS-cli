"""Run fixed tasks through the claude CLI against the wps-agent MCP server, then judge the workspace state.

The agent is the real `claude -p` process. Each task runs in its own workspace, which is also the MCP
server's working directory, so the server's state files live there. The judge reads that state
(documents, operations, backups, file hash). It does not read the agent's reply.

Usage:
    python scripts/agent_eval/run_agent_eval.py [--tasks config/agent_eval_tasks.json] [--out artifacts/agent-eval] [--only ID] [--model MODEL] [--max-turns N] [--timeout SECONDS]

Exit code: 0 when every task passes, 1 when any fails, 2 when the claude CLI is not available.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
MCP_SERVER_NAME = "wps-agent"
ALLOWED_TOOLS = f"mcp__{MCP_SERVER_NAME}__*"

sys.path.insert(0, str(SRC_DIR))
from wps_ai_agent_cli.backups import list_backups  # noqa: E402
from wps_ai_agent_cli.operations import get_operation  # noqa: E402
from wps_ai_agent_cli.sessions import get_document, stable_document_id  # noqa: E402


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_fixture(workspace: Path, name: str) -> str:
    from openpyxl import Workbook

    workbook = Workbook()
    workbook.active["A1"] = "seed"
    workbook.save(workspace / name)
    return file_sha256(workspace / name)


def write_mcp_config(workspace: Path) -> Path:
    config = {
        "mcpServers": {
            MCP_SERVER_NAME: {
                "command": sys.executable,
                "args": ["-m", "wps_ai_agent_cli", "mcp-server"],
                "cwd": str(workspace),
                "env": {"PYTHONPATH": str(SRC_DIR)},
            }
        }
    }
    path = workspace.parent / f"{workspace.name}.mcp.json"
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return path


def run_claude(prompt: str, mcp_config: Path, workspace: Path, model: str | None, max_turns: int, timeout: int) -> dict[str, Any]:
    command = [
        "claude", "-p", prompt,
        "--output-format", "json",
        "--mcp-config", str(mcp_config), "--strict-mcp-config",
        "--allowedTools", ALLOWED_TOOLS,
        "--max-turns", str(max_turns),
    ]
    if model:
        command += ["--model", model]
    try:
        completed = subprocess.run(command, cwd=workspace, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ran": False, "error": f"timed out after {timeout}s"}
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {}
    return {
        "ran": True,
        "exit_code": completed.returncode,
        "is_error": payload.get("is_error"),
        "num_turns": payload.get("num_turns"),
        "duration_ms": payload.get("duration_ms"),
        "total_cost_usd": payload.get("total_cost_usd"),
        "result_excerpt": str(payload.get("result", ""))[:500],
        "stderr_excerpt": completed.stderr[-500:],
    }


def judge(task: dict[str, Any], workspace: Path, fixture: Path, fixture_sha: str, component: str) -> list[dict[str, Any]]:
    """Check the workspace state the task asks for. A check never reads the agent's reply."""
    results = []
    document = get_document(stable_document_id(component, str(fixture)), workspace)
    document_id = document["document_id"] if document else None
    for check in task["checks"]:
        kind = check["kind"]
        if kind == "document_registered":
            passed, detail = document is not None, document_id or "not registered"
        elif kind == "operation_recorded":
            record = get_operation(check["request_id"], workspace)
            passed = bool(record) and record.get("command") == check["command"]
            detail = record.get("command") if record else "no record"
        elif kind == "no_operation":
            passed = get_operation(check["request_id"], workspace) is None
            detail = "none recorded" if passed else "a record exists"
        elif kind == "backup_count":
            count = 0
            if document_id:
                ok, data, _errors = list_backups(document_id, workspace)
                count = len(data.get("backups", [])) if ok else -1
            passed, detail = count == check["count"], count
        elif kind == "file_unchanged":
            passed = file_sha256(fixture) == fixture_sha
            detail = "unchanged" if passed else "changed"
        else:
            passed, detail = False, f"unknown check kind {kind}"
        results.append({"kind": kind, "passed": passed, "detail": detail, **{k: v for k, v in check.items() if k != "kind"}})
    return results


def run_task(task: dict[str, Any], fixture_name: str, component: str, root: Path, model: str | None,
             max_turns: int, timeout: int, runner: Callable[..., dict[str, Any]] = run_claude) -> dict[str, Any]:
    workspace = root / task["id"]
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)
    fixture_sha = write_fixture(workspace, fixture_name)
    mcp_config = write_mcp_config(workspace)
    agent = runner(task["prompt"], mcp_config, workspace, model, max_turns, timeout)
    checks = judge(task, workspace, workspace / fixture_name, fixture_sha, component)
    return {
        "id": task["id"],
        "passed": bool(agent.get("ran")) and all(check["passed"] for check in checks),
        "agent": agent,
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tasks", default=str(REPO_ROOT / "config" / "agent_eval_tasks.json"))
    parser.add_argument("--out", default=str(REPO_ROOT / "artifacts" / "agent-eval"))
    parser.add_argument("--only", action="append", default=[], help="Run only the task with this id (repeatable).")
    parser.add_argument("--model", default=None)
    parser.add_argument("--max-turns", type=int, default=15)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args(argv)

    if shutil.which("claude") is None:
        print("claude CLI not found on PATH.", file=sys.stderr)
        return 2

    spec = json.loads(Path(args.tasks).read_text(encoding="utf-8"))
    tasks = [task for task in spec["tasks"] if not args.only or task["id"] in args.only]
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    root = Path(args.out) / f"run-{stamp}"
    root.mkdir(parents=True, exist_ok=True)

    results = [run_task(task, spec["fixture"], spec["component"], root / "work", args.model, args.max_turns, args.timeout) for task in tasks]
    summary = {
        "generated_at": stamp,
        "claude_cli": "claude",
        "model": args.model or "CLI default",
        "passed": sum(result["passed"] for result in results),
        "total": len(results),
        "results": results,
    }
    artifact = root / "summary.json"
    artifact.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    for result in results:
        status = "PASS" if result["passed"] else "FAIL"
        print(f"{status} {result['id']}")
        for check in result["checks"]:
            print(f"    {'ok ' if check['passed'] else 'BAD'} {check['kind']}: {check['detail']}")
    print(f"{summary['passed']}/{summary['total']} passed; artifact: {artifact}")
    return 0 if summary["passed"] == summary["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
