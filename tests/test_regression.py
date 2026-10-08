import unittest
import json
import io
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from wps_ai_agent_cli.regression import (
    load_regression_manifest,
    list_regression_scenarios,
    _run_cli,
    run_regression_manifest,
)


class RegressionTests(unittest.TestCase):
    def test_nested_cli_runners_leave_process_stdout_unchanged(self):
        from wps_ai_agent_cli.performance import _run_cli as performance_runner

        for runner in (_run_cli, performance_runner):
            with self.subTest(runner=runner.__module__):
                started, release = Event(), Event()
                process_output = io.StringIO()

                def command(argv, output_stream=None):
                    started.set()
                    self.assertTrue(release.wait(5))
                    print(json.dumps({"ok": True}), file=output_stream)
                    return 0

                with patch("sys.stdout", process_output), patch("wps_ai_agent_cli.cli.run", side_effect=command):
                    with ThreadPoolExecutor(1) as executor:
                        future = executor.submit(runner, ["tasks"])
                        try:
                            self.assertTrue(started.wait(5))
                            self.assertIs(sys.stdout, process_output)
                            print("unrelated-output")
                        finally:
                            release.set()
                        result = future.result(timeout=5)
                self.assertTrue(result[1]["ok"])
                self.assertEqual(process_output.getvalue(), "unrelated-output\n")

    def test_load_manifest_and_filter_safe_scenarios(self):
        ok, manifest, errors = load_regression_manifest()
        scenarios = list_regression_scenarios(manifest, profile="safe")

        self.assertTrue(ok)
        self.assertEqual(errors, [])
        self.assertGreaterEqual(len(scenarios), 5)
        self.assertTrue(all(not scenario["requires_wps"] for scenario in scenarios))

    def test_release_gates_are_separate_from_safe_baseline(self):
        ok, manifest, errors = load_regression_manifest()
        self.assertTrue(ok, errors)
        safe = {item["id"] for item in list_regression_scenarios(manifest, profile="safe")}
        release = {item["id"] for item in list_regression_scenarios(manifest, profile="release")}
        self.assertEqual(release, {"local-handoff-summary", "regression-evidence", "regression-history"})
        self.assertFalse(safe & release)
        self.assertIn("sync-package-readiness", safe)

    def test_run_safe_regression_manifest(self):
        fixture = Path(__file__).parent / "fixtures" / "regression_contract.json"
        ok, result, errors = run_regression_manifest(fixture, profile="safe")

        self.assertTrue(ok)
        self.assertEqual(errors, [])
        self.assertEqual(result["scenario_count"], 2)
        self.assertEqual(result["failed_count"], 0)

    def test_failed_gate_is_reported_even_when_command_succeeds(self):
        fixture = Path(__file__).parent / "fixtures" / "regression_contract.json"
        manifest = json.loads(fixture.read_text(encoding="utf-8"))
        manifest["scenarios"][0]["required_checks"][0]["equals"] = "wrong-command"
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            ok, result, errors = run_regression_manifest(path)
        self.assertFalse(ok)
        self.assertEqual(result["failed_count"], 1)
        self.assertTrue(result["results"][0]["response_ok"])
        self.assertFalse(result["results"][0]["checks"][0]["passed"])
        self.assertEqual(errors[0]["code"], "REGRESSION_RUN_FAILED")

    def test_wps_scenarios_are_excluded_by_default(self):
        ok, manifest, _errors = load_regression_manifest()
        default_scenarios = list_regression_scenarios(manifest)
        all_scenarios = list_regression_scenarios(manifest, include_wps=True)

        self.assertTrue(ok)
        self.assertLess(len(default_scenarios), len(all_scenarios))
        self.assertTrue(any(scenario["requires_wps"] for scenario in all_scenarios))
        self.assertTrue(any(scenario["id"] == "writer-table-smoke" for scenario in all_scenarios))

    def test_run_cli_reports_exceptions_as_structured_failure(self):
        with patch("wps_ai_agent_cli.cli.run", side_effect=TimeoutError("slow command")):
            exit_code, payload, raw_output = _run_cli(["calc-smoke"])

        self.assertEqual(exit_code, 1)
        self.assertIsNotNone(payload)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["errors"][0]["exception_type"], "TimeoutError")
        self.assertIn("TimeoutError", raw_output)


if __name__ == "__main__":
    unittest.main()
