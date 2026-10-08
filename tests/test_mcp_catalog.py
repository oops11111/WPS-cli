import unittest
import json
from tempfile import TemporaryDirectory
from pathlib import Path

from wps_ai_agent_cli.mcp_catalog_drift import build_mcp_catalog_drift_report
from wps_ai_agent_cli.mcp_catalog import build_mcp_catalog_snapshot
from wps_ai_agent_cli.mcp_schema import list_mcp_tool_schemas


class McpCatalogSnapshotTests(unittest.TestCase):
    def test_snapshot_summarizes_tool_surface(self):
        snapshot = build_mcp_catalog_snapshot()
        tools = list_mcp_tool_schemas()
        mutating = [schema for schema in tools if schema["mutates_document"]]
        requires_wps = [schema for schema in tools if schema["requires_wps"]]

        self.assertEqual(snapshot["tool_count"], len(tools))
        self.assertEqual(snapshot["mutating_tool_count"], len(mutating))
        self.assertEqual(snapshot["requires_wps_tool_count"], len(requires_wps))
        self.assertEqual(snapshot["read_only_tool_count"], len(tools) - len(mutating))
        self.assertIn("mcp", snapshot["category_counts"])
        self.assertEqual(snapshot["safety_notes_missing_count"], 0)
        self.assertEqual(snapshot["safety_notes_missing_tools"], [])

    def test_catalog_drift_guard_passes_current_baseline(self):
        ok, report, errors = build_mcp_catalog_drift_report("config/mcp_catalog_guard.json")

        self.assertTrue(ok)
        self.assertEqual(errors, [])
        self.assertEqual(report["drift_count"], 0)
        self.assertFalse(report["review_required"])

    def test_catalog_drift_guard_reports_mismatch(self):
        with TemporaryDirectory() as tmpdir:
            guard = {
                "schema_version": "test",
                "expected_tool_count": -1,
                "expected_mutating_tool_count": -1,
                "expected_requires_wps_tool_count": -1,
                "expected_read_only_tool_count": -1,
                "expected_safety_notes_missing_count": -1,
                "expected_category_counts": {"mcp": -1},
            }
            guard_path = Path(tmpdir) / "guard.json"
            guard_path.write_text(json.dumps(guard), encoding="utf-8")

            ok, report, errors = build_mcp_catalog_drift_report(guard_path)

        self.assertFalse(ok)
        self.assertEqual(errors, [])
        self.assertGreater(report["drift_count"], 0)
        self.assertTrue(report["review_required"])
        self.assertTrue(any(drift["field"] == "tool_count" for drift in report["drifts"]))


if __name__ == "__main__":
    unittest.main()
