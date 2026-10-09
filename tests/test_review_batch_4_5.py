import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from wps_ai_agent_cli import mcp_server
from wps_ai_agent_cli.html_text import decode_html_bytes
from wps_ai_agent_cli.mcp_adapter import build_cli_argv, call_mcp_tool
from wps_ai_agent_cli.mcp_schema import list_mcp_tool_schemas
from wps_ai_agent_cli.security_audit import (
    build_security_boundary_audit,
    cli_parser_options,
    schema_parser_mismatches,
)


def tools_call(name, arguments, request_id=1):
    return {"jsonrpc": "2.0", "id": request_id, "method": "tools/call", "params": {"name": name, "arguments": arguments}}


TABLE_WRITE = {"document_id": "doc_x", "table_index": 1, "row": 1, "column": 1, "text": "t"}


class AdapterArgumentValidationTests(unittest.TestCase):
    def test_wrong_types_are_rejected_before_the_cli_parser_can_exit(self):
        cases = [
            {**TABLE_WRITE, "table_index": "abc"},
            {**TABLE_WRITE, "table_index": True},
            {**TABLE_WRITE, "table_index": 0},
            {**TABLE_WRITE, "dry_run": "false"},
            {**TABLE_WRITE, "text": 5},
        ]
        for arguments in cases:
            with self.subTest(arguments=arguments):
                ok, argv, _schema, errors = build_cli_argv("wps_agent_writer_table_write", arguments)
                self.assertFalse(ok)
                self.assertEqual(argv, [])
                self.assertTrue(errors[0]["code"].startswith("MCP_ARGUMENT_"), errors)

    def test_enum_values_are_checked(self):
        ok, _argv, _schema, errors = build_cli_argv("wps_agent_open_documents", {"component": "outlook"})
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "MCP_ARGUMENT_ENUM_INVALID")

    def test_values_starting_with_a_dash_cannot_become_flags(self):
        ok, argv, _schema, errors = build_cli_argv("wps_agent_writer_table_write", {**TABLE_WRITE, "text": "--dry-run"})
        self.assertTrue(ok, errors)
        self.assertIn("--text=--dry-run", argv)
        self.assertNotIn("--dry-run", argv)

        ok, argv, _schema, _errors = build_cli_argv("wps_agent_writer_table_write", {**TABLE_WRITE, "request_id": "-abc"})
        self.assertIn("--request-id=-abc", argv)

    def test_parser_exit_becomes_a_structured_error(self):
        with patch("wps_ai_agent_cli.cli.run", side_effect=SystemExit(2)):
            ok, result, errors = call_mcp_tool("wps_agent_plan", {})
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "MCP_CLI_ARGUMENTS_REJECTED")
        self.assertEqual(result["exit_code"], 2)

    def test_unexpected_cli_exception_becomes_a_structured_error(self):
        with patch("wps_ai_agent_cli.cli.run", side_effect=RuntimeError("boom")):
            ok, _result, errors = call_mcp_tool("wps_agent_plan", {})
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "MCP_TOOL_EXECUTION_FAILED")


HANDSHAKE = (
    json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "init",
            "method": "initialize",
            "params": {"protocolVersion": mcp_server.MCP_PROTOCOL_VERSION, "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}},
        }
    )
    + "\n"
    + json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})
    + "\n"
)


