import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wps_ai_agent_cli.mcp_config_audit import (
    MCP_CONFIG_MAX_BYTES,
    MCP_CONFIG_MAX_JSON_DEPTH,
    MCP_CONFIG_AUDIT_TIMEOUT_MAX_SECONDS,
    MCP_CONFIG_AUDIT_TIMEOUT_MIN_SECONDS,
    _load_config,
    audit_mcp_client_config,
)
from wps_ai_agent_cli.mcp_schema import list_mcp_tool_schemas


def tool_descriptor(name):
    return {
        "name": name,
        "title": "Example tool",
        "description": "A test tool.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
        "outputSchema": {"type": "object", "properties": {}},
        "annotations": {},
    }


class McpConfigAuditTests(unittest.TestCase):
    def test_timeout_bounds_are_checked_before_config_read_or_spawn(self):
        for timeout in (0, -1, MCP_CONFIG_AUDIT_TIMEOUT_MAX_SECONDS + 1, True, 1.5):
            with self.subTest(timeout=timeout):
                with patch("wps_ai_agent_cli.mcp_config_audit._load_config") as load_config:
                    with patch("wps_ai_agent_cli.mcp_config_audit.subprocess.Popen") as popen:
                        ok, result, errors = audit_mcp_client_config(
                            config_path="missing-config.json", timeout_seconds=timeout,
                        )

                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "MCP_CONFIG_AUDIT_FAILED")
                check = next(item for item in result["checks"] if item["name"] == "timeout_seconds_within_limit")
                self.assertFalse(check["passed"])
                self.assertIsNone(result["smoke"])
                load_config.assert_not_called()
                popen.assert_not_called()

        with patch("wps_ai_agent_cli.mcp_config_audit._load_config", return_value=(None, [])):
            ok, result, _ = audit_mcp_client_config(
                config_path="missing-config.json", timeout_seconds=MCP_CONFIG_AUDIT_TIMEOUT_MAX_SECONDS,
            )
        self.assertFalse(ok)
        check = next(item for item in result["checks"] if item["name"] == "timeout_seconds_within_limit")
        self.assertTrue(check["passed"])

    def audit_fake_paged_server(self, pages, expected_min_tools=1):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "mcp.json"
            server_script = "\n".join((
                "import json,sys,time",
                "pages=json.loads(sys.argv[-1])",
                "if pages and pages[0].get('_oversized'):",
                "    sys.stdout.write('x'*(1024*1024+1)+'\\n')",
                "    sys.stdout.flush()",
                "    time.sleep(30)",
                "if pages and pages[0].get('_invalidUtf8'):",
                "    sys.stdout.buffer.write(b'\\xff\\n')",
                "    sys.stdout.flush()",
                "    time.sleep(30)",
                "if pages and pages[0].get('_deepJson'):",
                "    sys.stdout.write('['*1500+'0'+']'*1500+'\\n')",
                "    sys.stdout.flush()",
                "    time.sleep(30)",
                "if pages and pages[0].get('_malformedJson'):",
                "    sys.stdout.write('{bad json\\n')",
                "    sys.stdout.flush()",
                "    time.sleep(30)",
                "if pages and pages[0].get('_stderrFlood'):",
                "    sys.stderr.write('e'*20000)",
                "    sys.stderr.flush()",
                "index=0",
                "initialized=False",
                "for line in sys.stdin:",
                "    request=json.loads(line)",
                "    method=request['method']",
                "    response={'jsonrpc':'2.0','id':request.get('id')}",
                "    if method=='initialize':",
                "        response['result']=pages[0].get('_initialize',{'protocolVersion':'2025-11-25','capabilities':{'tools':{}},'serverInfo':{'name':'fake','version':'1'}})",
                "    elif method=='notifications/initialized':",
                "        initialized=True",
                "        continue",
                "    elif method=='tools/list':",
                "        if not initialized:",
                "            response['error']={'code':-32600,'message':'not initialized'}",
                "        elif pages[index].get('_error'):",
                "            response['error']={'code':-32602,'message':'fake error'}",
                "        else:",
                "            page=pages[index]",
                "            response['id']=page.get('_responseId',request['id'])",
                "            response['result']={k:v for k,v in page.items() if not k.startswith('_')}",
                "            index+=1",
                "    else:",
                "        response['error']={'code':-32601,'message':'unknown'}",
                "    print(json.dumps(response),flush=True)",
            ))
            config_path.write_text(json.dumps({
                "mcpServers": {
                    "fake-server": {
                        "command": sys.executable,
                        "args": ["-c", server_script, "mcp-server", json.dumps(pages)],
                        "cwd": str(root),
                        "env": {"PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
                    }
                }
            }), encoding="utf-8")
            return audit_mcp_client_config(
                config_path=config_path,
                server_name="fake-server",
                expected_min_tools=expected_min_tools,
                timeout_seconds=10,
            )

    def test_audit_mcp_client_config_runs_configured_tools_list_smoke(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path.cwd()
            config_path = Path(tmp) / "mcp.json"
            config_path.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "wps-ai-agent-cli": {
                                "command": sys.executable,
                                "args": ["-m", "wps_ai_agent_cli", "mcp-server"],
                                "cwd": str(workspace),
                                "env": {"PYTHONPATH": "src"},
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            ok, result, errors = audit_mcp_client_config(
                config_path=config_path,
                expected_min_tools=len(list_mcp_tool_schemas()),
                timeout_seconds=15,
            )

            self.assertTrue(ok)
            self.assertEqual(errors, [])
            self.assertEqual(result["smoke"]["tool_count"], len(list_mcp_tool_schemas()))
            self.assertGreater(result["smoke"]["page_count"], 1)
            self.assertEqual(result["smoke"]["duplicate_tool_count"], 0)
            self.assertEqual(result["smoke"]["invalid_descriptor_count"], 0)
            self.assertTrue(result["smoke"]["persistent_session"])
            self.assertEqual(result["smoke"]["protocol_version"], "2025-11-25")
            self.assertTrue(all(check["passed"] for check in result["checks"]))

    def test_audit_mcp_client_config_reports_missing_server(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "mcp.json"
            config_path.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")

            ok, result, errors = audit_mcp_client_config(config_path=config_path)

            self.assertFalse(ok)
            self.assertEqual(errors[0]["code"], "MCP_CONFIG_AUDIT_FAILED")
            server_check = next(check for check in result["checks"] if check["name"] == "server_found")
            self.assertFalse(server_check["passed"])

    def test_malformed_process_argument_shapes_do_not_spawn(self):
        invalid_server_fields = (
            {"command": 7},
            {"args": ["-c", "pass", "mcp-server", 7]},
            {"args": "-m wps_ai_agent_cli mcp-server"},
            {"env": {"PYTHONPATH": "src", "BAD_VALUE": 7}},
            {"env": []},
            {"command": "bad\0command"},
            {"args": ["-c", "pass", "mcp-server", "bad\0arg"]},
            {"env": {"PYTHONPATH": "src", "BAD=KEY": "value"}},
            {"env": {"PYTHONPATH": "src", "BAD_VALUE": "bad\0value"}},
            {"env": {"": "empty key"}},
        )
        for overrides in invalid_server_fields:
            with self.subTest(overrides=overrides), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                config_path = root / "mcp.json"
                server = {
                    "command": sys.executable,
                    "args": ["-c", "pass", "mcp-server"],
                    "cwd": str(root),
                    "env": {"PYTHONPATH": "DO_NOT_ECHO_SECRET"},
                }
                server.update(overrides)
                config_path.write_text(json.dumps({
                    "mcpServers": {"fake-server": server},
                }), encoding="utf-8")

                with patch("wps_ai_agent_cli.mcp_config_audit.subprocess.Popen") as popen:
                    ok, result, errors = audit_mcp_client_config(
                        config_path=config_path,
                        server_name="fake-server",
                    )

                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "MCP_CONFIG_AUDIT_FAILED")
                self.assertIsNone(result["smoke"])
                self.assertNotIn("DO_NOT_ECHO_SECRET", json.dumps(result))
                popen.assert_not_called()

    def test_process_config_diagnostics_are_bounded_and_hide_argument_values(self):
        cases = (
            {"command": "missing-" + "c" * 600},
            {"cwd": "missing-" + "d" * 600},
            {
                "args": ["-c", "pass", "mcp-server", "ARG_SECRET_" + "s" * 300],
                "cwd": "missing-" + "d" * 600,
            },
        )
        for overrides in cases:
            with self.subTest(field=next(iter(overrides))), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                config_path = root / "mcp.json"
                server = {
                    "command": sys.executable,
                    "args": ["-c", "pass", "mcp-server"],
                    "cwd": str(root),
                    "env": {"PYTHONPATH": "src"},
                }
                server.update(overrides)
                config_path.write_text(json.dumps({
                    "mcpServers": {"fake-server": server},
                }), encoding="utf-8")

                with patch("wps_ai_agent_cli.mcp_config_audit.subprocess.Popen") as popen:
                    ok, result, errors = audit_mcp_client_config(
                        config_path=config_path,
                        server_name="fake-server",
                    )

                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "MCP_CONFIG_AUDIT_FAILED")
                checks = {check["name"]: check["details"] for check in result["checks"]}
                self.assertLessEqual(len(checks["command_resolves"] or ""), 256)
                self.assertLessEqual(len(checks["cwd_exists"] or ""), 256)
                self.assertNotIn("ARG_SECRET_", json.dumps(result))
                popen.assert_not_called()

    def test_oversized_config_is_rejected_before_spawn(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "mcp.json"
            config_path.write_bytes(b"{}" + b" " * MCP_CONFIG_MAX_BYTES)

            with patch("wps_ai_agent_cli.mcp_config_audit.subprocess.Popen") as popen:
                ok, result, errors = audit_mcp_client_config(config_path=config_path)

        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "MCP_CONFIG_AUDIT_FAILED")
        self.assertIsNone(result["smoke"])
        size_check = next(check for check in result["checks"] if check["name"] == "config_size_within_limit")
        self.assertFalse(size_check["passed"])
        self.assertLess(len(json.dumps(size_check)), 128)
        popen.assert_not_called()

    def test_malformed_config_object_shapes_are_rejected_before_spawn(self):
        cases = (
            ([], "config_root_is_object"),
            ("not an object", "config_root_is_object"),
            (7, "config_root_is_object"),
            (None, "config_root_is_object"),
            ({"mcpServers": []}, "mcp_servers_is_object"),
            ({"mcpServers": None}, "mcp_servers_is_object"),
        )
        for config, expected_check in cases:
            with self.subTest(config=repr(config)), tempfile.TemporaryDirectory() as tmp:
                config_path = Path(tmp) / "mcp.json"
                config_path.write_text(json.dumps(config), encoding="utf-8")

                with patch("wps_ai_agent_cli.mcp_config_audit.subprocess.Popen") as popen:
                    ok, result, errors = audit_mcp_client_config(config_path=config_path)

                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "MCP_CONFIG_AUDIT_FAILED")
                self.assertIsNone(result["smoke"])
                check = next(item for item in result["checks"] if item["name"] == expected_check)
                self.assertFalse(check["passed"])
                popen.assert_not_called()

    def test_ambiguous_json_members_and_constants_are_rejected_before_spawn(self):
        cases = (
            b'{"mcpServers":{},"mcpServers":{}}',
            b'{"mcpServers":{"fake":{"command":"first","command":"second"}}}',
            b'{"mcpServers":{},"nested":{"value":1,"value":2}}',
            b'{"mcpServers":{},"number":NaN}',
            b'{"mcpServers":{},"nested":{"number":Infinity}}',
            b'{"mcpServers":{},"number":-Infinity}',
        )
        for raw_config in cases:
            with self.subTest(raw_config=raw_config), tempfile.TemporaryDirectory() as tmp:
                config_path = Path(tmp) / "mcp.json"
                config_path.write_bytes(raw_config)

                with patch("wps_ai_agent_cli.mcp_config_audit.subprocess.Popen") as popen:
                    ok, result, errors = audit_mcp_client_config(config_path=config_path)

                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "MCP_CONFIG_AUDIT_FAILED")
                self.assertIsNone(result["smoke"])
                json_check = next(item for item in result["checks"] if item["name"] == "config_json_valid")
                self.assertFalse(json_check["passed"])
                self.assertIsNone(json_check["details"])
                self.assertLess(len(json.dumps(result)), 1024)
                popen.assert_not_called()

    def test_config_json_depth_limit_respects_strings_and_escapes(self):
        prefix = b'{"mcpServers":{},"payload":"braces [] {} and quote \\\"", "nested":'
        exact_depth = b"[" * (MCP_CONFIG_MAX_JSON_DEPTH - 1) + b"0" + b"]" * (MCP_CONFIG_MAX_JSON_DEPTH - 1)
        over_depth = b"[" * MCP_CONFIG_MAX_JSON_DEPTH + b"0" + b"]" * MCP_CONFIG_MAX_JSON_DEPTH
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "mcp.json"
            config_path.write_bytes(prefix + exact_depth + b"}")
            config, checks = _load_config(config_path)
            self.assertIsInstance(config, dict)
            exact_check = next(item for item in checks if item["name"] == "config_json_depth_within_limit")
            self.assertTrue(exact_check["passed"])

            config_path.write_bytes(prefix + over_depth + b"}")
            with patch("wps_ai_agent_cli.mcp_config_audit.json.loads") as loads:
                with patch("wps_ai_agent_cli.mcp_config_audit.subprocess.Popen") as popen:
                    ok, result, errors = audit_mcp_client_config(config_path=config_path)

        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "MCP_CONFIG_AUDIT_FAILED")
        depth_check = next(item for item in result["checks"] if item["name"] == "config_json_depth_within_limit")
        self.assertFalse(depth_check["passed"])
        self.assertLess(len(json.dumps(depth_check)), 128)
        loads.assert_not_called()
        popen.assert_not_called()

    def test_unpaired_surrogates_are_rejected_and_valid_unicode_is_preserved(self):
        invalid_cases = (
            b'{"mcpServers":{},"private":"SECRET_HIGH\\ud800"}',
            b'{"mcpServers":{},"nested":{"private":"SECRET_LOW\\udfff"}}',
        )
        for raw_config in invalid_cases:
            with self.subTest(raw_config=raw_config), tempfile.TemporaryDirectory() as tmp:
                config_path = Path(tmp) / "mcp.json"
                config_path.write_bytes(raw_config)

                with patch("wps_ai_agent_cli.mcp_config_audit.subprocess.Popen") as popen:
                    ok, result, errors = audit_mcp_client_config(config_path=config_path)

                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "MCP_CONFIG_AUDIT_FAILED")
                self.assertIsNone(result["smoke"])
                unicode_check = next(item for item in result["checks"] if item["name"] == "config_unicode_valid")
                self.assertFalse(unicode_check["passed"])
                self.assertIsNone(unicode_check["details"])
                self.assertNotIn("SECRET_", json.dumps(result))
                popen.assert_not_called()

        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "mcp.json"
            config_path.write_bytes(b'{"mcpServers":{},"emoji":"\\ud83d\\ude00","text":"caf\xc3\xa9"}')
            config, checks = _load_config(config_path)

        self.assertIsInstance(config, dict)
        self.assertEqual(config["emoji"], "\U0001f600")
        self.assertEqual(config["text"], "caf\u00e9")
        unicode_check = next(item for item in checks if item["name"] == "config_unicode_valid")
        self.assertTrue(unicode_check["passed"])

    def test_valid_config_at_exact_byte_limit_is_audited(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "mcp.json"
            server_script = "\n".join((
                "import json,sys",
                "for line in sys.stdin:",
                "    request=json.loads(line)",
                "    method=request['method']",
                "    if method=='notifications/initialized': continue",
                "    result={'protocolVersion':'2025-11-25','capabilities':{'tools':{}},'serverInfo':{'name':'edge','version':'1'}} if method=='initialize' else {'tools':[{'name':'edge_tool','inputSchema':{'type':'object'}}]}",
                "    print(json.dumps({'jsonrpc':'2.0','id':request['id'],'result':result}),flush=True)",
            ))
            config = {
                "mcpServers": {"fake-server": {
                    "command": sys.executable,
                    "args": ["-c", server_script, "mcp-server"],
                    "cwd": str(root),
                    "env": {"PYTHONPATH": "src"},
                }},
                "padding": "",
            }
            base_size = len(json.dumps(config).encode("utf-8"))
            config["padding"] = "x" * (MCP_CONFIG_MAX_BYTES - base_size)
            encoded = json.dumps(config).encode("utf-8")
            self.assertEqual(len(encoded), MCP_CONFIG_MAX_BYTES)
            config_path.write_bytes(encoded)

            ok, result, errors = audit_mcp_client_config(
                config_path=config_path, server_name="fake-server", expected_min_tools=1,
            )

        self.assertTrue(ok, errors)
        size_check = next(check for check in result["checks"] if check["name"] == "config_size_within_limit")
        self.assertTrue(size_check["passed"])
        self.assertEqual(size_check["details"]["size_bytes"], MCP_CONFIG_MAX_BYTES)

    def test_audit_rejects_duplicate_tool_names_across_pages(self):
        ok, result, errors = self.audit_fake_paged_server([
            {"resultType": "complete", "tools": [tool_descriptor("tool_a")], "nextCursor": "page-2"},
            {"resultType": "complete", "tools": [tool_descriptor("tool_a")]},
        ], expected_min_tools=2)

        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "MCP_CONFIG_AUDIT_FAILED")
        self.assertEqual(result["smoke"]["tool_count"], 2)
        self.assertEqual(result["smoke"]["page_count"], 2)
        self.assertEqual(result["smoke"]["duplicate_tool_count"], 1)
        smoke_check = next(check for check in result["checks"] if check["name"] == "configured_tools_list_smoke")
        self.assertFalse(smoke_check["passed"])

    def test_audit_rejects_repeated_cursor_without_extra_request(self):
        ok, result, errors = self.audit_fake_paged_server([
            {"resultType": "complete", "tools": [tool_descriptor("tool_a")], "nextCursor": "repeat"},
            {"resultType": "complete", "tools": [tool_descriptor("tool_b")], "nextCursor": "repeat"},
        ])

        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "MCP_CONFIG_AUDIT_FAILED")
        self.assertEqual(result["smoke"]["page_count"], 2)
        self.assertIn("repeated cursor", result["smoke"]["error"])

    def test_audit_rejects_response_id_mismatch(self):
        ok, result, errors = self.audit_fake_paged_server([
            {"resultType": "complete", "tools": [tool_descriptor("tool_a")], "_responseId": "wrong-id"},
        ])

        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "MCP_CONFIG_AUDIT_FAILED")
        self.assertIn("response or request ID", result["smoke"]["error"])

    def test_audit_cleans_up_timed_out_persistent_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "mcp.json"
            script = "import time; time.sleep(30)"
            config_path.write_text(json.dumps({
                "mcpServers": {"fake-server": {
                    "command": sys.executable,
                    "args": ["-c", script],
                    "cwd": str(root),
                    "env": {},
                }},
            }), encoding="utf-8")

            ok, result, errors = audit_mcp_client_config(
                config_path=config_path, server_name="fake-server", timeout_seconds=1,
            )

        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "MCP_CONFIG_AUDIT_FAILED")
        self.assertIn("timed out", result["smoke"]["error"].lower())

    def test_audit_rejects_empty_and_whitespace_tool_names(self):
        for name in ("", "   "):
            with self.subTest(name=repr(name)):
                ok, result, errors = self.audit_fake_paged_server([
                    {"resultType": "complete", "tools": [{"name": name}]},
                    {"resultType": "complete", "tools": []},
                ], expected_min_tools=1)

                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "MCP_CONFIG_AUDIT_FAILED")
                self.assertEqual(result["smoke"]["tool_count"], 1)
                self.assertEqual(result["smoke"]["invalid_tool_count"], 1)

    def test_audit_validates_mcp_tool_name_charset_and_length(self):
        for name in ("tool name", "tool/name", "naïve", "a" * 129):
            with self.subTest(name=name[:20]):
                ok, result, _ = self.audit_fake_paged_server([
                    {"resultType": "complete", "tools": [tool_descriptor(name)]},
                    {"resultType": "complete", "tools": []},
                ])
                self.assertFalse(ok)
                self.assertEqual(result["smoke"]["invalid_tool_count"], 1)

        for name in ("a", "A" * 128, "tool.name_v2-3"):
            with self.subTest(valid_name=name[:20]):
                ok, result, errors = self.audit_fake_paged_server([
                    {"resultType": "complete", "tools": [tool_descriptor(name)]},
                    {"resultType": "complete", "tools": []},
                ])
                self.assertTrue(ok, errors)
                self.assertEqual(result["smoke"]["invalid_tool_count"], 0)
                self.assertEqual(result["smoke"]["duplicate_tool_count"], 0)

    def test_audit_rejects_malformed_tool_schema_on_later_page_with_bounded_diagnostics(self):
        malformed = tool_descriptor("tool_b")
        malformed["inputSchema"] = {"type": "string"}
        malformed["outputSchema"] = {"type": "array"}
        malformed["description"] = "  "
        malformed["annotations"] = []
        ok, result, errors = self.audit_fake_paged_server([
            {"resultType": "complete", "tools": [tool_descriptor("tool_a")], "nextCursor": "page-2"},
            {"resultType": "complete", "tools": [malformed]},
        ], expected_min_tools=2)

        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "MCP_CONFIG_AUDIT_FAILED")
        self.assertEqual(result["smoke"]["page_count"], 2)
        self.assertEqual(result["smoke"]["invalid_descriptor_count"], 4)
        self.assertEqual(result["smoke"]["descriptor_issues"], [
            {"page": 2, "index": 0, "path": "description"},
            {"page": 2, "index": 0, "path": "inputSchema.type"},
            {"page": 2, "index": 0, "path": "outputSchema.type"},
            {"page": 2, "index": 0, "path": "annotations"},
        ])

    def test_audit_caps_reported_descriptor_diagnostics(self):
        descriptors = []
        for index in range(25):
            descriptor = tool_descriptor(f"tool_{index}")
            descriptor["inputSchema"] = {"type": "string"}
            descriptors.append(descriptor)
        ok, result, _ = self.audit_fake_paged_server([
            {"resultType": "complete", "tools": descriptors},
        ], expected_min_tools=25)

        self.assertFalse(ok)
        self.assertEqual(result["smoke"]["invalid_descriptor_count"], 20)
        self.assertEqual(len(result["smoke"]["descriptor_issues"]), 20)

    def test_audit_recursively_validates_schema_paths_and_keyword_shapes(self):
        invalid = tool_descriptor("nested_invalid")
        invalid["inputSchema"] = {
            "type": "object",
            "properties": {
                "profile": {
                    "type": "object",
                    "properties": {"age": {"type": "integer", "minimum": "zero"}},
                    "required": "age",
                    "dependentRequired": {"age": ["name", "name"]},
                },
                "tags": {
                    "type": "array", "items": {"type": "string", "maxLength": -1},
                    "prefixItems": [{"type": "string"}], "uniqueItems": "false",
                },
            },
        }
        valid = tool_descriptor("nested_valid")
        valid["inputSchema"] = {
            "type": "object",
            "properties": {
                "profile": {
                    "type": "object",
                    "properties": {"age": {"type": ["integer", "null"], "minimum": 0}},
                    "required": ["age"],
                },
                "tags": {"type": "array", "items": {"type": "string", "maxLength": 64}},
            },
        }
        ok, result, errors = self.audit_fake_paged_server([
            {"resultType": "complete", "tools": [valid, invalid]},
        ], expected_min_tools=2)

        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "MCP_CONFIG_AUDIT_FAILED")
        paths = [entry["path"] for entry in result["smoke"]["descriptor_issues"]]
        self.assertIn("inputSchema.properties.profile.required", paths)
        self.assertIn("inputSchema.properties.profile.properties.age.minimum", paths)
        self.assertIn("inputSchema.properties.profile.dependentRequired", paths)
        self.assertIn("inputSchema.properties.tags.items.maxLength", paths)
        self.assertIn("inputSchema.properties.tags.uniqueItems", paths)

    def test_audit_rejects_invalid_initialize_metadata_and_later_audit_succeeds(self):
        invalid_initialize_results = (
            {"protocolVersion": "2025-11-25", "capabilities": {"tools": {}}, "serverInfo": {"name": " ", "version": "1"}},
            {"protocolVersion": "2025-11-25", "capabilities": {"tools": {}}, "serverInfo": {"name": "fake", "version": ""}},
            {"protocolVersion": "2025-11-25", "capabilities": {}, "serverInfo": {"name": "fake", "version": "1"}},
            {"protocolVersion": "2025-11-25", "capabilities": {"tools": []}, "serverInfo": {"name": "fake", "version": "1"}},
            {"protocolVersion": "2025-11-25", "capabilities": {"tools": {"listChanged": "yes"}}, "serverInfo": {"name": "fake", "version": "1"}},
        )
        for initialize in invalid_initialize_results:
            with self.subTest(initialize=initialize):
                ok, result, errors = self.audit_fake_paged_server([
                    {"_initialize": initialize, "resultType": "complete", "tools": []},
                ])
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "MCP_CONFIG_AUDIT_FAILED")
                self.assertEqual(result["smoke"]["page_count"], 0)
                self.assertLess(len(result["smoke"]["error"]), 160)

        ok, _, errors = self.audit_fake_paged_server([
            {"resultType": "complete", "tools": [tool_descriptor("valid_after_bad_initialize")]},
        ])
        self.assertTrue(ok, errors)

    def test_audit_validates_optional_implementation_metadata_without_fetching_icons(self):
        valid_initialize = {
            "protocolVersion": "2025-11-25",
            "capabilities": {"tools": {}},
            "serverInfo": {
                "name": "fake", "version": "1", "title": "Fake server",
                "description": "A test implementation.",
                "websiteUrl": "https://example.test/docs",
                "icons": [{
                    "src": "data:image/png;base64,AAAA", "mimeType": "image/png",
                    "sizes": ["48x48", "any"], "theme": "light",
                }],
            },
        }
        ok, _, errors = self.audit_fake_paged_server([
            {"_initialize": valid_initialize, "resultType": "complete", "tools": [tool_descriptor("icon_server")]},
        ])
        self.assertTrue(ok, errors)

        invalid_info = (
            {"title": 4},
            {"websiteUrl": "file:///private"},
            {"icons": "not-an-array"},
            {"icons": [{"src": "javascript:alert(1)"}]},
            {"icons": [{"src": "https://example.test/icon.png", "mimeType": 5}]},
            {"icons": [{"src": "https://example.test/icon.png", "sizes": "48x48"}]},
            {"icons": [{"src": "https://example.test/icon.png", "theme": "sepia"}]},
        )
        for optional_fields in invalid_info:
            with self.subTest(optional_fields=optional_fields):
                server_info = {"name": "fake", "version": "1", **optional_fields}
                initialize = {
                    "protocolVersion": "2025-11-25", "capabilities": {"tools": {}},
                    "serverInfo": server_info,
                }
                ok, result, errors = self.audit_fake_paged_server([
                    {"_initialize": initialize, "resultType": "complete", "tools": [tool_descriptor("bad_metadata")]},
                ])
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "MCP_CONFIG_AUDIT_FAILED")
                self.assertEqual(result["smoke"]["page_count"], 0)
                self.assertLess(len(result["smoke"]["error"]), 200)

    def test_audit_rejects_oversized_stdout_and_reaps_server(self):
        children = []
        real_popen = subprocess.Popen

        def track_process(*args, **kwargs):
            process = real_popen(*args, **kwargs)
            children.append(process)
            return process

        with patch("wps_ai_agent_cli.mcp_config_audit.subprocess.Popen", side_effect=track_process):
            ok, result, errors = self.audit_fake_paged_server([{"_oversized": True}])

        self.assertFalse(ok)
        self.assertEqual(errors[0]["code"], "MCP_CONFIG_AUDIT_FAILED")
        self.assertIn("stdout line exceeded", result["smoke"]["error"])
        self.assertEqual(len(children), 1)
        self.assertIsNotNone(children[0].poll())

    def test_audit_drains_large_stderr_but_retains_only_bounded_prefix(self):
        ok, result, errors = self.audit_fake_paged_server([
            {"_stderrFlood": True, "resultType": "complete", "tools": [tool_descriptor("tool_a")]},
        ])

        self.assertTrue(ok, errors)
        self.assertEqual(len(result["smoke"]["stderr"]), 8192)

    def test_audit_normalizes_invalid_utf8_malformed_and_deep_json(self):
        real_popen = subprocess.Popen
        for mode, expected in (
            ("_invalidUtf8", "not valid UTF-8"),
            ("_malformedJson", "Expecting"),
            ("_deepJson", "invalid json-rpc response"),
        ):
            children = []

            def track_process(*args, **kwargs):
                process = real_popen(*args, **kwargs)
                children.append(process)
                return process

            with self.subTest(mode=mode), patch(
                "wps_ai_agent_cli.mcp_config_audit.subprocess.Popen", side_effect=track_process,
            ):
                ok, result, errors = self.audit_fake_paged_server([{mode: True}])
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "MCP_CONFIG_AUDIT_FAILED")
                self.assertIn(expected.lower(), result["smoke"]["error"].lower())
                self.assertLess(len(result["smoke"]["error"]), 256)
                self.assertEqual(len(children), 1)
                self.assertIsNotNone(children[0].poll())

        ok, _, errors = self.audit_fake_paged_server([
            {"resultType": "complete", "tools": [tool_descriptor("tool_after_bad_server")]},
        ])
        self.assertTrue(ok, errors)


if __name__ == "__main__":
    unittest.main()
