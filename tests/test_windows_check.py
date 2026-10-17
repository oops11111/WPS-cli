"""The one-command Windows check (P7-005): prerequisites, resumable eval runs and the results it writes."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "run_windows_check", REPO_ROOT / "scripts" / "windows_check" / "run_windows_check.py"
)
windows_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(windows_check)

GOOD_ENV = {
    "ok": True,
    "errors": [],
    "data": {
        "components": {
            "writer": {"selected_prog_id": "kwps.Application"},
            "spreadsheets": {"selected_prog_id": "ket.Application"},
            "presentation": {"selected_prog_id": "kwpp.Application"},
        }
    },
}


class FakeMachine(windows_check.Machine):
    """A Windows machine that is ready, unless a test changes one answer."""

    def __init__(self, **overrides):
        self.answers = {
            "windows": True,
            "dirty": "",
            "python": r"C:\Python312\python.exe",
            "claude": (True, "OK"),
            "processes": [],
            "open": {
                ".docx": r'"C:\WPS\office6\wps.exe" "%1"',
                ".xlsx": r'"C:\WPS\office6\et.exe" "%1"',
                ".pptx": r'"C:\WPS\office6\wpp.exe" "%1"',
            },
            "env": GOOD_ENV,
            "package": {"version": "0.9.0", "file": r"C:\repo\src\wps_ai_agent_cli\__init__.py"},
            **overrides,
        }
        self.process_calls = 0

    def is_windows(self):
        return self.answers["windows"]

    def git(self, *args):
        if args[:1] == ("status",):
            return self.answers["dirty"]
        return "main" if "--abbrev-ref" in args else "abc1234"

    def python_executable(self):
        return self.answers["python"]

    def claude_reply(self):
        return self.answers["claude"]

    def wps_processes(self):
        self.process_calls += 1
        return self.answers["processes"]

    def open_command(self, extension):
        return self.answers["open"][extension]

    def file_version(self, path):
        return "12.8.2.18913"

    def inspect_env(self):
        return self.answers["env"]

    def package(self):
        return self.answers["package"]


def failed(report):
    return [item["name"] for item in report["checks"] if item["required"] and not item["ok"]]


class PrerequisiteTests(unittest.TestCase):
    def test_a_ready_machine_passes_and_records_the_wps_version(self):
        report = windows_check.prerequisites(FakeMachine(), need_claude=True, need_wps=True)
        self.assertTrue(report["passed"], report)
        self.assertEqual(report["info"]["commit"], "abc1234")
        self.assertEqual(report["info"]["wps_versions"]["wps.exe"], "12.8.2.18913")

    def test_each_problem_phase_6_hit_by_hand_stops_the_run(self):
        cases = {
            "commit": {"dirty": " M src/x.py"},
            "python": {"python": r"C:\Users\a\AppData\Local\Microsoft\WindowsApps\python.exe"},
            "claude answers": {"claude": (False, "API Error: 402 Insufficient Balance")},
            "no WPS process running": {"processes": [{"name": "wps.exe", "id": 7, "title": "report.docx"}]},
            "open command .docx": {
                "open": {
                    ".docx": r'"C:\WPS\office6\wps.exe" /Automation "%1"',
                    ".xlsx": r'"C:\WPS\office6\et.exe" "%1"',
                    ".pptx": r'"C:\WPS\office6\wpp.exe" "%1"',
                }
            },
            "inspect-env": {
                "env": {**GOOD_ENV, "data": {"components": {"writer": {"selected_prog_id": None}}}},
            },
        }
        for name, override in cases.items():
            with self.subTest(check=name):
                report = windows_check.prerequisites(FakeMachine(**override), need_claude=True, need_wps=True)
                self.assertFalse(report["passed"])
                self.assertEqual(failed(report), [name])

    def test_claude_is_not_asked_when_the_check_does_not_need_it(self):
        machine = FakeMachine(claude=(False, "never asked"))
        report = windows_check.prerequisites(machine, need_claude=False, need_wps=True)
        self.assertTrue(report["passed"], report)

    def test_a_machine_that_is_not_windows_fails_a_check_that_needs_wps(self):
        report = windows_check.prerequisites(FakeMachine(windows=False), need_claude=False, need_wps=True)
        self.assertEqual(failed(report), ["windows"])

    def test_the_package_under_test_is_recorded_and_checked_only_with_installed(self):
        report = windows_check.prerequisites(FakeMachine(), need_claude=False, need_wps=True)
        self.assertEqual(report["info"]["package"]["version"], "0.9.0")
        self.assertNotIn("installed package", [item["name"] for item in report["checks"]])
        site = r"C:\Users\clean\venv\Lib\site-packages\wps_ai_agent_cli\__init__.py"
        with patch.dict(os.environ, {"WPS_AGENT_USE_INSTALLED": "1"}):
            report = windows_check.prerequisites(FakeMachine(), need_claude=False, need_wps=True)
            self.assertEqual(failed(report), ["installed package"])
            machine = FakeMachine(package={"version": "0.9.0", "file": site})
            report = windows_check.prerequisites(machine, need_claude=False, need_wps=True)
            self.assertTrue(report["passed"], report)

    def test_installed_sets_the_switch_the_eval_runner_reads(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("WPS_AGENT_USE_INSTALLED", None)
            with patch.object(windows_check, "run_prereq", return_value=0) as run:
                self.assertEqual(windows_check.main(["--installed", "prereq", "--skip-claude"]), 0)
            self.assertEqual(os.environ.get("WPS_AGENT_USE_INSTALLED"), "1")
            self.assertTrue(run.called)

    def test_the_program_of_an_open_command(self):
        self.assertEqual(windows_check.program_of(r'"C:\a b\wps.exe" "%1"'), r"C:\a b\wps.exe")
        self.assertEqual(windows_check.program_of(r"C:\WPS\et.exe %1"), r"C:\WPS\et.exe")


def task_result(task_id, passes=3, repeat=3, **run_extra):
    run = {
        "passed": True,
        "agent": {"num_turns": 4, "tool_calls": [{"name": "x", "error_codes": ["DOCUMENT_HELD_OPEN"]}]},
        "checks": [{"kind": "file_text", "passed": True, "detail": {}}],
        "cleanup": "fixture closed; processes stopped 7",
        **run_extra,
    }
    return {
        "id": task_id,
        "passed": passes >= 2,
        "repeat": repeat,
        "min_passes": 2,
        "passes": passes,
        "metrics": {"wps_tool_calls": 6, "wps_tool_errors": 0, "off_path_calls": 1, "off_path_tools": ["operation"]},
        "runs": [run] * repeat,
    }


class FakeRunner:
    WPS_LAUNCH = "default"

    def __init__(self, fail_on=None):
        self.ran = []
        self.fail_on = fail_on

    def run_task_repeated(self, task, fixture, component, root, model, max_turns, timeout, repeat, min_passes):
        if task["id"] == self.fail_on:
            raise KeyboardInterrupt("interrupted")
        self.ran.append(task["id"])
        return task_result(task["id"])

    def summarize(self, results, stamp, model):
        ran = [result for result in results if not result.get("skipped")]
        return {
            "passed": sum(result["passed"] for result in ran),
            "total": len(ran),
            "skipped": len(results) - len(ran),
            "results": results,
        }


class EvalTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.tasks = self.dir / "tasks.json"
        self.tasks.write_text(
            json.dumps(
                {
                    "fixture": "book.xlsx",
                    "component": "spreadsheets",
                    "tasks": [{"id": "task-a"}, {"id": "task-b"}, {"id": "task-c"}],
                }
            ),
            encoding="utf-8",
        )
        self.out = self.dir / "results"
        for patcher in (
            patch.object(windows_check, "_cli_version", return_value="2.1.295"),
            patch("sys.stdout", new_callable=io.StringIO),
            patch("sys.stderr", new_callable=io.StringIO),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_eval(self, *extra, machine=None, runner=None):
        argv = ["eval", "--tasks", str(self.tasks), "--out", str(self.out), *extra]
        return windows_check.main(argv, machine=machine or FakeMachine(), runner=runner or FakeRunner())

    def test_a_run_writes_the_results_in_the_repository_format(self):
        machine = FakeMachine()
        self.assertEqual(self.run_eval(machine=machine), 0)
        text = (self.out / "RESULTS.md").read_text(encoding="utf-8")
        self.assertIn("| `task-a` | 3/3 | 4.0 (4, 4, 4) | 6 | 0 |  | 1 |  | `operation` |", text)
        self.assertIn("**3/3 tasks passed**", text)
        self.assertIn("| claude answers | ok | OK |", text)
        self.assertIn("cleanup: fixture closed; processes stopped 7", text)
        self.assertIn("error codes: DOCUMENT_HELD_OPEN", text)
        self.assertIn("nothing in this file was typed by hand", text)
        self.assertTrue((self.out / "summary.json").is_file())
        state = json.loads((self.out / "results.json").read_text(encoding="utf-8"))
        self.assertTrue(state["complete"])
        self.assertEqual(machine.process_calls, 2)  # before the run and after it

    def test_without_a_filter_every_task_in_the_repository_runs(self):
        # P12-001: M1 runs all tasks of config/agent_eval_tasks.json in one invocation.
        tasks_file = Path(windows_check.__file__).resolve().parents[2] / "config" / "agent_eval_tasks.json"
        spec = json.loads(tasks_file.read_text(encoding="utf-8"))
        runner = FakeRunner()
        argv = ["eval", "--tasks", str(tasks_file), "--out", str(self.out)]
        self.assertEqual(windows_check.main(argv, machine=FakeMachine(), runner=runner), 0)
        self.assertEqual(runner.ran, [task["id"] for task in spec["tasks"]])
        self.assertEqual(len(runner.ran), 34)
        self.assertGreater(sum(not task_id.startswith("wps-open-") for task_id in runner.ran), 0)

    def test_failed_prerequisites_run_nothing_unless_forced(self):
        runner = FakeRunner()
        machine = FakeMachine(claude=(False, "API Error: 402 Insufficient Balance"))
        self.assertEqual(self.run_eval(machine=machine, runner=runner), 1)
        self.assertEqual(runner.ran, [])
        self.assertIn("402 Insufficient Balance", (self.out / "RESULTS.md").read_text(encoding="utf-8"))

        forced = FakeRunner()
        self.run_eval("--force", machine=machine, runner=forced)
        self.assertEqual(forced.ran, ["task-a", "task-b", "task-c"])

    def test_an_interrupted_run_resumes_with_only_the_tasks_left(self):
        with self.assertRaises(KeyboardInterrupt):
            self.run_eval(runner=FakeRunner(fail_on="task-b"))
        state = json.loads((self.out / "results.json").read_text(encoding="utf-8"))
        self.assertFalse(state["complete"])
        self.assertEqual([result["id"] for result in state["results"]], ["task-a"])

        resumed = FakeRunner()
        code = windows_check.main(["eval", "--resume", str(self.out)], machine=FakeMachine(), runner=resumed)
        self.assertEqual(code, 0)
        self.assertEqual(resumed.ran, ["task-b", "task-c"])
        final = json.loads((self.out / "results.json").read_text(encoding="utf-8"))
        self.assertEqual([result["id"] for result in final["results"]], ["task-a", "task-b", "task-c"])
        self.assertTrue(final["complete"])

    def test_only_and_the_runner_settings_are_passed_through(self):
        runner = FakeRunner()
        self.run_eval("--only", "task-c", "--wps-launch", "automation", runner=runner)
        self.assertEqual(runner.ran, ["task-c"])
        self.assertEqual(runner.WPS_LAUNCH, "automation")
        self.assertIn("--wps-launch automation", (self.out / "RESULTS.md").read_text(encoding="utf-8"))

    def test_a_prefix_selects_every_task_whose_id_starts_with_it(self):
        runner = FakeRunner()
        self.run_eval("--prefix", "task-b", "--only", "task-a", runner=runner)
        self.assertEqual(runner.ran, ["task-a", "task-b"])
        self.assertIn("--only task-a --prefix task-b", (self.out / "RESULTS.md").read_text(encoding="utf-8"))

    def test_documents_wps_had_open_outside_the_workspaces_are_listed_once_with_their_runs(self):
        restored = {"component": "spreadsheets", "name": "预算.xlsx", "full_name": r"D:\上次\预算.xlsx"}

        class Restoring(FakeRunner):
            def run_task_repeated(self, task, *args, **kwargs):
                self.ran.append(task["id"])
                outside = [restored] if task["id"] == "task-a" else []
                return task_result(task["id"], documents_outside=outside)

        self.run_eval(runner=Restoring())
        text = (self.out / "RESULTS.md").read_text(encoding="utf-8")
        self.assertIn("WPS also had open: `D:\\上次\\预算.xlsx` (spreadsheets)", text)
        self.assertIn("- `D:\\上次\\预算.xlsx` (spreadsheets): 3 runs (task-a run 1, task-a run 2, task-a run 3)", text)

    def test_no_documents_outside_the_workspaces_is_said(self):
        self.run_eval()
        text = (self.out / "RESULTS.md").read_text(encoding="utf-8")
        section = text.split("### Documents WPS had open outside the task workspaces")[1]
        self.assertIn("- None.", section.split("###")[0])

    def test_writes_that_did_not_verify_are_listed_per_run(self):
        class Unverified(FakeRunner):
            def run_task_repeated(self, task, *args, **kwargs):
                self.ran.append(task["id"])
                calls = [
                    {
                        "name": "mcp__wps-agent__wps_agent_writer_selection_insert",
                        "error_codes": [],
                        "verified_state": {"passed": None, "check": "not compared (no reader for .doc)"},
                    }
                ]
                return task_result(task["id"], agent={"num_turns": 4, "tool_calls": calls})

        self.run_eval(runner=Unverified())
        text = (self.out / "RESULTS.md").read_text(encoding="utf-8")
        self.assertIn(
            "not verified: writer_selection_insert verified_state.passed None: not compared (no reader for .doc)", text
        )
        self.assertIn("writes whose verified_state.passed is not true**", text)

    def test_wrong_tool_calls_are_shown_per_task_and_in_total(self):
        class Wrong(FakeRunner):
            def run_task_repeated(self, task, *args, **kwargs):
                self.ran.append(task["id"])
                result = task_result(task["id"])
                result["metrics"] = {**result["metrics"], "wrong_tool_calls": 2 if task["id"] == "task-b" else 0}
                return result

            def summarize(self, results, stamp, model):
                summary = super().summarize(results, stamp, model)
                summary["wrong_tool_calls"] = sum(r["metrics"]["wrong_tool_calls"] for r in results)
                return summary

        self.run_eval(runner=Wrong())
        text = (self.out / "RESULTS.md").read_text(encoding="utf-8")
        self.assertIn("| `task-b` | 3/3 | 4.0 (4, 4, 4) | 6 | 0 | 2 | 1 |  | `operation` |", text)
        self.assertIn("| `task-a` | 3/3 | 4.0 (4, 4, 4) | 6 | 0 | 0 | 1 |  | `operation` |", text)
        self.assertIn("**2 wrong-tool calls**", text)

    def test_leftover_wps_processes_are_listed(self):
        class Leftover(FakeMachine):
            def wps_processes(self):
                self.process_calls += 1
                if self.process_calls == 1:
                    return []
                return [{"name": "wps.exe", "id": 22416, "title": "report.docx", "command_line": "wps.exe x"}]

        self.run_eval(machine=Leftover())
        self.assertIn("wps.exe 22416 `report.docx`", (self.out / "RESULTS.md").read_text(encoding="utf-8"))

    def test_failed_runs_list_their_failed_checks_setup_and_agent_errors(self):
        result = task_result("task-x", passes=1)
        result["runs"] = [
            {**result["runs"][0], "passed": False, "setup_failed": "select_text: text_not_found"},
            {
                **result["runs"][0],
                "passed": False,
                "agent_error": "API Error: 402",
                "checks": [{"kind": "operation_recorded", "passed": False, "detail": "no record"}],
            },
        ]
        lines = "\n".join(windows_check.run_details([result, {"id": "task-y", "skipped": "needs WPS"}]))
        self.assertIn("run 1 (FAIL): setup failed: select_text: text_not_found", lines)
        self.assertIn("agent did not run: API Error: 402", lines)
        self.assertIn("failed checks: operation_recorded (no record)", lines)
        self.assertIn("`task-y` skipped: needs WPS", lines)


class WheelTests(unittest.TestCase):
    def result(self, **overrides):
        return {
            "version": "0.4.0",
            "sha256_matches": True,
            "installed": True,
            "package_version": "0.4.0",
            "package_file": r"C:\t\venv\Lib\site-packages\wps_ai_agent_cli\__init__.py",
            "inspect_env_ok": True,
            "safe_ok": True,
            "safe_failed": 0,
            "manifest_path": r"C:\t\venv\Lib\site-packages\wps_ai_agent_cli\resources\regression_manifest.json",
            **overrides,
        }

    def test_the_verdict_needs_every_condition(self):
        passed, _lines = windows_check.wheel_verdict(self.result())
        self.assertTrue(passed)
        cases = {
            "SHA-256 matches the Release": {"sha256_matches": False},
            "version is 0.4.0": {"package_version": "0.3.0"},
            "package loaded from site-packages": {"package_file": r"C:\repo\src\wps_ai_agent_cli\__init__.py"},
            "safe profile ok with no failures": {"safe_failed": 1},
            "manifest loaded from site-packages": {"manifest_path": r"C:\repo\config\regression_manifest.json"},
        }
        for name, override in cases.items():
            with self.subTest(condition=name):
                passed, lines = windows_check.wheel_verdict(self.result(**override))
                self.assertFalse(passed)
                self.assertIn(f"- FAILED: {name}", lines)

    def test_the_release_digest_is_the_expected_sha(self):
        release = {
            "assets": [
                {"name": "wps_ai_agent_cli-0.4.0.tar.gz", "digest": "sha256:aa"},
                {
                    "name": "wps_ai_agent_cli-0.4.0-py3-none-any.whl",
                    "browser_download_url": "https://example.invalid/w.whl",
                    "digest": "sha256:870dd38d",
                },
            ]
        }

        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        with (
            patch.object(
                windows_check.urllib.request, "urlopen", return_value=Response(json.dumps(release).encode())
            ) as urlopen,
            patch.dict(windows_check.os.environ, {"GITHUB_TOKEN": "t0ken"}),
        ):
            url, digest = windows_check.release_wheel("0.4.0")
        self.assertEqual((url, digest), ("https://example.invalid/w.whl", "870dd38d"))
        # A token, when there is one, avoids the unauthenticated quota that once failed the P7-009 run.
        self.assertEqual(urlopen.call_args.args[0].get_header("Authorization"), "Bearer t0ken")


class PypiWheelTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.work = Path(tmp.name)

    def completed(self, command, stdout="", returncode=0):
        import subprocess

        return subprocess.CompletedProcess(command, returncode, stdout=stdout, stderr="")

    def test_pip_downloads_the_exact_version_from_pypi_only(self):
        def fake(command, timeout=120, **kwargs):
            target = Path(command[command.index("-d") + 1])
            (target / "wps_ai_agent_cli-0.9.0-py3-none-any.whl").write_bytes(b"wheel")
            return self.completed(command)

        with patch.object(windows_check, "_run", side_effect=fake) as run:
            wheel = windows_check.pypi_wheel("0.9.0", self.work)
        command = run.call_args.args[0]
        self.assertEqual(wheel.name, "wps_ai_agent_cli-0.9.0-py3-none-any.whl")
        self.assertIn("wps-ai-agent-cli==0.9.0", command)
        self.assertEqual(command[command.index("--index-url") + 1], "https://pypi.org/simple")
        self.assertIn("--no-deps", command)

    def test_a_version_missing_on_pypi_says_so(self):
        with patch.object(windows_check, "_run", return_value=self.completed([], returncode=1)):
            with self.assertRaisesRegex(RuntimeError, "could not download wps-ai-agent-cli==0.9.0 from PyPI"):
                windows_check.pypi_wheel("0.9.0", self.work)

    def test_the_pypi_wheel_is_checked_against_the_github_release(self):
        import hashlib

        wheel = self.work / "pypi" / "wps_ai_agent_cli-0.9.0-py3-none-any.whl"
        wheel.parent.mkdir()
        wheel.write_bytes(b"the wheel")
        digest = hashlib.sha256(b"the wheel").hexdigest()

        def fake(command, timeout=120, **kwargs):
            if "-c" in command:
                return self.completed(command, "0.9.0\nC:/venv/Lib/site-packages/wps_ai_agent_cli/__init__.py\n")
            if "inspect-env" in command:
                return self.completed(command, json.dumps({"ok": True, "errors": []}))
            if "regression-run" in command:
                regression = {
                    "passed_count": 7,
                    "scenario_count": 7,
                    "failed_count": 0,
                    "manifest_path": "site-packages/m",
                }
                return self.completed(command, json.dumps({"ok": True, "data": {"regression": regression}}))
            return self.completed(command)

        with (
            patch.object(windows_check, "release_wheel", return_value=("https://example.invalid/w.whl", digest)),
            patch.object(windows_check, "pypi_wheel", return_value=wheel) as download,
            patch.object(windows_check.subprocess, "run"),
            patch.object(windows_check, "_run", side_effect=fake),
        ):
            result = windows_check.check_wheel("0.9.0", self.work, source="pypi")
        download.assert_called_once_with("0.9.0", self.work)
        self.assertEqual(result["source"], "pypi")
        self.assertTrue(result["sha256_matches"])
        self.assertEqual(result["expected_sha256"], digest)
        passed, _lines = windows_check.wheel_verdict(result)
        self.assertTrue(passed)


if __name__ == "__main__":
    unittest.main()