class McpServerResilienceTests(unittest.TestCase):
    def serve(self, text):
        output = io.StringIO()
        self.assertEqual(mcp_server.serve_stdio(io.StringIO(HANDSHAKE + text), output), 0)
        return [json.loads(line) for line in output.getvalue().splitlines()][1:]

    def test_invalid_tool_arguments_do_not_end_the_session(self):
        responses = self.serve(
            json.dumps(tools_call("wps_agent_writer_table_write", {**TABLE_WRITE, "table_index": "abc"}))
            + "\n"
            + json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            + "\n"
        )
        self.assertEqual([item["id"] for item in responses], [1, 2])
        self.assertEqual(responses[0]["error"]["code"], -32602)
        self.assertIn("result", responses[1])

    def test_unexpected_exception_in_a_tool_call_does_not_end_the_session(self):
        with patch.object(mcp_server, "call_mcp_tool", side_effect=RuntimeError("boom")):
            responses = self.serve(
                json.dumps(tools_call("wps_agent_plan", {})) + "\n" + json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}) + "\n"
            )
        self.assertEqual(responses[0]["error"]["code"], -32603)
        self.assertIn("result", responses[1])

    def test_notifications_never_get_a_response(self):
        self.assertIsNone(mcp_server.handle_mcp_request({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {}}))
        self.assertIsNone(mcp_server.handle_mcp_request({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        self.assertEqual(
            mcp_server.handle_mcp_request({"jsonrpc": "2.0", "id": 3, "method": "nope"})["error"]["code"], -32601
        )


class SchemaParserConsistencyTests(unittest.TestCase):
    def test_every_tool_schema_matches_its_cli_parser(self):
        commands = cli_parser_options()
        problems = {
            schema["name"]: found
            for schema in list_mcp_tool_schemas()
            if (found := schema_parser_mismatches(schema, commands))
        }
        self.assertEqual(problems, {})

    def test_mismatches_are_detected(self):
        commands = cli_parser_options()
        schema = {
            "cli_command": "writer-table-write",
            "input_schema": {
                "properties": {"document_id": {"type": "string"}, "bogus_flag": {"type": "string"}, "dry_run": {"type": "string"}},
                "required": ["document_id"],
            },
        }
        found = " | ".join(schema_parser_mismatches(schema, commands))
        self.assertIn("bogus_flag", found)
        self.assertIn("dry_run: boolean schema/flag mismatch", found)
        self.assertIn("CLI requires --table-index", found)
        self.assertEqual(schema_parser_mismatches({"cli_command": "does-not-exist", "input_schema": {}}, commands), ["no CLI subcommand named does-not-exist"])

    def test_audit_declares_its_scope_and_fails_on_drift(self):
        ok, result, errors = build_security_boundary_audit()
        self.assertTrue(ok, errors)
        self.assertFalse(result["behavioral_verification"])
        self.assertIn("not by this audit", result["scope_note"])

        drifted = [dict(schema) for schema in list_mcp_tool_schemas()]
        drifted[0] = {**drifted[0], "cli_command": "does-not-exist"}
        with patch("wps_ai_agent_cli.security_audit.list_mcp_tool_schemas", return_value=drifted):
            ok, result, errors = build_security_boundary_audit()
        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "SECURITY_BOUNDARY_AUDIT_FAILED")
        self.assertTrue(result["schema_parser_mismatches"])


class HtmlDecodingTests(unittest.TestCase):
    def test_decoding_order_and_fallback(self):
        text = "<html><head><meta charset=\"gb2312\"></head><body>你好，世界</body></html>"
        self.assertEqual(decode_html_bytes(text.encode("gbk"))[:2], (text, "gb2312"))
        self.assertEqual(decode_html_bytes(text.encode("utf-8"))[1], "utf-8")
        self.assertEqual(decode_html_bytes(b"\xef\xbb\xbf" + "你好".encode("utf-8")), ("你好", "utf-8-sig", None))
        self.assertEqual(decode_html_bytes("你好".encode("utf-16"))[:2], ("你好", "utf-16"))

        lossy, encoding, warning = decode_html_bytes("你好".encode("gbk"))
        self.assertEqual(encoding, "utf-8-replace")
        self.assertIn("\ufffd", lossy)
        self.assertIn("corrupted", warning)

        _text, encoding, warning = decode_html_bytes("你好".encode("gbk").join([b"<meta charset=nonsense>", b""]))
        self.assertEqual(encoding, "utf-8-replace")

    def test_editable_conversion_preserves_gbk_text_and_reports_encoding(self):
        import docx

        from wps_ai_agent_cli.html_editable import convert_html_editable

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "gbk.html"
            source.write_bytes('<html><head><meta charset="gb2312"><title>报告</title></head><body><p>你好，世界</p></body></html>'.encode("gbk"))
            ok, data, errors = convert_html_editable(source, root / "out.docx")
            self.assertTrue(ok, errors)
            self.assertEqual(data["source_encoding"], "gb2312")
            self.assertEqual([p.text for p in docx.Document(root / "out.docx").paragraphs], ["你好，世界"])
            self.assertFalse(any("document" in warning for warning in data["warnings"]))

    def test_undeclared_non_utf8_input_warns_instead_of_silently_corrupting(self):
        from wps_ai_agent_cli.html_editable import convert_html_editable

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "unknown.html"
            source.write_bytes("<html><body><p>你好，世界</p></body></html>".encode("gbk"))
            ok, data, errors = convert_html_editable(source, root / "out.docx")
            self.assertTrue(ok, errors)
            self.assertTrue(any("not valid UTF-8" in warning for warning in data["warnings"]))


class HyperlinkTargetTests(unittest.TestCase):
    def test_unc_paths_and_control_characters_are_not_linked(self):
        from wps_ai_agent_cli.html_editable import _safe_link_target

        for value in (r"\\server\share\file.docx", "\\folder\\x", "page\x00.html", "javascript:alert(1)", "//host/x", "file:///c:/x"):
            with self.subTest(value=value):
                self.assertFalse(_safe_link_target(value))
        for value in ("https://example.com/a", "mailto:a@b.c", "tel:123", "page.html#top", "../up.html"):
            with self.subTest(value=value):
                self.assertTrue(_safe_link_target(value))


class RenderPublishTests(unittest.TestCase):
    def test_render_never_overwrites_an_output_that_appears_during_rendering(self):
        from wps_ai_agent_cli import html_render

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "page.html"
            source.write_text("<html></html>", encoding="utf-8")
            destination = root / "page.pdf"

            def fake_run(_node, request, _timeout_seconds):
                Path(request["output_path"]).write_bytes(b"%PDF-1.7 fake")
                destination.write_bytes(b"someone else's file")
                return type("Completed", (), {"stdout": json.dumps({"ok": True}), "stderr": "", "returncode": 0})()

            with patch.object(html_render, "_resolve_browser_runtime", return_value=("node", "edge")), patch.object(
                html_render, "_run_renderer", side_effect=fake_run
            ):
                ok, _data, errors = html_render.render_html(source, destination, "pdf")
            self.assertFalse(ok)
            self.assertEqual(errors[0]["code"], "OUTPUT_ALREADY_EXISTS")
            self.assertEqual(destination.read_bytes(), b"someone else's file")
            self.assertEqual([item.name for item in root.iterdir() if item.name.startswith(".")], [])

    def test_render_publishes_valid_output_and_cleans_the_temporary_file(self):
        from wps_ai_agent_cli import html_render

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "page.html"
            source.write_text("<html></html>", encoding="utf-8")
            destination = root / "page.pdf"

            def fake_run(_node, request, _timeout_seconds):
                Path(request["output_path"]).write_bytes(b"%PDF-1.7 fake")
                return type("Completed", (), {"stdout": json.dumps({"ok": True}), "stderr": "", "returncode": 0})()

            with patch.object(html_render, "_resolve_browser_runtime", return_value=("node", "edge")), patch.object(
                html_render, "_run_renderer", side_effect=fake_run
            ):
                ok, data, errors = html_render.render_html(source, destination, "pdf")
            self.assertTrue(ok, errors)
            self.assertEqual(destination.read_bytes(), b"%PDF-1.7 fake")
            self.assertEqual(data["bytes"], 13)
            self.assertEqual(data["websocket_blocked"], True)
            self.assertEqual(sorted(item.name for item in root.iterdir()), ["page.html", "page.pdf"])

    def test_render_timeout_kills_the_process_tree(self):
        from wps_ai_agent_cli import html_render

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "page.html"
            source.write_text("<html></html>", encoding="utf-8")
            destination = root / "page.pdf"
            process = MagicMock()
            process.pid = 4242
            process.poll.return_value = None
            process.args = ["node", "render"]
            process.communicate.side_effect = [
                subprocess.TimeoutExpired(["node"], 1),
                ("", ""),
            ]

            with patch.object(html_render, "_resolve_browser_runtime", return_value=("node", "edge")), patch.object(
                html_render.subprocess, "Popen", return_value=process
            ), patch.object(html_render, "_kill_process_tree") as kill_tree:
                ok, _data, errors = html_render.render_html(source, destination, "pdf", timeout_seconds=1)
            self.assertFalse(ok)
            self.assertEqual(errors[0]["code"], "RENDER_TIMEOUT")
            kill_tree.assert_called_once_with(process)


class ConfigAuditExecutionTests(unittest.TestCase):
    def write_config(self, root, command, args, env=None, cwd=None):
        path = root / "mcp.json"
        path.write_text(
            json.dumps({
                "mcpServers": {
                    "srv": {"command": command, "args": args, "cwd": str(cwd or Path.cwd()), "env": env or {"PYTHONPATH": "src"}}
                }
            }),
            encoding="utf-8",
        )
        return path

    def audit(self, path):
        from wps_ai_agent_cli.mcp_config_audit import audit_mcp_client_config

        return audit_mcp_client_config(config_path=path, server_name="srv", timeout_seconds=15, restrict_launch=True)

    def test_untrusted_launch_lines_are_never_executed(self):
        import sys

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = root / "executed"
            cases = {
                "shell": ("/bin/sh", ["-c", f"touch {marker}", "mcp-server"], None),
                "python -c": (sys.executable, ["-c", f"open({str(marker)!r}, 'w')", "mcp-server"], None),
                "extra env": (sys.executable, ["-m", "wps_ai_agent_cli", "mcp-server"], {"PYTHONPATH": "src", "PYTHONSTARTUP": str(marker)}),
                "foreign package": (sys.executable, ["-m", "wps_ai_agent_cli", "mcp-server"], {"PYTHONPATH": str(root)}),
            }
            for name, (command, args, env) in cases.items():
                with self.subTest(case=name):
                    ok, result, _errors = self.audit(self.write_config(root, command, args, env))
                    self.assertFalse(ok)
                    self.assertIsNone(result["smoke"])
                    failed = {check["name"] for check in result["checks"] if not check["passed"]}
                    self.assertIn("launch_line_is_this_package", failed)
                    self.assertFalse(marker.exists())

    def test_foreign_cwd_cannot_supply_its_own_package(self):
        import sys

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "src" / "wps_ai_agent_cli"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("open('executed', 'w')\n", encoding="utf-8")
            (package / "__main__.py").write_text("", encoding="utf-8")
            config = self.write_config(root, sys.executable, ["-m", "wps_ai_agent_cli", "mcp-server"], cwd=root)
            ok, result, _errors = self.audit(config)
            self.assertFalse(ok)
            self.assertIsNone(result["smoke"])
            self.assertFalse((root / "executed").exists())


class RegressionCommandAllowlistTests(unittest.TestCase):
    def test_shipped_manifest_only_uses_allowed_commands(self):
        from wps_ai_agent_cli.regression import REGRESSION_ALLOWED_COMMANDS

        manifest = json.loads((Path(__file__).resolve().parent.parent / "config" / "regression_manifest.json").read_text(encoding="utf-8"))
        used = {scenario["command"][0] for scenario in manifest["scenarios"]}
        self.assertEqual(used - REGRESSION_ALLOWED_COMMANDS, set())

    def test_custom_manifest_cannot_run_mutating_or_recursive_commands(self):
        from wps_ai_agent_cli.regression import run_regression_manifest

        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "manifest.json"
            manifest.write_text(
                json.dumps({
                    "version": "t",
                    "default_profile": "safe",
                    "scenarios": [
                        {"id": "restore", "profile": "safe", "command": ["restore-backup", "--document-id", "d"], "required_checks": []},
                        {"id": "recursion", "profile": "safe", "command": ["regression-run"], "required_checks": []},
                        {"id": "server", "profile": "safe", "command": ["mcp-server"], "required_checks": []},
                        {"id": "empty", "profile": "safe", "command": [], "required_checks": []},
                        {"id": "wrong-type", "profile": "safe", "command": ["plan", 5], "required_checks": []},
                    ],
                }),
                encoding="utf-8",
            )
            with patch("wps_ai_agent_cli.regression._run_cli") as run_cli:
                ok, result, _errors = run_regression_manifest(manifest_path=manifest)
            run_cli.assert_not_called()
            self.assertFalse(ok)
            self.assertEqual(result["failed_count"], 5)
            self.assertTrue(all(item["errors"][0]["code"] == "REGRESSION_COMMAND_NOT_ALLOWED" for item in result["results"]))

    def test_allowed_commands_still_run(self):
        from wps_ai_agent_cli.regression import run_regression_manifest

        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "manifest.json"
            manifest.write_text(
                json.dumps({"version": "t", "default_profile": "safe", "scenarios": [
                    {"id": "plan", "profile": "safe", "command": ["plan"], "required_checks": []}
                ]}),
                encoding="utf-8",
            )
            ok, result, errors = run_regression_manifest(manifest_path=manifest)
        self.assertTrue(ok, errors)
        self.assertEqual(result["passed_count"], 1)


if __name__ == "__main__":
    unittest.main()
