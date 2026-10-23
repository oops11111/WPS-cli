"""MCP client configuration written by the installer (P14-002)."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from wps_ai_agent_cli import client_config

EXE = r"C:\Users\me\AppData\Local\wps-agent\venv\Scripts\wps-agent.exe"


def _run(*argv: str) -> tuple[int, dict]:
    out = io.StringIO()
    with redirect_stdout(out):
        code = client_config.main(list(argv))
    return code, json.loads(out.getvalue())


class ClientConfigTests(unittest.TestCase):
    def test_the_entry_starts_the_stdio_server_with_its_environment(self):
        code, result = _run("--command", EXE, "--env", "NODE_PATH=C:\\n\\node_modules")
        self.assertEqual(code, 0)
        entry = result["entry"]["mcpServers"]["wps-agent"]
        self.assertEqual(entry, {"command": EXE, "args": ["mcp-server"], "env": {"NODE_PATH": "C:\\n\\node_modules"}})

    def test_claude_desktop_keeps_other_servers_and_backs_the_file_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Claude" / "claude_desktop_config.json"
            path.parent.mkdir()
            path.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}, "theme": "dark"}), encoding="utf-8")
            code, result = _run("--client", "claude-desktop", "--command", EXE, "--write", "--config-path", str(path))
            self.assertEqual(code, 0)
            written = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(set(written["mcpServers"]), {"other", "wps-agent"})
            self.assertEqual(written["theme"], "dark")
            backup = Path(result["written"]["backup"])
            self.assertTrue(backup.is_file())
            self.assertNotIn("wps-agent", json.loads(backup.read_text(encoding="utf-8"))["mcpServers"])

    def test_claude_desktop_creates_the_file_when_there_is_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "new" / "claude_desktop_config.json"
            code, result = _run("--client", "claude-desktop", "--command", EXE, "--write", "--config-path", str(path))
            self.assertEqual(code, 0)
            self.assertIsNone(result["written"]["backup"])
            self.assertIn("wps-agent", json.loads(path.read_text(encoding="utf-8"))["mcpServers"])

    def test_a_config_that_is_not_an_object_is_left_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claude_desktop_config.json"
            path.write_text("[1, 2]", encoding="utf-8")
            code, result = _run("--client", "claude-desktop", "--command", EXE, "--write", "--config-path", str(path))
            self.assertEqual(code, 1)
            self.assertIn("error", result)
            self.assertEqual(path.read_text(encoding="utf-8"), "[1, 2]")

    def test_without_write_nothing_is_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claude_desktop_config.json"
            code, result = _run("--client", "claude-desktop", "--command", EXE, "--config-path", str(path))
            self.assertEqual(code, 0)
            self.assertFalse(path.exists())
            self.assertNotIn("written", result)

    def test_claude_code_gets_a_user_scoped_add_command(self):
        code, result = _run("--client", "claude-code", "--command", EXE, "--env", "NODE_PATH=n")
        self.assertEqual(code, 0)
        self.assertEqual(
            result["command"],
            ["claude", "mcp", "add", "--scope", "user", "-e", "NODE_PATH=n", "wps-agent", "--", EXE, "mcp-server"],
        )


if __name__ == "__main__":
    unittest.main()


class McpServerWorkspaceTests(unittest.TestCase):
    def test_the_server_works_in_wps_agent_workspace_when_it_is_set(self):
        import os
        from unittest import mock

        from wps_ai_agent_cli import cli

        seen = {}

        def fake_serve():
            seen["cwd"] = os.getcwd()
            return 0

        before = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "data" / "workspace"
            try:
                with (
                    mock.patch.dict(os.environ, {"WPS_AGENT_WORKSPACE": str(workspace)}),
                    mock.patch.object(cli, "serve_stdio", side_effect=fake_serve),
                ):
                    cli.run(["mcp-server"])
            finally:
                os.chdir(before)
            self.assertTrue(workspace.is_dir())
            self.assertEqual(Path(seen["cwd"]).resolve(), workspace.resolve())
