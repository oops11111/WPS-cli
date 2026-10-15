"""The one-command Windows check (P7-005): prerequisites, resumable eval runs and the results it writes."""

from __future__ import annotations

import importlib.util
import io
import json
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
        self.assertIn("| `task-a` | 3/3 | 4.0 (4, 4, 4) | 6 | 0 | 1 | `operation` |", text)
        self.assertIn("**3/3 tasks passed**", text)
        self.assertIn("| claude answers | ok | OK |", text)
        self.assertIn("cleanup: fixture closed; processes stopped 7", text)
        self.assertIn("error codes: DOCUMENT_HELD_OPEN", text)
        self.assertIn("nothing in this file was typed by hand", text)
        self.assertTrue((self.out / "summary.json").is_file())
        state = json.loads((self.out / "results.json").read_text(encoding="utf-8"))
        self.assertTrue(state["complete"])
        self.assertEqual(machine.process_calls, 2)  # before the run and after it

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

        with patch.object(windows_check.urllib.request, "urlopen", return_value=Response(json.dumps(release).encode())):
            url, digest = windows_check.release_wheel("0.4.0")
        self.assertEqual((url, digest), ("https://example.invalid/w.whl", "870dd38d"))


if __name__ == "__main__":
    unittest.main()
