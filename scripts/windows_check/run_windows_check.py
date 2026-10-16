"""Run a Windows check with one command and write its results file (P7-005, Phase 7 exit criterion H3).

Phase 6 ran five Windows sessions by hand from a runbook. Every one of them hit something the runbook could not
catch in advance: a tag on the wrong commit, an exhausted API balance, WPS processes left running, a console
code page. This script checks those things before it starts, runs the check, and writes what it found in the
format the repository records results in.

Subcommands:

    prereq   Check the machine only: clean commit, real Python, claude answers, no WPS process running, the
             registered open commands unchanged, inspect-env. Exits 1 when a required check fails.
    eval     prereq, then run agent-evaluation tasks one at a time. Progress is saved after every task, so
             --resume after an interruption runs only the tasks that have no result yet.
    undo     prereq, then make a Writer and a Presentation selection replace fail its read-back inside this
             process (undo_injection.py), so that the undo in WPS (P7-001) runs on real WPS, and record the file
             hashes before the write, after it and after the undo.
    wheel    Download a released wheel, compare its SHA-256 with the one the Release reports, install it alone
             in a new virtual environment and run inspect-env and the safe regression profile outside the
             repository.

Each run writes RESULTS.md, results.json (and for eval the runner's summary.json) into one directory under
scripts/windows_check/results/, ready to commit.

Usage:
    python scripts/windows_check/run_windows_check.py prereq
    python scripts/windows_check/run_windows_check.py eval --only wps-open-writer-selection-replace --repeat 3 --min-passes 2
    python scripts/windows_check/run_windows_check.py eval --prefix wps-open- --repeat 3 --min-passes 2
    python scripts/windows_check/run_windows_check.py eval --resume scripts/windows_check/results/<dir>
    python scripts/windows_check/run_windows_check.py undo
    python scripts/windows_check/run_windows_check.py wheel --version 0.4.0
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path, PureWindowsPath
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_ROOT = REPO_ROOT / "scripts" / "windows_check" / "results"
REPOSITORY = "oops11111/WPS-cli"
OPEN_COMMAND_EXTENSIONS = (".docx", ".xlsx", ".pptx")


def load_undo_injection() -> Any:
    """undo_injection.py next to this script; it imports the package, which load_runner puts on sys.path."""
    path = Path(__file__).resolve().parent / "undo_injection.py"
    spec = importlib.util.spec_from_file_location("undo_injection", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_runner() -> Any:
    """The agent-eval runner, which is a script, not a package module."""
    path = REPO_ROOT / "scripts" / "agent_eval" / "run_agent_eval.py"
    spec = importlib.util.spec_from_file_location("run_agent_eval", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


# Windows PowerShell writes redirected output in the console code page; window titles came back garbled (P7-007).
POWERSHELL_UTF8 = "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false; "


def _run(command: list[str], timeout: int = 120, **kwargs: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        **kwargs,
    )


# ---------------------------------------------------------------------------------------------- the machine
class Machine:
    """What the checks ask of the machine. Tests replace it; on Windows it asks the real one."""

    def is_windows(self) -> bool:
        return os.name == "nt"

    def git(self, *args: str) -> str:
        return _run(["git", *args], cwd=REPO_ROOT).stdout.strip()

    def python_executable(self) -> str:
        return sys.executable

    def claude_reply(self) -> tuple[bool, str]:
        executable = shutil.which("claude")
        if executable is None:
            return False, "claude is not on PATH"
        try:
            completed = _run([executable, "-p", "Reply with the single word OK."], timeout=180)
        except subprocess.TimeoutExpired:
            return False, "claude did not answer within 180 s"
        reply = (completed.stdout or "").strip()
        if completed.returncode != 0 or not reply or reply.startswith("API Error"):
            return False, (reply or completed.stderr.strip() or f"exit code {completed.returncode}")[:300]
        return True, reply[:100]

    def wps_processes(self) -> list[dict[str, Any]]:
        script = (
            "Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(wps|et|wpp)\\.exe$' } | "
            "ForEach-Object { $p = Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue; "
            "[pscustomobject]@{ id = [int]$_.ProcessId; name = $_.Name; command_line = [string]$_.CommandLine; "
            "title = [string]$p.MainWindowTitle } } | ConvertTo-Json -Depth 3"
        )
        completed = _run(["powershell", "-NoProfile", "-Command", POWERSHELL_UTF8 + script], timeout=60)
        text = completed.stdout.strip()
        if not text:
            return []
        data = json.loads(text)
        return data if isinstance(data, list) else [data]

    def open_command(self, extension: str) -> str:
        return load_runner().registered_open_command(extension)

    def file_version(self, path: str) -> str:
        completed = _run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                POWERSHELL_UTF8 + f"(Get-Item -LiteralPath '{path}').VersionInfo.FileVersion",
            ],
            timeout=60,
        )
        return completed.stdout.strip()

    def inspect_env(self) -> dict[str, Any]:
        env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
        completed = _run([sys.executable, "-m", "wps_ai_agent_cli", "inspect-env"], timeout=180, env=env)
        return json.loads(completed.stdout)


def program_of(command: str) -> str:
    """The program of a registered open command such as "C:\\...\\wps.exe" "%1"."""
    command = command.strip()
    if command.startswith('"'):
        return command[1 : command.index('"', 1)]
    return command.split(" ", 1)[0]


# ------------------------------------------------------------------------------------------------- prereq
def check(name: str, ok: bool, detail: str, required: bool = True) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail, "required": required}


def prerequisites(machine: Machine, *, need_claude: bool, need_wps: bool) -> dict[str, Any]:
    """Everything the session needs before a check starts. Required checks that fail stop the run."""
    checks: list[dict[str, Any]] = []
    commit = machine.git("rev-parse", "--short", "HEAD")
    branch = machine.git("rev-parse", "--abbrev-ref", "HEAD")
    dirty = machine.git("status", "--porcelain", "--untracked-files=no")
    checks.append(
        check("commit", bool(commit) and not dirty, f"{commit} on {branch}" + (f"; changed: {dirty}" if dirty else ""))
    )
    python = machine.python_executable()
    checks.append(check("python", "WindowsApps" not in python, python))
    windows = machine.is_windows()
    checks.append(check("windows", windows, platform.platform() if windows else "not Windows", required=need_wps))
    info: dict[str, Any] = {"commit": commit, "branch": branch, "python": python, "platform": platform.platform()}
    if need_claude:
        ok, detail = machine.claude_reply()
        checks.append(check("claude answers", ok, detail))
    if need_wps and windows:
        processes = machine.wps_processes()
        listed = "; ".join(
            f"{item.get('name')} {item.get('id')} {item.get('title') or ''}".strip() for item in processes
        )
        checks.append(check("no WPS process running", not processes, listed or "none"))
        versions: dict[str, str] = {}
        for extension in OPEN_COMMAND_EXTENSIONS:
            try:
                command = machine.open_command(extension)
            except Exception as exc:  # noqa: BLE001 - reported as a failed check
                checks.append(check(f"open command {extension}", False, str(exc)))
                continue
            unchanged = "/automation" not in command.lower()
            checks.append(check(f"open command {extension}", unchanged, command))
            program = program_of(command)
            versions[PureWindowsPath(program).name] = machine.file_version(program)
        info["wps_versions"] = versions
        env = machine.inspect_env()
        progids = {
            name: (component or {}).get("selected_prog_id")
            for name, component in ((env.get("data") or {}).get("components") or {}).items()
        }
        found = len(progids) == 3 and all(progids.values())
        checks.append(check("inspect-env", bool(env.get("ok")) and found, json.dumps(progids or env.get("errors"))))
    passed = all(item["ok"] for item in checks if item["required"])
    return {"passed": passed, "checks": checks, "info": info}


def prerequisites_markdown(report: dict[str, Any]) -> list[str]:
    lines = ["## Prerequisites", "", "| Check | Result | Detail |", "| --- | --- | --- |"]
    for item in report["checks"]:
        result = "ok" if item["ok"] else ("FAILED" if item["required"] else "not required")
        detail = str(item["detail"]).replace("|", "\\|")
        lines.append(f"| {item['name']} | {result} | {detail} |")
    return [*lines, ""]


# --------------------------------------------------------------------------------------------------- eval
def eval_table(results: list[dict[str, Any]]) -> list[str]:
    """The table docs/AGENT_E2E_EVAL.md uses for Windows runs."""
    lines = [
        "| Task | Passes | Turns | `wps-agent` calls | Tool errors | `off_path_calls` | `off_path_tools` |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for result in results:
        if result.get("skipped"):
            lines.append(f"| `{result['id']}` | skipped | | | | | |")
            continue
        runs = result["runs"]
        turns = [run.get("agent", {}).get("num_turns") or 0 for run in runs]
        mean = sum(turns) / len(turns) if turns else 0
        metrics = result.get("metrics", {})
        tools = ", ".join(f"`{tool}`" for tool in metrics.get("off_path_tools") or [])
        lines.append(
            f"| `{result['id']}` | {result['passes']}/{result['repeat']} | {mean:.1f} ({', '.join(map(str, turns))}) "
            f"| {metrics.get('wps_tool_calls')} | {metrics.get('wps_tool_errors')} | {metrics.get('off_path_calls')} | {tools} |"
        )
    return lines


def run_details(results: list[dict[str, Any]]) -> list[str]:
    """Failed checks, setup failures, agent errors and cleanup, per run: what a review needs."""
    lines: list[str] = []
    for result in results:
        if result.get("skipped"):
            lines.append(f"- `{result['id']}` skipped: {result['skipped']}")
            continue
        for index, run in enumerate(result["runs"], 1):
            notes = []
            if run.get("setup_failed"):
                notes.append(f"setup failed: {run['setup_failed']}")
            if run.get("agent_error"):
                notes.append(f"agent did not run: {run['agent_error']}")
            failed = [
                f"{check['kind']} ({check.get('detail')})" for check in run.get("checks", []) if not check["passed"]
            ]
            if failed:
                notes.append("failed checks: " + "; ".join(failed))
            errors = sorted(
                {
                    code
                    for call in run.get("agent", {}).get("tool_calls") or []
                    for code in call.get("error_codes") or []
                }
            )
            if errors:
                notes.append("error codes: " + ", ".join(errors))
            if run.get("cleanup"):
                notes.append(f"cleanup: {run['cleanup']}")
            if notes:
                lines.append(
                    f"- `{result['id']}` run {index} ({'pass' if run['passed'] else 'FAIL'}): " + " | ".join(notes)
                )
    return lines or ["- Nothing to report."]


def write_results(
    directory: Path,
    title: str,
    prereq: dict[str, Any],
    body: list[str],
    payload: dict[str, Any],
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    info = prereq["info"]
    header = [
        f"# {title}",
        "",
        f"- Date: {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"- Commit: `{info.get('commit')}` on `{info.get('branch')}`",
        f"- Machine: {info.get('platform')}; Python {platform.python_version()}",
    ]
    if info.get("wps_versions"):
        header.append("- WPS: " + ", ".join(f"{name} {version}" for name, version in info["wps_versions"].items()))
    header.append("- Written by `scripts/windows_check/run_windows_check.py`; nothing in this file was typed by hand.")
    text = "\n".join([*header, "", *prerequisites_markdown(prereq), *body, ""])
    (directory / "RESULTS.md").write_text(text, encoding="utf-8")
    (directory / "results.json").write_text(
        json.dumps({"prerequisites": prereq, **payload}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return directory / "RESULTS.md"


def run_eval(args: argparse.Namespace, machine: Machine, runner: Any) -> int:
    if args.resume:
        directory = Path(args.resume)
        state = json.loads((directory / "results.json").read_text(encoding="utf-8"))
        settings = state["settings"]
        done = {result["id"]: result for result in state.get("results", [])}
    else:
        settings = {
            "only": args.only,
            "prefix": args.prefix,
            "repeat": args.repeat,
            "min_passes": args.min_passes or args.repeat,
            "model": args.model,
            "wps_launch": args.wps_launch,
            "tasks": args.tasks,
        }
        done = {}
        directory = None
    prereq = prerequisites(machine, need_claude=True, need_wps=True)
    if directory is None:
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        directory = Path(args.out or RESULTS_ROOT / f"{stamp}-{prereq['info'].get('commit')}-eval")
    if not prereq["passed"] and not args.force:
        write_results(
            directory, "Windows check stopped: prerequisites", prereq, [], {"settings": settings, "results": []}
        )
        print(f"Prerequisites failed; nothing was run. See {directory / 'RESULTS.md'}", file=sys.stderr)
        return 1

    runner.WPS_LAUNCH = settings["wps_launch"]
    spec = json.loads(Path(settings["tasks"]).read_text(encoding="utf-8"))
    prefixes = tuple(settings.get("prefix") or ())
    tasks = [
        task
        for task in spec["tasks"]
        if (not settings["only"] and not prefixes) or task["id"] in settings["only"] or task["id"].startswith(prefixes)
    ]
    results: list[dict[str, Any]] = [done[task["id"]] for task in tasks if task["id"] in done]
    # The task workspaces stay out of the results directory, which is meant to be committed.
    work = Path(tempfile.gettempdir()) / "wps-windows-check" / directory.name
    settings.setdefault("workspaces", str(work))
    for task in tasks:
        if task["id"] in done:
            print(f"kept {task['id']} from the earlier run")
            continue
        print(f"running {task['id']} x{settings['repeat']}")
        result = runner.run_task_repeated(
            task,
            task.get("fixture", spec["fixture"]),
            task.get("component", spec["component"]),
            work,
            settings["model"],
            args.max_turns,
            args.timeout,
            repeat=settings["repeat"],
            min_passes=settings["min_passes"],
        )
        results.append(result)
        # Saved after every task, so that --resume can carry on after an interruption.
        partial = {"settings": settings, "results": results, "complete": False}
        (directory).mkdir(parents=True, exist_ok=True)
        (directory / "results.json").write_text(
            json.dumps({"prerequisites": prereq, **partial}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    order = {task["id"]: index for index, task in enumerate(tasks)}
    results.sort(key=lambda result: order.get(result["id"], len(order)))
    summary = runner.summarize(results, dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"), settings["model"])
    (directory / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    leftover = machine.wps_processes() if machine.is_windows() else []
    command = ["eval"] + [f"--only {task_id}" for task_id in settings["only"]]
    command += [f"--prefix {prefix}" for prefix in prefixes]
    command += [f"--repeat {settings['repeat']}", f"--min-passes {settings['min_passes']}"]
    if settings["wps_launch"] != "default":
        command.append(f"--wps-launch {settings['wps_launch']}")
    body = [
        "## Agent evaluation",
        "",
        "```",
        "python scripts/windows_check/run_windows_check.py " + " ".join(command),
        "```",
        "",
        f"Claude Code CLI {_cli_version()}, model {settings['model'] or 'CLI default'}, launch mode `{settings['wps_launch']}`. "
        f"**{summary['passed']}/{summary['total']} tasks passed**, {summary['skipped']} skipped. "
        f"Each task passes with at least {settings['min_passes']} of {settings['repeat']} runs. "
        f"Task workspaces: `{work}`.",
        "",
        *eval_table(results),
        "",
        "### Runs",
        "",
        *run_details(results),
        "",
        "### WPS processes after the run",
        "",
        *(
            [
                f"- {item.get('name')} {item.get('id')} `{item.get('title') or ''}` {item.get('command_line') or ''}"
                for item in leftover
            ]
            or ["- None."]
        ),
    ]
    path = write_results(
        directory,
        "Windows agent evaluation",
        prereq,
        body,
        {"settings": settings, "results": results, "complete": True, "leftover_processes": leftover},
    )
    print(f"{summary['passed']}/{summary['total']} passed; results: {path}")
    return 0 if summary["passed"] == summary["total"] else 1


def _cli_version() -> str:
    executable = shutil.which("claude")
    if executable is None:
        return "not found"
    try:
        return _run([executable, "--version"], timeout=60).stdout.strip() or "unknown"
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


# -------------------------------------------------------------------------------------------------- wheel
def release_wheel(version: str) -> tuple[str, str]:
    """The wheel's download URL and the SHA-256 the Release lists for it."""
    name = f"wps_ai_agent_cli-{version}-py3-none-any.whl"
    api = f"https://api.github.com/repos/{REPOSITORY}/releases/tags/v{version}"
    request = urllib.request.Request(api, headers={"Accept": "application/vnd.github+json"})
    # Unauthenticated calls share a small hourly quota; the P7-009 run once got HTTP 403 rate limit exceeded.
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - a fixed https URL
        release = json.load(response)
    for asset in release.get("assets", []):
        if asset.get("name") == name:
            digest = str(asset.get("digest") or "")
            return asset["browser_download_url"], digest.removeprefix("sha256:")
    raise RuntimeError(f"Release v{version} has no asset {name}")


