import unittest
import json
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
        self.assertEqual([call.args[0] for call in runner.call_args_list],
                         [item["command"] for item in PERFORMANCE_BASELINE_COMMANDS])

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
        self.assertEqual(MCP_BASELINE_EXPECTED_TOOL_COUNT, 81)
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


if __name__ == "__main__":
    unittest.main()
