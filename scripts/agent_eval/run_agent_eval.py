"""Run fixed tasks through the claude CLI against the wps-agent MCP server, then judge the workspace state.

The agent is the real `claude -p` process. Each task runs in its own workspace, which is also the MCP
server's working directory, so the server's state files live there. A task can list setup steps that
prepare the workspace before the agent starts (register, back up, change or hold the file, write an HTML
table). The judge reads the workspace state (documents, operations, backups, file hashes, output files)
and the agent's tool calls from the CLI transcript. It does not read the agent's reply.

Usage:
    python scripts/agent_eval/run_agent_eval.py [--tasks config/agent_eval_tasks.json] [--out artifacts/agent-eval] [--only ID] [--model MODEL] [--max-turns N] [--timeout SECONDS]

Exit code: 0 when every task passes, 1 when any fails, 2 when the claude CLI is not available.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
MCP_SERVER_NAME = "wps-agent"
ALLOWED_TOOLS = f"mcp__{MCP_SERVER_NAME}__*"

sys.path.insert(0, str(SRC_DIR))
from wps_ai_agent_cli.backups import create_backup, list_backups  # noqa: E402
from wps_ai_agent_cli.operations import get_operation  # noqa: E402
from wps_ai_agent_cli.sessions import (  # noqa: E402
    get_document,
    register_document,
    stable_document_id,
)

TOOL_PREFIX = f"mcp__{MCP_SERVER_NAME}__wps_agent_"
HTML_TABLE = (
    "<html><body><h2>Sales</h2><table>"
    "<tr><th>Region</th><th>Q1</th></tr><tr><td>North</td><td>120</td></tr><tr><td>South</td><td>95</td></tr>"
    "</table></body></html>"
)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


WRITER_FIXTURE_PARAGRAPHS = ("Quarterly report", "Status: DRAFT", "Owner: Finance")
PRESENTATION_FIXTURE_TEXTS = ("Quarterly review", "Status: DRAFT")


def write_fixture(workspace: Path, name: str) -> str:
    """Write the task's fixture, chosen by its suffix: .xlsx, .docx or .pptx."""
    path = workspace / name
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        from openpyxl import Workbook

        workbook = Workbook()
        workbook.active["A1"] = "seed"
        workbook.save(path)
    elif suffix == ".docx":
        from docx import Document

        document = Document()
        for text in WRITER_FIXTURE_PARAGRAPHS:
            document.add_paragraph(text)
        document.save(path)
    elif suffix == ".pptx":
        from pptx import Presentation
        from pptx.util import Inches

        presentation = Presentation()
        slide = presentation.slides.add_slide(presentation.slide_layouts[6])
        for index, text in enumerate(PRESENTATION_FIXTURE_TEXTS):
            box = slide.shapes.add_textbox(Inches(1), Inches(1 + index), Inches(8), Inches(1))
            box.text_frame.text = text
        presentation.save(path)
    else:
        raise ValueError(f"unsupported fixture type {suffix}")
    return file_sha256(path)


def document_text(path: Path) -> str:
    """All text in a .docx (paragraphs and tables) or .pptx (every shape), joined by newlines."""
    suffix = path.suffix.lower()
    if suffix == ".docx":
        from docx import Document

        document = Document(path)
        parts = [paragraph.text for paragraph in document.paragraphs]
        for table in document.tables:
            parts += [cell.text for row in table.rows for cell in row.cells]
        return "\n".join(parts)
    if suffix == ".pptx":
        from pptx import Presentation

        presentation = Presentation(path)
        return "\n".join(
            shape.text_frame.text for slide in presentation.slides for shape in slide.shapes if shape.has_text_frame
        )
    raise ValueError(f"unsupported document type {suffix}")


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


def hold_file(path: Path) -> tuple[Callable[[], None] | None, str | None]:
    """Hold the file so the server cannot read it, as WPS does with an open document.

    Returns (release, None), or (None, reason) when this machine cannot hold a file.
    """
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateFileW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        kernel32.CreateFileW.restype = wintypes.HANDLE
        # GENERIC_READ, no sharing, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL: every other open is refused.
        handle = kernel32.CreateFileW(str(path), 0x80000000, 0, None, 3, 0x80, None)
        if handle == wintypes.HANDLE(-1).value:
            return None, f"CreateFileW failed with error {ctypes.get_last_error()}"
        return (lambda: kernel32.CloseHandle(handle)), None
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return None, "running as root, which ignores file permissions, so the file cannot be held"
    mode = path.stat().st_mode
    path.chmod(0)
    return (lambda: path.chmod(mode)), None