def venv_program(venv: Path, name: str) -> Path:
    folder = venv / ("Scripts" if os.name == "nt" else "bin")
    for candidate in (folder / f"{name}.exe", folder / name):
        if candidate.exists():
            return candidate
    return folder / name


def check_wheel(
    version: str, work: Path, *, wheel: Path | None = None, expected_sha: str | None = None
) -> dict[str, Any]:
    """Install only the wheel in a new venv and run it outside the repository, with no PYTHONPATH."""
    work.mkdir(parents=True, exist_ok=True)
    if wheel is None:
        url, listed = release_wheel(version)
        expected_sha = expected_sha or listed
        wheel = work / url.rsplit("/", 1)[-1]
        urllib.request.urlretrieve(url, wheel)  # noqa: S310 - the Release's https URL
    actual = hashlib.sha256(wheel.read_bytes()).hexdigest()
    venv = work / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    python = venv_program(venv, "python")
    install = _run([str(python), "-m", "pip", "install", "-q", str(wheel)], timeout=600, env=env)
    run_dir = work / "run"
    run_dir.mkdir(exist_ok=True)
    package = _run(
        [str(python), "-c", "import wps_ai_agent_cli as p; print(p.__version__); print(p.__file__)"],
        cwd=run_dir,
        env=env,
    )
    agent = str(venv_program(venv, "wps-agent"))
    inspect = _run([agent, "inspect-env"], timeout=300, cwd=run_dir, env=env)
    safe = _run(
        [agent, "regression-run", "--profile", "safe", "--artifact-dir", str(run_dir / "artifacts")],
        timeout=900,
        cwd=run_dir,
        env=env,
    )
    lines = package.stdout.split()
    inspect_data = json.loads(inspect.stdout) if inspect.stdout.strip() else {}
    safe_data = json.loads(safe.stdout) if safe.stdout.strip() else {}
    regression = (safe_data.get("data") or {}).get("regression") or {}
    return {
        "version": version,
        "wheel": str(wheel),
        "sha256": actual,
        "expected_sha256": expected_sha,
        "sha256_matches": bool(expected_sha) and actual.lower() == str(expected_sha).lower(),
        "installed": install.returncode == 0,
        "install_error": install.stderr.strip()[-500:] if install.returncode else "",
        "package_version": lines[0] if lines else None,
        "package_file": lines[1] if len(lines) > 1 else None,
        "inspect_env_ok": bool(inspect_data.get("ok")),
        "inspect_env_errors": inspect_data.get("errors"),
        "safe_ok": bool(safe_data.get("ok")),
        "safe_passed": regression.get("passed_count"),
        "safe_total": regression.get("scenario_count"),
        "safe_failed": regression.get("failed_count"),
        "manifest_path": regression.get("manifest_path"),
    }


