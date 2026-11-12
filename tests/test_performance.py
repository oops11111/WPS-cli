import json
import unittest
from unittest.mock import patch

from wps_ai_agent_cli.performance import (
    MCP_BASELINE_EXPECTED_TOOL_COUNT,
    PERFORMANCE_BASELINE_COMMANDS,
    _run_cli,
    capture_performance_baseline,
)


class PerformanceBaselineTests(unittest.TestCase):
    def test_capture_performance_baseline_uses_safe_commands(self):
        def completed(command):
            payload = {"ok": True, "command": command[0], "validation": {"status": "passed"}}
            return 0, payload, json.dumps(payload), 2.5

        with patch("wps_ai_agent_cli.performance._run_cli", side_effect=completed) as runner:
            ok, result, errors = capture_performance_baseline()
        self.assertEqual(
            [call.args[0] for call in runner.call_args_list],
            [item["command"] for item in PERFORMANCE_BASELINE_COMMANDS],
        )

        self.assertTrue(ok)
        self.assertEqual(errors, [])
        self.assertGreaterEqual(result["scenario_count"], 6)
        self.assertEqual(result["failed_count"], 0)
        self.assertFalse(result["launches_wps"])
        self.assertGreater(result["total_duration_ms"], 0)
        self.assertGreater(result["total_output_bytes"], 0)
        self.assertTrue(all(not item["launches_wps"] for item in result["results"]))

    def test_real_cli_runner_captures_output_and_duration(self):
        code, payload, raw, duration = _run_cli(["tasks", "--phase", "phase2"])
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(json.loads(raw)["command"], "tasks")
        self.assertGreater(duration, 0)

    def test_mcp_scenarios_require_the_current_catalog_size(self):
        scenarios = {item["id"]: item["command"] for item in PERFORMANCE_BASELINE_COMMANDS}
        expected = str(MCP_BASELINE_EXPECTED_TOOL_COUNT)
        self.assertEqual(MCP_BASELINE_EXPECTED_TOOL_COUNT, 70)
        self.assertEqual(
            scenarios["mcp-smoke"][scenarios["mcp-smoke"].index("--expected-min-tools") + 1],
            expected,
        )
        self.assertEqual(
            scenarios["mcp-config-audit"][scenarios["mcp-config-audit"].index("--expected-min-tools") + 1],
            expected,
        )

    def test_failed_command_is_preserved_in_baseline(self):
        def completed(command):
            payload = {"ok": command[0] != "regression-run", "summary": command[0]}
            return 0, payload, json.dumps(payload), 1.0

        with patch("wps_ai_agent_cli.performance._run_cli", side_effect=completed):
            ok, result, errors = capture_performance_baseline()
        self.assertFalse(ok)
        self.assertEqual(result["failed_count"], 1)
        self.assertEqual(errors[0]["details"][0]["id"], "regression-run-safe")


class WpsOperationCostTests(unittest.TestCase):
    def measure(self, call_ms, start_ms=400.0, fail_at=None):
        from wps_ai_agent_cli import performance

        calls = iter(range(1, 100))

        def run_cli(command):
            index = next(calls)
            ok = index != fail_at
            payload = {"ok": ok, "errors": [] if ok else [{"code": "COM_OPERATION_FAILED"}]}
            return (0 if ok else 1), payload, json.dumps(payload), call_ms[index - 1]

        with (
            patch.object(performance, "_run_cli", side_effect=run_cli) as runner,
            patch.object(performance, "_process_start_ms", return_value=(True, start_ms)),
            patch.object(performance, "_wps_process_count", return_value=0),
        ):
            result = performance.measure_wps_operation_cost(repeat=len(call_ms))
        return result, runner

    def test_medians_and_threshold(self):
        (ok, result, errors), runner = self.measure([2500.0, 900.0, 1100.0])
        self.assertTrue(ok, errors)
        self.assertEqual(result["wps_call_median_ms"], 1100.0)
        self.assertEqual(result["wps_first_call_ms"], 2500.0)
        self.assertEqual(result["cli_call_fixed_cost_ms"], 1500.0)
        self.assertFalse(result["c10_threshold_exceeded"])
        commands = [call.args[0] for call in runner.call_args_list]
        self.assertTrue(all(command[0] == "spreadsheet-write" for command in commands))
        self.assertEqual([command[-1] for command in commands], ["perf-1", "perf-2", "perf-3"])

        (ok, result, _errors), _ = self.measure([1900.0, 1800.0, 1850.0], start_ms=500.0)
        self.assertTrue(result["c10_threshold_exceeded"])

    def test_a_failed_wps_call_stops_and_fails(self):
        (ok, result, errors), runner = self.measure([1000.0, 1000.0, 1000.0], fail_at=2)
        self.assertFalse(ok)
        self.assertEqual(runner.call_count, 2)
        self.assertEqual(errors[0]["code"], "PERFORMANCE_WPS_CALL_FAILED")
        self.assertEqual(result["wps_call_median_ms"], 1000.0)

    def test_cli_flag(self):
        import io

        from wps_ai_agent_cli.cli import run

        measured = (
            True,
            {"cli_call_fixed_cost_ms": 1234.0, "c10_threshold_ms": 2000, "c10_threshold_exceeded": False},
            [],
        )
        safe = (True, {"scenario_count": 6, "launches_wps": False}, [])
        with (
            patch("wps_ai_agent_cli.performance.capture_performance_baseline", return_value=safe),
            patch("wps_ai_agent_cli.performance.measure_wps_operation_cost", return_value=measured),
        ):
            output = io.StringIO()
            code = run(["performance-baseline", "--include-wps", "--repeat", "2"], output_stream=output)
        response = json.loads(output.getvalue())
        self.assertEqual(code, 0, response)
        self.assertIn("1234 ms", response["summary"])
        self.assertEqual(
            [check["name"] for check in response["validation"]["checks"]],
            ["baseline_commands_passed", "wps_operation_measured"],
        )
        output = io.StringIO()
        code = run(["performance-baseline", "--include-wps", "--repeat", "0"], output_stream=output)
        self.assertNotEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["errors"][0]["code"], "INVALID_ARGUMENT")


if __name__ == "__main__":
    unittest.main()
