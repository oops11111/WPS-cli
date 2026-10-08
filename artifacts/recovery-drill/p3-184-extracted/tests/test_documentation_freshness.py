import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from wps_ai_agent_cli.documentation_freshness import CURRENT_DOC_PATHS, build_documentation_freshness_report
from wps_ai_agent_cli.mcp_schema import list_mcp_tool_schemas
from wps_ai_agent_cli.tasks import list_tasks


def _write_current_docs(workspace: Path) -> None:
    tool_count = len(list_mcp_tool_schemas())
    next_id = list_tasks(phase="phase3", status="next")[0]["id"]
    for relative in CURRENT_DOC_PATHS:
        path = workspace / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if relative == "config/regression_manifest.json":
            path.write_text(json.dumps({"checks": [{"id": next_id}], "tools": tool_count}), encoding="utf-8")
        elif relative == "config/mcp_catalog_guard.json":
            path.write_text(json.dumps({"expected_tool_count": tool_count}), encoding="utf-8")
        else:
            path.write_text(
                f"当前 MCP 工具面为 {tool_count} 个工具。\n当前 next 为 {next_id}。\n",
                encoding="utf-8",
            )


class DocumentationFreshnessTests(unittest.TestCase):
    def test_report_passes_when_current_references_are_fresh(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            _write_current_docs(workspace)

            report = build_documentation_freshness_report(workspace)

        self.assertEqual(report["freshness_status"], "passed")
        self.assertTrue(report["read_only"])
        self.assertFalse(report["launches_wps"])
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["current"]["mcp_tool_count"], len(list_mcp_tool_schemas()))

    def test_report_warns_on_current_stale_tool_count(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            _write_current_docs(workspace)
            stale_count = len(list_mcp_tool_schemas()) - 1
            (workspace / "README.md").write_text(f"当前 MCP 工具面为 {stale_count} 个工具。\n", encoding="utf-8")

            report = build_documentation_freshness_report(workspace)

        self.assertEqual(report["freshness_status"], "warning")
        self.assertGreaterEqual(len(report["findings"]), 1)
        self.assertEqual(report["findings"][0]["path"], "README.md")


if __name__ == "__main__":
    unittest.main()