def wheel_verdict(result: dict[str, Any]) -> tuple[bool, list[str]]:
    """Every condition of the wheel check, with the failed ones named."""
    conditions = {
        "SHA-256 matches the Release": result["sha256_matches"],
        "installed": result["installed"],
        f"version is {result['version']}": result["package_version"] == result["version"],
        "package loaded from site-packages": "site-packages" in str(result["package_file"] or ""),
        "inspect-env ok": result["inspect_env_ok"],
        "safe profile ok with no failures": result["safe_ok"] and result["safe_failed"] == 0,
        "manifest loaded from site-packages": "site-packages" in str(result["manifest_path"] or ""),
    }
    return all(conditions.values()), [f"- {'ok' if ok else 'FAILED'}: {name}" for name, ok in conditions.items()]


def run_wheel(args: argparse.Namespace, machine: Machine) -> int:
    prereq = prerequisites(machine, need_claude=False, need_wps=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    directory = Path(args.out or RESULTS_ROOT / f"{stamp}-wheel-{args.version}")
    if not prereq["passed"] and not args.force:
        write_results(directory, "Windows check stopped: prerequisites", prereq, [], {})
        print(f"Prerequisites failed; nothing was run. See {directory / 'RESULTS.md'}", file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory(prefix="wps-wheel-") as work:
        result = check_wheel(
            args.version,
            Path(work),
            wheel=Path(args.wheel) if args.wheel else None,
            expected_sha=args.sha256,
        )
    passed, conditions = wheel_verdict(result)
    body = [
        f"## Released wheel {args.version}",
        "",
        f"**{'Passed' if passed else 'Failed'}.**",
        "",
        *conditions,
        "",
        f"- SHA-256: `{result['sha256']}` (Release: `{result['expected_sha256']}`)",
        f"- Package: `{result['package_version']}` from `{result['package_file']}`",
        f"- inspect-env errors: {json.dumps(result['inspect_env_errors'])}",
        f"- Safe profile: {result['safe_passed']} of {result['safe_total']} passed, {result['safe_failed']} failed; "
        f"manifest `{result['manifest_path']}`",
    ]
    path = write_results(
        directory, f"Windows check of the {args.version} wheel", prereq, body, {"wheel": result, "passed": passed}
    )
    print(f"wheel {args.version}: {'passed' if passed else 'FAILED'}; results: {path}")
    return 0 if passed else 1


# --------------------------------------------------------------------------------------------------- undo
def _short(sha: str | None) -> str:
    return f"`{sha[:12]}`" if sha else "-"


def undo_table(results: list[dict[str, Any]], verdicts: dict[str, bool]) -> list[str]:
    lines = [
        "| Scenario | Result | Error codes | Before write | Before undo | After undo | Content matches backup | Cleanup |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for result in results:
        hashes = result.get("hashes") or {}
        rollback = result.get("rollback") or {}
        codes = ", ".join(f"`{code}`" for code in result.get("error_codes") or []) or "-"
        cleanup = str(result.get("cleanup") or "-").replace("|", "\\|")
        lines.append(
            f"| `{result['scenario']}` | {'pass' if verdicts[result['scenario']] else 'FAIL'} | {codes} "
            f"| {_short(hashes.get('before_write'))} | {_short(hashes.get('before_undo'))} "
            f"| {_short(hashes.get('after_undo'))} | {rollback.get('content_matches_backup')} | {cleanup} |"
        )
    return lines


def run_undo(args: argparse.Namespace, machine: Machine, runner: Any, injection: Any) -> int:
    prereq = prerequisites(machine, need_claude=False, need_wps=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    directory = Path(args.out or RESULTS_ROOT / f"{stamp}-{prereq['info'].get('commit')}-undo")
    scenarios = args.scenario or list(injection.SCENARIOS)
    settings = {"scenarios": scenarios, "wps_launch": args.wps_launch}
    if not prereq["passed"] and not args.force:
        write_results(directory, "Windows check stopped: prerequisites", prereq, [], {"settings": settings})
        print(f"Prerequisites failed; nothing was run. See {directory / 'RESULTS.md'}", file=sys.stderr)
        return 1
    runner.WPS_LAUNCH = args.wps_launch
    work = Path(tempfile.gettempdir()) / "wps-windows-check" / directory.name
    results = []
    for name in scenarios:
        print(f"running {name}")
        results.append(injection.run_scenario(name, runner, work))
    verdicts: dict[str, bool] = {}
    details: list[str] = []
    for result in results:
        passed, conditions = injection.verdict(result)
        verdicts[result["scenario"]] = passed
        result["passed"] = passed
        details += [f"### `{result['scenario']}`", "", *conditions, ""]
        rollback = result.get("rollback") or {}
        if rollback:
            details += [
                f"- rollback status `{rollback.get('status')}`, read back {json.dumps(rollback.get('read_back_text'), ensure_ascii=False)}",
                f"- WPS read back after the write (replaced by the injection): "
                f"{json.dumps(result.get('real_read_back_text'), ensure_ascii=False)}",
                "",
            ]
        for error in result.get("errors") or []:
            details.append(f"- `{error.get('code')}`: {error.get('message')}")
        if result.get("errors"):
            details.append("")
    leftover = machine.wps_processes() if machine.is_windows() else []
    passed_count = sum(verdicts.values())
    body = [
        "## Undo in WPS after an injected read-back failure",
        "",
        "```",
        "python scripts/windows_check/run_windows_check.py undo"
        + "".join(f" --scenario {name}" for name in args.scenario)
        + (f" --wps-launch {args.wps_launch}" if args.wps_launch != "default" else ""),
        "```",
        "",
        f"**{passed_count}/{len(results)} scenarios passed.** The write runs in WPS as usual; inside this process "
        "only its reported read-back is replaced, so the command rejects the write and undoes it in WPS. Hashes are "
        f"the file's SHA-256. Workspaces: `{work}`.",
        "",
        *undo_table(results, verdicts),
        "",
        *details,
        "### WPS processes after the run",
        "",
        *([f"- {item.get('name')} {item.get('id')} `{item.get('title') or ''}`" for item in leftover] or ["- None."]),
    ]
    path = write_results(
        directory,
        "Windows check of the undo in WPS",
        prereq,
        body,
        {"settings": settings, "results": results, "leftover_processes": leftover},
    )
    print(f"{passed_count}/{len(results)} passed; results: {path}")
    return 0 if passed_count == len(results) else 1


def run_prereq(args: argparse.Namespace, machine: Machine) -> int:
    report = prerequisites(machine, need_claude=not args.skip_claude, need_wps=True)
    for line in prerequisites_markdown(report):
        print(line)
    return 0 if report["passed"] else 1


def main(
    argv: list[str] | None = None, machine: Machine | None = None, runner: Any = None, injection: Any = None
) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    prereq = commands.add_parser("prereq", help="Check the machine only.")
    prereq.add_argument("--skip-claude", action="store_true", help="Do not ask claude to answer.")
    evaluation = commands.add_parser("eval", help="Run agent-evaluation tasks and write the results.")
    evaluation.add_argument("--only", action="append", default=[], help="Task id (repeatable); default: all tasks.")
    evaluation.add_argument(
        "--prefix",
        action="append",
        default=[],
        help="Run every task whose id starts with this (repeatable), for example wps-open-; adds to --only.",
    )
    evaluation.add_argument("--repeat", type=int, default=3)
    evaluation.add_argument("--min-passes", type=int, default=2)
    evaluation.add_argument("--model", default=None)
    evaluation.add_argument("--max-turns", type=int, default=15)
    evaluation.add_argument("--timeout", type=int, default=600)
    evaluation.add_argument("--wps-launch", choices=("default", "automation"), default="default")
    evaluation.add_argument("--tasks", default=str(REPO_ROOT / "config" / "agent_eval_tasks.json"))
    evaluation.add_argument("--resume", default=None, help="A results directory of an interrupted eval run.")
    evaluation.add_argument("--out", default=None, help="Results directory (default: under results/).")
    evaluation.add_argument("--force", action="store_true", help="Run even when a required prerequisite failed.")
    undo = commands.add_parser("undo", help="Make a selection write's read-back fail and check the undo in WPS.")
    undo.add_argument(
        "--scenario",
        action="append",
        default=[],
        choices=("writer-replace", "presentation-replace"),
        help="Scenario (repeatable); default: all.",
    )
    undo.add_argument("--wps-launch", choices=("default", "automation"), default="default")
    undo.add_argument("--out", default=None, help="Results directory (default: under results/).")
    undo.add_argument("--force", action="store_true", help="Run even when a required prerequisite failed.")
    wheel = commands.add_parser("wheel", help="Check a released wheel in a new virtual environment.")
    wheel.add_argument("--version", required=True)
    wheel.add_argument("--wheel", default=None, help="A local wheel instead of the Release's.")
    wheel.add_argument("--sha256", default=None, help="Expected SHA-256 (default: the one the Release lists).")
    wheel.add_argument("--out", default=None)
    wheel.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "eval" and not 1 <= args.min_passes <= args.repeat:
        parser.error("--min-passes must be between 1 and --repeat")
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    machine = machine or Machine()
    if args.command == "prereq":
        return run_prereq(args, machine)
    if args.command == "eval":
        return run_eval(args, machine, runner or load_runner())
    if args.command == "undo":
        runner = runner or load_runner()
        return run_undo(args, machine, runner, injection or load_undo_injection())
    return run_wheel(args, machine)


if __name__ == "__main__":
    raise SystemExit(main())
