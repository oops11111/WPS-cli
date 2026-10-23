"""scripts/windows_check/mcp_client_smoke.py against this repository's MCP server (P14-005)."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "mcp_client_smoke", ROOT / "scripts" / "windows_check" / "mcp_client_smoke.py"
)
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


def _config(directory: Path, env: dict[str, str]) -> Path:
    path = directory / "claude_desktop_config.json"
    entry = {"command": sys.executable, "args": ["-m", "wps_ai_agent_cli", "mcp-server"], "env": env}
    path.write_text(json.dumps({"mcpServers": {"wps-agent": entry}}), encoding="utf-8")
    return path


class McpClientSmokeTests(unittest.TestCase):
    @unittest.skipIf(sys.platform == "win32", "the write goes through WPS on Windows")
    def test_it_starts_the_configured_server_and_stops_at_the_write_without_wps(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            workspace = tmp_path / "data"
            config = _config(tmp_path, {"PYTHONPATH": str(ROOT / "src"), "WPS_AGENT_WORKSPACE": str(workspace)})
            work = tmp_path / "work"
            work.mkdir()
            with redirect_stdout(io.StringIO()):
                report = smoke.run(config, "wps-agent", work)
        steps = {item["step"]: item for item in report["steps"]}
        for label in ("read the client config", "initialize", "tools/list", "register the workbook"):
            self.assertTrue(steps[label]["ok"], steps[label])
        self.assertTrue(steps["read sales_gbk!A1:F3"]["ok"])
        self.assertEqual(report["read"][0][0], "地区")
        self.assertGreater(report["tool_count"], 50)  # more than one tools/list page
        write = steps["write sales_gbk!F2"]
        self.assertFalse(write["ok"])
        self.assertEqual(write["detail"][0]["code"], "COM_BACKEND_UNAVAILABLE")

    def test_an_entry_without_a_workspace_fails_before_starting_the_server(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config = _config(tmp_path, {})
            with redirect_stdout(io.StringIO()):
                report = smoke.run(config, "wps-agent", tmp_path)
        self.assertEqual([item["ok"] for item in report["steps"]], [True, False])

    def test_a_missing_server_entry_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config = _config(tmp_path, {})
            with redirect_stdout(io.StringIO()):
                report = smoke.run(config, "other", tmp_path)
        self.assertEqual(len(report["steps"]), 1)
        self.assertFalse(report["steps"][0]["ok"])


if __name__ == "__main__":
    unittest.main()
