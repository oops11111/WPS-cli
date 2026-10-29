"""scripts/windows_check/mcp_client_smoke.py against this repository's MCP server (P14-005)."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "mcp_client_smoke", ROOT / "scripts" / "windows_check" / "mcp_client_smoke.py"
)
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


def _config(directory: Path, env: dict[str, str], command: str | None = None, args: list[str] | None = None) -> Path:
    path = directory / "claude_desktop_config.json"
    entry = {
        "command": command or sys.executable,
        "args": ["-m", "wps_ai_agent_cli", "mcp-server"] if args is None else args,
        "env": env,
    }
    path.write_text(json.dumps({"mcpServers": {"wps-agent": entry}}), encoding="utf-8")
    return path


def _run(*args, **kwargs):
    with redirect_stdout(io.StringIO()):
        return smoke.run(*args, **kwargs)


class McpClientSmokeTests(unittest.TestCase):
    @unittest.skipIf(sys.platform == "win32", "the write goes through WPS on Windows")
    def test_it_starts_the_configured_server_and_stops_at_the_write_without_wps(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            workspace = tmp_path / "data"
            config = _config(tmp_path, {"PYTHONPATH": str(ROOT / "src"), "WPS_AGENT_WORKSPACE": str(workspace)})
            work = tmp_path / "work"
            work.mkdir()
            report = _run(config, "wps-agent", work)
            backups = workspace / ".wps-agent" / "backups"
            left = sorted(p.name for p in backups.iterdir()) if backups.is_dir() else []
        steps = {item["step"]: item for item in report["steps"]}
        for label in ("read the client config", "initialize", "tools/list", "register the workbook"):
            self.assertTrue(steps[label]["ok"], steps[label])
        self.assertTrue(steps["read sales_gbk!A1:F3"]["ok"])
        self.assertEqual(report["read"][0][0], "地区")
        self.assertGreater(report["tool_count"], 50)  # more than one tools/list page
        self.assertEqual(report["protocol_version"]["answered"], smoke.PROTOCOL_VERSION)
        write = steps["write sales_gbk!F2"]
        self.assertFalse(write["ok"])
        self.assertEqual(write["detail"][0]["code"], "COM_BACKEND_UNAVAILABLE")
        self.assertEqual(left, [])  # the backup the failed write took was this run's, so it is removed
        self.assertEqual(report["entry"]["env_names"], ["PYTHONPATH", "WPS_AGENT_WORKSPACE"])
        self.assertNotIn(str(workspace), json.dumps(report["entry"]))  # env values are not reported

    def test_an_entry_without_a_workspace_fails_before_starting_the_server(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            report = _run(_config(tmp_path, {}), "wps-agent", tmp_path)
        self.assertEqual([item["ok"] for item in report["steps"]], [True, False])

    def test_a_missing_server_entry_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            report = _run(_config(tmp_path, {}), "other", tmp_path)
        self.assertEqual(len(report["steps"]), 1)
        self.assertFalse(report["steps"][0]["ok"])

    def test_a_command_that_does_not_exist_is_a_failed_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config = _config(tmp_path, {"WPS_AGENT_WORKSPACE": str(tmp_path / "data")}, command=str(tmp_path / "nope"))
            report = _run(config, "wps-agent", tmp_path)
        self.assertEqual(report["steps"][-1]["step"], "start the server")
        self.assertFalse(report["steps"][-1]["ok"])

    def test_a_server_that_never_answers_times_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config = _config(
                tmp_path,
                {"WPS_AGENT_WORKSPACE": str(tmp_path / "data")},
                args=["-c", "import sys; sys.stdin.readline(); sys.stdin.readline()"],  # never answers
            )
            report = _run(config, "wps-agent", tmp_path, timeout=1)
        self.assertEqual(report["steps"][-1]["step"], "talk to the server")
        self.assertIn("TimeoutError", report["steps"][-1]["detail"])

    def test_a_server_that_writes_something_other_than_json_is_a_failed_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config = _config(
                tmp_path,
                {"WPS_AGENT_WORKSPACE": str(tmp_path / "data")},
                args=["-c", "import sys; sys.stdin.readline(); print('hello'); sys.stdout.flush()"],
            )
            report = _run(config, "wps-agent", tmp_path, timeout=10)
        self.assertIn("not JSON", report["steps"][-1]["detail"])

    def test_the_report_is_written_when_the_server_cannot_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config = _config(tmp_path, {"WPS_AGENT_WORKSPACE": str(tmp_path / "data")}, command=str(tmp_path / "nope"))
            with redirect_stdout(io.StringIO()):
                code = smoke.main(["--out", str(tmp_path / "out"), "--config", str(config)])
            self.assertEqual(code, 1)
            self.assertIn("start the server", (tmp_path / "out" / "MCP_CLIENT_SMOKE.md").read_text(encoding="utf-8"))


class HelperTests(unittest.TestCase):
    def test_a_relative_backup_path_is_relative_to_the_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = str(Path(tmp) / "data")
            self.assertTrue(smoke.backup_under_workspace(".wps-agent/backups/doc_1/book.xlsx", workspace))
            self.assertTrue(smoke.backup_under_workspace(str(Path(workspace) / ".wps-agent" / "b.xlsx"), workspace))
            self.assertFalse(smoke.backup_under_workspace(str(Path(tmp) / "elsewhere.xlsx"), workspace))
            self.assertFalse(smoke.backup_under_workspace("../elsewhere.xlsx", workspace))

    def test_the_server_gets_the_sdk_default_variables_and_the_entry_env(self):
        shell = {"PATH": "/bin", "HOME": "/home/me", "PYTHONPATH": "/repo/src", "VIRTUAL_ENV": "/repo/.venv"}
        with mock.patch.dict(os.environ, shell, clear=True), mock.patch.object(smoke.sys, "platform", "linux"):
            env = smoke.server_env({"WPS_AGENT_WORKSPACE": "/data"}, inherit=False)
            inherited = smoke.server_env({"WPS_AGENT_WORKSPACE": "/data"}, inherit=True)
        self.assertEqual(env, {"PATH": "/bin", "HOME": "/home/me", "WPS_AGENT_WORKSPACE": "/data"})
        self.assertEqual(inherited["PYTHONPATH"], "/repo/src")

    def test_only_a_document_id_backup_folder_is_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            backups = Path(tmp) / ".wps-agent" / "backups"
            (backups / "doc_ab12").mkdir(parents=True)
            (backups / "doc_ab12" / "book.xlsx").write_bytes(b"x")
            self.assertIsNone(smoke._remove_backup_folder(tmp, ".."))
            self.assertIsNone(smoke._remove_backup_folder(tmp, "doc_ab12/../.."))
            self.assertTrue(backups.is_dir())
            self.assertIsNotNone(smoke._remove_backup_folder(tmp, "doc_ab12"))
            self.assertFalse((backups / "doc_ab12").exists())


if __name__ == "__main__":
    unittest.main()