def run_setup(
    steps: list[str], workspace: Path, fixture: Path, component: str
) -> tuple[str, Callable[[], None] | None, str | None]:
    """Prepare the workspace.

    Returns (hash of the file as the agent receives it, release for a held file, skip reason). The hash is
    taken before a hold, because a held file cannot be read; "hold" must therefore be the last step.
    """
    for step in steps:
        if step == "register":
            ok, record, errors = register_document(component, str(fixture), workspace)
            if not ok:
                raise RuntimeError(f"setup register failed: {errors}")
        elif step == "backup":
            document_id = stable_document_id(component, str(fixture))
            ok, _result, errors, _replayed = create_backup(document_id, "setup-backup", workspace=workspace)
            if not ok:
                raise RuntimeError(f"setup backup failed: {errors}")
        elif step == "modify":
            from openpyxl import load_workbook

            workbook = load_workbook(fixture)
            workbook.active["A1"] = "changed by mistake"
            workbook.save(fixture)
        elif step == "html_table":
            (workspace / "table.html").write_text(HTML_TABLE, encoding="utf-8")
        elif step == "hold":
            start_sha = file_sha256(fixture)
            release, reason = hold_file(fixture)
            if release is None:
                return start_sha, None, reason
            return start_sha, release, None
        else:
            raise ValueError(f"unknown setup step {step}")
    return file_sha256(fixture), None, None


def _error_codes(content: Any) -> list[str]:
    """Error codes from a wps-agent tool result, which is the CLI envelope as JSON text."""
    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    try:
        envelope = json.loads(content) if isinstance(content, str) else content
    except json.JSONDecodeError:
        return []
    if not isinstance(envelope, dict):
        return []
    return [str(error.get("code")) for error in envelope.get("errors") or [] if isinstance(error, dict)]


