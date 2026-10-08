import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wps_ai_agent_cli.mcp_config_audit import audit_mcp_client_config
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
                "        response['result']={'protocolVersion':'2025-11-25','capabilities':{'tools':{}},'serverInfo':{'name':'fake','version':'1'}}",
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
            self.assertFalse(result["checks"][2]["passed"])

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