def parse_transcript(lines: list[str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return the final result event and every tool call, in order, from stream-json output."""
    result: dict[str, Any] = {}
    calls: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "result":
            result = event
            continue
        message = event.get("message") or {}
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        for block in content:
            if block.get("type") == "tool_use":
                call = {
                    "name": block.get("name"),
                    "input": block.get("input") or {},
                    "is_error": None,
                    "error_codes": [],
                }
                calls.append(call)
                by_id[block.get("id")] = call
            elif block.get("type") == "tool_result" and block.get("tool_use_id") in by_id:
                call = by_id[block["tool_use_id"]]
                call["error_codes"] = _error_codes(block.get("content"))
                call["is_error"] = bool(block.get("is_error")) or bool(call["error_codes"])
    return result, calls


def tool_metrics(calls: list[dict[str, Any]], expected_tools: list[str] | None = None) -> dict[str, Any]:
    """Counts for one run. With expected_tools, also the wps-agent calls to any other tool (off-path calls).

    Off-path calls are reported, not judged: a task passes or fails on its checks alone.
    """
    wps_calls = [call for call in calls if str(call["name"]).startswith(TOOL_PREFIX)]
    used = [str(call["name"]).removeprefix(TOOL_PREFIX) for call in wps_calls]
    metrics = {
        "wps_tool_calls": len(wps_calls),
        "wps_tool_errors": sum(bool(call["is_error"]) for call in wps_calls),
        "other_tool_calls": len(calls) - len(wps_calls),
        "tools_used": sorted(set(used)),
        "expected_tools": sorted(expected_tools) if expected_tools is not None else None,
        "off_path_calls": None,
        "off_path_tools": None,
    }
    if expected_tools is not None:
        off_path = [tool for tool in used if tool not in expected_tools]
        metrics["off_path_calls"] = len(off_path)
        metrics["off_path_tools"] = sorted(set(off_path))
    return metrics


def run_claude(
    prompt: str, mcp_config: Path, workspace: Path, model: str | None, max_turns: int, timeout: int
) -> dict[str, Any]:
    command = [
        "claude",
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",
        "--mcp-config",
        str(mcp_config),
        "--strict-mcp-config",
        "--allowedTools",
        ALLOWED_TOOLS,
        "--max-turns",
        str(max_turns),
    ]
    if model:
        command += ["--model", model]
    try:
        completed = subprocess.run(command, cwd=workspace, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ran": False, "error": f"timed out after {timeout}s"}
    payload, calls = parse_transcript(completed.stdout.splitlines())
    return {
        "ran": True,
        "exit_code": completed.returncode,
        "is_error": payload.get("is_error"),
        "num_turns": payload.get("num_turns"),
        "duration_ms": payload.get("duration_ms"),
        "total_cost_usd": payload.get("total_cost_usd"),
        "result_excerpt": str(payload.get("result", ""))[:500],
        "stderr_excerpt": completed.stderr[-500:],
        "tool_calls": calls,
    }


def _calls_to(calls: list[dict[str, Any]], tool: str) -> list[dict[str, Any]]:
    return [call for call in calls if call["name"] == TOOL_PREFIX + tool]


def judge(
    task: dict[str, Any],
    workspace: Path,
    fixture: Path,
    fixture_sha: str,
    component: str,
    seed_sha: str | None = None,
    calls: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Check the workspace state and tool calls the task asks for. A check never reads the agent's reply.

    fixture_sha is the file as the agent received it, after setup; seed_sha is the file before setup.
    """
    seed_sha = seed_sha or fixture_sha
    calls = calls or []
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
        elif kind == "file_matches_seed":
            passed = file_sha256(fixture) == seed_sha
            detail = "matches the seed" if passed else "differs from the seed"
        elif kind == "tool_called":
            matching = [
                call
                for call in _calls_to(calls, check["tool"])
                if all(call["input"].get(key) == value for key, value in check.get("input", {}).items())
            ]
            passed, detail = len(matching) >= check.get("min", 1), f"{len(matching)} matching call(s)"
        elif kind == "tool_not_called":
            count = len(_calls_to(calls, check["tool"]))
            passed, detail = count == 0, f"{count} call(s)"
        elif kind == "tool_error_seen":
            passed = any(check["code"] in call["error_codes"] for call in calls)
            detail = "seen" if passed else "not seen"
        elif kind == "max_tool_calls":
            count = tool_metrics(calls)["wps_tool_calls"]
            passed, detail = count <= check["count"], f"{count} wps-agent call(s)"
        elif kind == "file_text":
            path = workspace / check["path"]
            if not path.is_file():
                passed, detail = False, "file missing"
            else:
                text = document_text(path)
                missing = [item for item in check.get("contains", []) if item not in text]
                present = [item for item in check.get("absent", []) if item in text]
                passed = not missing and not present
                detail = "ok" if passed else {"missing": missing, "present": present}
        elif kind == "xlsx_cell":
            from openpyxl import load_workbook

            path = workspace / check["path"]
            if not path.is_file():
                passed, detail = False, "output missing"
            else:
                workbook = load_workbook(path, read_only=True)
                try:
                    value = workbook.worksheets[0][check["cell"]].value
                finally:
                    workbook.close()
                passed, detail = value == check["value"], value
        else:
            passed, detail = False, f"unknown check kind {kind}"
        results.append(
            {"kind": kind, "passed": passed, "detail": detail, **{k: v for k, v in check.items() if k != "kind"}}
        )
    return results


def wps_available(component: str) -> bool:
    """True when this machine has a registered WPS ProgID for the component (the project's own probe)."""
    from wps_ai_agent_cli.capabilities import probe_wps_capabilities

    selected = probe_wps_capabilities().get("components", {}).get(component, {}).get("selected_prog_id")
    return bool(selected)


def run_task(
    task: dict[str, Any],
    fixture_name: str,
    component: str,
    root: Path,
    model: str | None,
    max_turns: int,
    timeout: int,
    runner: Callable[..., dict[str, Any]] = run_claude,
    has_wps: Callable[[str], bool] = wps_available,
) -> dict[str, Any]:
    if task.get("requires_wps") and not has_wps(component):
        return {
            "id": task["id"],
            "passed": False,
            "skipped": f"needs WPS {component}, which is not available here",
            "agent": {},
            "checks": [],
        }
    workspace = root / task["id"]
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)
    fixture = workspace / fixture_name
    seed_sha = write_fixture(workspace, fixture_name)
    fixture_sha, release, skip_reason = run_setup(task.get("setup", []), workspace, fixture, component)
    if skip_reason:
        return {"id": task["id"], "passed": False, "skipped": skip_reason, "agent": {}, "checks": []}
    try:
        mcp_config = write_mcp_config(workspace)
        agent = runner(task["prompt"], mcp_config, workspace, model, max_turns, timeout)
    finally:
        if release is not None:
            release()
    calls = agent.get("tool_calls") or []
    checks = judge(task, workspace, fixture, fixture_sha, component, seed_sha=seed_sha, calls=calls)
    return {
        "id": task["id"],
        "passed": bool(agent.get("ran")) and all(check["passed"] for check in checks),
        "agent": agent,
        "metrics": tool_metrics(calls, task.get("expected_tools")),
        "checks": checks,
    }


def run_task_repeated(
    task: dict[str, Any],
    fixture_name: str,
    component: str,
    root: Path,
    model: str | None,
    max_turns: int,
    timeout: int,
    repeat: int = 1,
    min_passes: int = 1,
    runner: Callable[..., dict[str, Any]] = run_claude,
    has_wps: Callable[[str], bool] = wps_available,
) -> dict[str, Any]:
    """Run a task `repeat` times, each in its own workspace. It passes when at least `min_passes` runs pass.

    A skip (no WPS, or a file that cannot be held) does not depend on the run, so the first one ends the task.
    """
    runs = []
    for index in range(1, repeat + 1):
        result = run_task(
            task,
            fixture_name,
            component,
            root / f"run-{index}",
            model,
            max_turns,
            timeout,
            runner=runner,
            has_wps=has_wps,
        )
        if result.get("skipped"):
            return {"id": task["id"], "passed": False, "skipped": result["skipped"], "runs": []}
        runs.append(result)
    passes = sum(run["passed"] for run in runs)
    return {
        "id": task["id"],
        "passed": passes >= min_passes,
        "repeat": repeat,
        "min_passes": min_passes,
        "passes": passes,
        "pass_rate": passes / repeat,
        "metrics": {
            "wps_tool_calls": sum(run["metrics"]["wps_tool_calls"] for run in runs),
            "wps_tool_errors": sum(run["metrics"]["wps_tool_errors"] for run in runs),
            "off_path_calls": (
                sum(run["metrics"]["off_path_calls"] for run in runs) if "expected_tools" in task else None
            ),
            "off_path_tools": (
                sorted({tool for run in runs for tool in run["metrics"]["off_path_tools"]})
                if "expected_tools" in task
                else None
            ),
        },
        "runs": runs,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tasks", default=str(REPO_ROOT / "config" / "agent_eval_tasks.json"))
    parser.add_argument("--out", default=str(REPO_ROOT / "artifacts" / "agent-eval"))
    parser.add_argument("--only", action="append", default=[], help="Run only the task with this id (repeatable).")
    parser.add_argument("--model", default=None)
    parser.add_argument("--max-turns", type=int, default=15)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--repeat", type=int, default=1, help="Run each task this many times (default 1).")
    parser.add_argument(
        "--min-passes", type=int, default=None, help="Runs that must pass for a task to pass (default: all of them)."
    )
    args = parser.parse_args(argv)
    if args.repeat < 1:
        parser.error("--repeat must be at least 1")
    min_passes = args.repeat if args.min_passes is None else args.min_passes
    if not 1 <= min_passes <= args.repeat:
        parser.error("--min-passes must be between 1 and --repeat")

    if shutil.which("claude") is None:
        print("claude CLI not found on PATH.", file=sys.stderr)
        return 2

    spec = json.loads(Path(args.tasks).read_text(encoding="utf-8"))
    tasks = [task for task in spec["tasks"] if not args.only or task["id"] in args.only]
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    root = Path(args.out) / f"run-{stamp}"
    root.mkdir(parents=True, exist_ok=True)

    results = [
        run_task_repeated(
            task,
            task.get("fixture", spec["fixture"]),
            task.get("component", spec["component"]),
            root / "work",
            args.model,
            args.max_turns,
            args.timeout,
            repeat=args.repeat,
            min_passes=min_passes,
        )
        for task in tasks
    ]
    summary = summarize(results, stamp, args.model)
    artifact = root / "summary.json"
    artifact.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    for result in results:
        if result.get("skipped"):
            print(f"SKIP {result['id']}: {result['skipped']}")
            continue
        metrics = result.get("metrics", {})
        print(
            f"{'PASS' if result['passed'] else 'FAIL'} {result['id']} "
            f"({result['passes']}/{result['repeat']} runs passed, need {result['min_passes']}; "
            f"wps-agent calls {metrics.get('wps_tool_calls')}, errors {metrics.get('wps_tool_errors')}, "
            f"off-path calls {metrics.get('off_path_calls')})"
        )
        for index, run in enumerate(result["runs"], 1):
            label = f"  run {index}: " if result["repeat"] > 1 else ""
            for check in run["checks"]:
                print(f"    {label}{'ok ' if check['passed'] else 'BAD'} {check['kind']}: {check['detail']}")
    print(f"{summary['passed']}/{summary['total']} passed, {summary['skipped']} skipped; artifact: {artifact}")
    return 0 if summary["passed"] == summary["total"] else 1


def summarize(results: list[dict[str, Any]], stamp: str, model: str | None) -> dict[str, Any]:
    ran = [result for result in results if not result.get("skipped")]
    return {
        "generated_at": stamp,
        "claude_cli": "claude",
        "model": model or "CLI default",
        "passed": sum(result["passed"] for result in ran),
        "total": len(ran),
        "skipped": len(results) - len(ran),
        "wps_tool_calls": sum(result.get("metrics", {}).get("wps_tool_calls", 0) for result in ran),
        "wps_tool_errors": sum(result.get("metrics", {}).get("wps_tool_errors", 0) for result in ran),
        "off_path_calls": sum(result.get("metrics", {}).get("off_path_calls") or 0 for result in ran),
        "tasks_without_expected_tools": [
            result["id"] for result in ran if result.get("metrics", {}).get("off_path_calls") is None
        ],
        "results": results,
    }


if __name__ == "__main__":
    raise SystemExit(main())
