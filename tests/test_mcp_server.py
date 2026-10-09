import base64
import io
import json
import unittest
import os
import subprocess
import sys
from pathlib import Path
from queue import Queue
from tempfile import TemporaryDirectory
from threading import Event, Thread
from unittest.mock import patch

from wps_ai_agent_cli.mcp_schema import list_mcp_tool_schemas
from wps_ai_agent_cli.mcp_server import (
    MCP_STDIO_MAX_LINE_CHARS,
    MCP_PROTOCOL_VERSION,
    MCP_TOOLS_PAGE_SIZE,
    MCP_TOOLS_CURSOR_MAX_LENGTH,
    handle_mcp_json,
    handle_mcp_request,
    serve_stdio,
)


def initialize_params(protocol_version=MCP_PROTOCOL_VERSION):
    return {
        "protocolVersion": protocol_version,
        "capabilities": {},
        "clientInfo": {"name": "wps-cli-test", "version": "1"},
    }


class McpServerTests(unittest.TestCase):
    def test_request_envelope_rejects_invalid_versions_methods_ids_and_params(self):
        invalid_messages = (
            {"id": 1, "method": "initialize"},
            {"jsonrpc": "1.0", "id": 1, "method": "initialize"},
            {"jsonrpc": "2.0", "id": 1},
            {"jsonrpc": "2.0", "id": 1, "method": ""},
            {"jsonrpc": "2.0", "id": 1, "method": 7},
            {"jsonrpc": "2.0", "id": None, "method": "initialize"},
            {"jsonrpc": "2.0", "id": True, "method": "initialize"},
            {"jsonrpc": "2.0", "id": 1.5, "method": "initialize"},
            {"jsonrpc": "2.0", "id": {}, "method": "initialize"},
            {"jsonrpc": "2.0", "id": [], "method": "initialize"},
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": []},
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": None},
            {"jsonrpc": "2.0", "id": 1, "method": "notifications/initialized"},
        )
        for message in invalid_messages:
            with self.subTest(message=message):
                response = handle_mcp_request(message)
                self.assertEqual(response["error"]["code"], -32600)
                self.assertIsNone(response["id"])

    def test_notifications_are_silent_and_idless_requests_cannot_run_tools(self):
        with patch("wps_ai_agent_cli.mcp_server.call_mcp_tool") as call_tool:
            response = handle_mcp_request({
                "jsonrpc": "2.0", "method": "tools/call",
                "params": {"name": "wps_agent_tasks", "arguments": {}},
            })
        self.assertEqual(response["error"]["code"], -32600)
        self.assertIsNone(response["id"])
        call_tool.assert_not_called()

        self.assertIsNone(handle_mcp_request({
            "jsonrpc": "2.0", "method": "notifications/initialized",
        }))
        self.assertIsNone(handle_mcp_request({
            "jsonrpc": "2.0", "method": "notifications/future-event", "params": {},
        }))

    def test_request_envelope_preserves_valid_string_and_integer_ids(self):
        for request_id in (0, "request-id"):
            with self.subTest(request_id=request_id):
                response = handle_mcp_request({
                    "jsonrpc": "2.0", "id": request_id, "method": "initialize",
                    "params": initialize_params(),
                })
                self.assertEqual(response["id"], request_id)
                self.assertIn("protocolVersion", response["result"])

    def test_initialize_selects_supported_version_and_validates_required_params(self):
        for requested_version in (MCP_PROTOCOL_VERSION, "future-unknown-version"):
            with self.subTest(requested_version=requested_version):
                response = handle_mcp_request({
                    "jsonrpc": "2.0", "id": "negotiation", "method": "initialize",
                    "params": initialize_params(requested_version),
                })
                self.assertEqual(response["id"], "negotiation")
                self.assertEqual(response["result"]["protocolVersion"], MCP_PROTOCOL_VERSION)

        invalid_params = (
            {},
            {"protocolVersion": 3, "capabilities": {}, "clientInfo": {"name": "x", "version": "1"}},
            {"protocolVersion": MCP_PROTOCOL_VERSION, "capabilities": [], "clientInfo": {"name": "x", "version": "1"}},
            {"protocolVersion": MCP_PROTOCOL_VERSION, "capabilities": {}, "clientInfo": {"name": "x"}},
        )
        for params in invalid_params:
            with self.subTest(params=params):
                response = handle_mcp_request({
                    "jsonrpc": "2.0", "id": 17, "method": "initialize", "params": params,
                })
                self.assertEqual(response["id"], 17)
                self.assertEqual(response["error"]["code"], -32602)

    def test_ping_returns_empty_result_and_rejects_nonempty_params(self):
        for params in (None, {}):
            message = {"jsonrpc": "2.0", "id": "ping", "method": "ping"}
            if params is not None:
                message["params"] = params
            self.assertEqual(handle_mcp_request(message), {
                "jsonrpc": "2.0", "id": "ping", "result": {},
            })

        response = handle_mcp_request({
            "jsonrpc": "2.0", "id": "ping-invalid", "method": "ping",
            "params": {"unexpected": True},
        })
        self.assertEqual(response["error"]["code"], -32602)

    def test_stdio_ping_works_after_handshake_and_session_remains_usable(self):
        requests = (
            {"jsonrpc": "2.0", "id": "init", "method": "initialize", "params": initialize_params()},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": "ping", "method": "ping", "params": {}},
            {"jsonrpc": "2.0", "id": "list", "method": "tools/list", "params": {}},
        )
        output = io.StringIO()
        self.assertEqual(serve_stdio(io.StringIO("\n".join(map(json.dumps, requests)) + "\n"), output), 0)
        responses = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([response["id"] for response in responses], ["init", "ping", "list"])
        self.assertEqual(responses[1]["result"], {})
        self.assertTrue(responses[2]["result"]["tools"])

    def test_subprocess_initialize_negotiates_and_survives_invalid_params(self):
        root = Path(__file__).resolve().parents[1]
        env = dict(os.environ, PYTHONPATH=str(root / "src"))
        process = subprocess.Popen(
            [sys.executable, "-m", "wps_ai_agent_cli", "mcp-server"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", cwd=root, env=env,
        )
        replies = Queue()

        def read_replies():
            for line in process.stdout:
                replies.put(line)

        reader = Thread(target=read_replies)
        reader.start()
        try:
            requests = (
                {"jsonrpc": "2.0", "id": "malformed", "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "id": "fallback", "method": "initialize",
                 "params": initialize_params("future-unknown-version")},
            )
            responses = []
            for request in requests:
                process.stdin.write(json.dumps(request) + "\n")
                process.stdin.flush()
                responses.append(json.loads(replies.get(timeout=10)))

            self.assertEqual(responses[0]["id"], "malformed")
            self.assertEqual(responses[0]["error"]["code"], -32602)
            self.assertEqual(responses[1]["id"], "fallback")
            self.assertEqual(responses[1]["result"]["protocolVersion"], MCP_PROTOCOL_VERSION)
            process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
            process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": "still-live", "method": "tools/list", "params": {}}) + "\n")
            process.stdin.flush()
            response = json.loads(replies.get(timeout=10))
            self.assertEqual(response["id"], "still-live")
            self.assertTrue(response["result"]["tools"])
        finally:
            process.stdin.close()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            reader.join(timeout=5)
            stderr = process.stderr.read()
            process.stdout.close()
            process.stderr.close()

        self.assertEqual(process.returncode, 0, stderr)
        self.assertFalse(reader.is_alive())
        self.assertTrue(replies.empty())

    def test_subprocess_envelope_errors_do_not_execute_or_break_following_requests(self):
        root = Path(__file__).resolve().parents[1]
        env = dict(os.environ, PYTHONPATH=str(root / "src"))
        process = subprocess.Popen(
            [sys.executable, "-m", "wps_ai_agent_cli", "mcp-server"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", cwd=root, env=env,
        )
        replies = Queue()

        def read_replies():
            for line in process.stdout:
                replies.put(line)

        reader = Thread(target=read_replies)
        reader.start()
        try:
            for request in (
                {"jsonrpc": "1.0", "id": "bad-version", "method": "initialize"},
                {"jsonrpc": "2.0", "id": None, "method": "tools/call", "params": {
                    "name": "wps_agent_tasks", "arguments": {},
                }},
                {"jsonrpc": "2.0", "id": "bad-params", "method": "initialize", "params": []},
            ):
                process.stdin.write(json.dumps(request) + "\n")
                process.stdin.flush()
                response = json.loads(replies.get(timeout=10))
                self.assertEqual(response["error"]["code"], -32600)
                self.assertIsNone(response["id"])

            process.stdin.write(json.dumps({
                "jsonrpc": "2.0", "method": "notifications/initialized",
            }) + "\n")
            process.stdin.flush()
            valid = {"jsonrpc": "2.0", "id": "after-errors", "method": "initialize", "params": initialize_params()}
            process.stdin.write(json.dumps(valid) + "\n")
            process.stdin.flush()
            response = json.loads(replies.get(timeout=10))
            self.assertEqual(response["id"], "after-errors")
            self.assertIn("protocolVersion", response["result"])
            self.assertIsNone(process.poll())
        finally:
            process.stdin.close()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            reader.join(timeout=5)
            stderr = process.stderr.read()
            process.stdout.close()
            process.stderr.close()

        self.assertEqual(process.returncode, 0, stderr)
        self.assertFalse(reader.is_alive())
        self.assertTrue(replies.empty())

    def test_subprocess_stdio_recovers_after_malformed_and_non_object_requests(self):
        root = Path(__file__).resolve().parents[1]
        env = dict(os.environ, PYTHONPATH=str(root / "src"))
        process = subprocess.Popen(
            [sys.executable, "-m", "wps_ai_agent_cli", "mcp-server"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", cwd=root, env=env,
        )
        replies = Queue()

        def read_replies():
            for line in process.stdout:
                replies.put(line)

        reader = Thread(target=read_replies)
        reader.start()
        try:
            for payload, code in (("{not-json", -32700), ("[]", -32600), ("7", -32600)):
                process.stdin.write(payload + "\n")
                process.stdin.flush()
                response = json.loads(replies.get(timeout=10))
                self.assertEqual(response["jsonrpc"], "2.0")
                self.assertIsNone(response["id"])
                self.assertEqual(response["error"]["code"], code)

            request = {"jsonrpc": "2.0", "id": "recovered", "method": "initialize", "params": initialize_params()}
            process.stdin.write(json.dumps(request) + "\n")
            process.stdin.flush()
            response = json.loads(replies.get(timeout=10))
            self.assertEqual(response["id"], "recovered")
            self.assertIn("protocolVersion", response["result"])
            self.assertIsNone(process.poll())
        finally:
            process.stdin.close()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            reader.join(timeout=5)
            stderr = process.stderr.read()
            process.stdout.close()
            process.stderr.close()

        self.assertEqual(process.returncode, 0, stderr)
        self.assertFalse(reader.is_alive())
        self.assertTrue(replies.empty())

    def test_subprocess_stdio_completes_paginated_mcp_contract(self):
        root = Path(__file__).resolve().parents[1]
        env = dict(os.environ, PYTHONPATH=str(root / "src"))
        process = subprocess.Popen(
            [sys.executable, "-m", "wps_ai_agent_cli", "mcp-server"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", cwd=root, env=env,
        )
        replies = Queue()

        def read_replies():
            for line in process.stdout:
                replies.put(line)

        reader = Thread(target=read_replies)
        reader.start()

        def exchange(request_id, method, params):
            request = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
            process.stdin.write(json.dumps(request) + "\n")
            process.stdin.flush()
            response = json.loads(replies.get(timeout=10))
            self.assertEqual(response["id"], request_id)
            self.assertEqual(response["jsonrpc"], "2.0")
            return response

        expected_names = [schema["name"] for schema in list_mcp_tool_schemas()]
        try:
            initialize = exchange("init", "initialize", {
                **initialize_params(),
            })
            self.assertEqual(initialize["result"]["protocolVersion"], MCP_PROTOCOL_VERSION)
            process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
            process.stdin.flush()

            first = exchange("page-1", "tools/list", {})["result"]
            self.assertEqual(first["ttlMs"], 300000)
            self.assertEqual(first["cacheScope"], "public")
            self.assertEqual(len(first["tools"]), MCP_TOOLS_PAGE_SIZE)
            cursor = first["nextCursor"]

            second = exchange("page-2", "tools/list", {"cursor": cursor})["result"]
            self.assertEqual(second["ttlMs"], 300000)
            self.assertEqual(second["cacheScope"], "public")
            self.assertNotIn("nextCursor", second)
            names = [tool["name"] for tool in first["tools"] + second["tools"]]
            self.assertEqual(names, expected_names)
            self.assertEqual(len(names), len(set(names)))

            invalid_cursor = exchange("bad-cursor", "tools/list", {"cursor": "invalid"})
            self.assertEqual(invalid_cursor["error"]["code"], -32602)

            call = exchange("safe-call", "tools/call", {
                "name": "wps_agent_tasks", "arguments": {"phase": "phase3", "status": "next"},
            })["result"]
            self.assertFalse(call["isError"])
            self.assertTrue(call["structuredContent"]["mcp_call"]["response"]["ok"])
            self.assertIsNone(process.poll())
        finally:
            process.stdin.close()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            reader.join(timeout=5)
            stderr = process.stderr.read()
            process.stdout.close()
            process.stderr.close()

        self.assertEqual(process.returncode, 0, stderr)
        self.assertFalse(reader.is_alive())
        self.assertTrue(replies.empty())

    def test_subprocess_returns_batch_before_stdin_closes(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input"
            source.mkdir()
            (source / "a.html").write_text("<p>Live connection</p>", encoding="utf-8")
            env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
            process = subprocess.Popen(
                [sys.executable, "-m", "wps_ai_agent_cli", "mcp-server"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", cwd=root, env=env,
            )
            replies = Queue()

            def read_replies():
                for line in process.stdout:
                    replies.put(line)

            reader = Thread(target=read_replies)
            reader.start()
            try:
                initialize = {"jsonrpc": "2.0", "id": "init", "method": "initialize", "params": initialize_params()}
                process.stdin.write(json.dumps(initialize) + "\n")
                process.stdin.flush()
                self.assertEqual(json.loads(replies.get(timeout=10))["id"], "init")
                process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
                process.stdin.flush()
                for index in range(2):
                    request = {"jsonrpc": "2.0", "id": index, "method": "tools/call", "params": {
                        "name": "wps_agent_html_batch_convert", "arguments": {
                            "input_dir": str(source), "output_dir": str(root / f"output-{index}"), "mode": "docx",
                        },
                    }}
                    process.stdin.write(json.dumps(request) + "\n")
                    process.stdin.flush()
                    response = json.loads(replies.get(timeout=10))
                    self.assertEqual(response["id"], index)
                    self.assertFalse(response["result"]["isError"])
                    self.assertTrue((root / f"output-{index}" / "a.docx").is_file())
                self.assertIsNone(process.poll())
            finally:
                process.stdin.close()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                reader.join(timeout=5)
                stderr = process.stderr.read()
                process.stdout.close()
                process.stderr.close()
            self.assertEqual(process.returncode, 0, stderr)
            self.assertFalse(reader.is_alive())
            self.assertTrue(replies.empty())

    def test_batch_response_arrives_while_input_remains_open(self):
        waiting_for_input, response_flushed = Event(), Event()
        request = {"jsonrpc": "2.0", "id": "live", "method": "tools/call", "params": {
            "name": "wps_agent_html_batch_convert", "arguments": {},
        }}

        class OpenInput:
            def __iter__(self):
                yield json.dumps({
                    "jsonrpc": "2.0", "id": "init", "method": "initialize",
                    "params": initialize_params(),
                })
                yield json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})
                yield json.dumps(request)
                waiting_for_input.set()
                if not response_flushed.wait(2):
                    raise AssertionError("batch response required another input line or EOF")

        class Output(io.StringIO):
            def flush(self):
                super().flush()
                response_flushed.set()

        def complete(raw):
            self.assertTrue(waiting_for_input.wait(2))
            return {"jsonrpc": "2.0", "id": "live", "result": {"ok": True}}

        output = Output()
        with patch("wps_ai_agent_cli.mcp_server.handle_mcp_json", side_effect=complete):
            self.assertEqual(serve_stdio(OpenInput(), output), 0)
        responses = list(map(json.loads, output.getvalue().splitlines()))
        self.assertEqual(len(responses), 2)
        self.assertEqual(responses[1]["id"], "live")

    def test_initialize_returns_server_capabilities(self):
        response = handle_mcp_request(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": initialize_params()}
        )

        self.assertEqual(response["jsonrpc"], "2.0")
        self.assertEqual(response["id"], 1)
        self.assertIn("protocolVersion", response["result"])
        self.assertFalse(response["result"]["capabilities"]["tools"]["listChanged"])

    def test_tools_list_returns_mcp_tool_shapes(self):
        response = handle_mcp_request(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        )
        tools = response["result"]["tools"]
        names = {tool["name"] for tool in tools}

        self.assertEqual(response["result"]["resultType"], "complete")
        self.assertIn("wps_agent_tasks", names)
        self.assertIn("inputSchema", tools[0])
        self.assertEqual(len(tools), MCP_TOOLS_PAGE_SIZE)
        self.assertIn("nextCursor", response["result"])

    def test_tools_list_cursor_traversal_covers_catalog_once_in_order(self):
        expected_names = [schema["name"] for schema in list_mcp_tool_schemas()]
        cursor = None
        seen_cursors = set()
        names = []
        page_count = 0
        while True:
            params = {"cursor": cursor} if cursor is not None else {}
            response = handle_mcp_request({
                "jsonrpc": "2.0", "id": page_count + 1,
                "method": "tools/list", "params": params,
            })
            result = response["result"]
            page_count += 1
            self.assertEqual(result["resultType"], "complete")
            self.assertEqual(result["ttlMs"], 300000)
            self.assertEqual(result["cacheScope"], "public")
            self.assertLessEqual(len(result["tools"]), MCP_TOOLS_PAGE_SIZE)
            names.extend(tool["name"] for tool in result["tools"])
            cursor = result.get("nextCursor")
            if cursor is None:
                break
            self.assertIsInstance(cursor, str)
            self.assertNotIn(cursor, seen_cursors)
            seen_cursors.add(cursor)

        self.assertGreater(page_count, 1)
        self.assertEqual(names, expected_names)
        self.assertEqual(len(names), len(set(names)))

    def test_tools_list_rejects_invalid_and_stale_cursors(self):
        for cursor in ("", "not-a-cursor", 12, None):
            with self.subTest(cursor=cursor):
                response = handle_mcp_request({
                    "jsonrpc": "2.0", "id": "invalid", "method": "tools/list",
                    "params": {"cursor": cursor},
                })
                self.assertEqual(response["error"]["code"], -32602)

        first_page = handle_mcp_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {},
        })["result"]
        cursor_payload = first_page["nextCursor"]
        encoded = cursor_payload.encode("ascii")
        decoded = base64.urlsafe_b64decode(encoded + b"=" * (-len(encoded) % 4)).decode("ascii")
        fingerprint, _, _ = decoded.rpartition(":")
        out_of_range = base64.urlsafe_b64encode(
            f"{fingerprint}:{len(list_mcp_tool_schemas())}".encode("ascii")
        ).rstrip(b"=").decode("ascii")
        response = handle_mcp_request({
            "jsonrpc": "2.0", "id": 2, "method": "tools/list",
            "params": {"cursor": out_of_range},
        })
        self.assertEqual(response["error"]["code"], -32602)

        with patch("wps_ai_agent_cli.mcp_server.list_mcp_tool_schemas", return_value=list_mcp_tool_schemas()[:-1]):
            response = handle_mcp_request({
                "jsonrpc": "2.0", "id": 3, "method": "tools/list",
                "params": {"cursor": cursor_payload},
            })
        self.assertEqual(response["error"]["code"], -32602)

    def test_tools_list_rejects_oversized_cursor_before_base64_decode(self):
        oversized = "A" * (MCP_TOOLS_CURSOR_MAX_LENGTH + 1)
        with patch("wps_ai_agent_cli.mcp_server.base64.b64decode") as decode:
            response = handle_mcp_request({
                "jsonrpc": "2.0", "id": "oversized", "method": "tools/list",
                "params": {"cursor": oversized},
            })

        self.assertEqual(response["error"]["code"], -32602)
        decode.assert_not_called()

    def test_tools_call_uses_adapter(self):
        response = handle_mcp_request(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "wps_agent_tasks",
                    "arguments": {"phase": "phase2", "request_id": "mcp-server-test-001"},
                },
            }
        )

        self.assertFalse(response["result"]["isError"])
        self.assertEqual(
            response["result"]["structuredContent"]["mcp_call"]["response"]["command"],
            "tasks",
        )
        structured = response["result"]["structuredContent"]
        contract = list_mcp_tool_schemas()[0]["output_contract"]
        self.assertEqual(set(structured), set(contract["required"]))
        self.assertIsInstance(structured["mcp_call"], dict)
        self.assertIsInstance(structured["errors"], list)

    def test_tools_call_execution_error_matches_advertised_output_schema(self):
        tool = list_mcp_tool_schemas()[0]
        with patch(
            "wps_ai_agent_cli.mcp_server.call_mcp_tool",
            return_value=(False, {"tool_name": tool["name"], "response": None}, [
                {"code": "TEST_FAILURE", "message": "Synthetic adapter failure."},
            ]),
        ):
            response = handle_mcp_request({
                "jsonrpc": "2.0", "id": "tool-error", "method": "tools/call",
                "params": {"name": tool["name"], "arguments": {}},
            })

        self.assertTrue(response["result"]["isError"])
        structured = response["result"]["structuredContent"]
        contract = tool["output_contract"]
        self.assertEqual(set(structured), set(contract["required"]))
        self.assertIsInstance(structured["mcp_call"], dict)
        self.assertIsInstance(structured["errors"], list)
        for error in structured["errors"]:
            self.assertIsInstance(error["code"], str)
            self.assertIsInstance(error["message"], str)

    def test_tools_call_unknown_name_returns_protocol_error_without_adapter_dispatch(self):
        with patch("wps_ai_agent_cli.mcp_server.call_mcp_tool") as call_tool:
            response = handle_mcp_request({
                "jsonrpc": "2.0", "id": "unknown-tool", "method": "tools/call",
                "params": {"name": "wps_agent_not_in_catalog", "arguments": {}},
            })

        self.assertEqual(response["error"]["code"], -32602)
        self.assertEqual(response["id"], "unknown-tool")
        call_tool.assert_not_called()

    def test_tools_call_invalid_arguments_returns_protocol_error_without_adapter_dispatch(self):
        with patch("wps_ai_agent_cli.mcp_server.call_mcp_tool") as call_tool:
            response = handle_mcp_request({
                "jsonrpc": "2.0", "id": "invalid-arguments", "method": "tools/call",
                "params": {"name": "wps_agent_mcp_tools", "arguments": {"mutates_document": True}},
            })

        self.assertEqual(response["error"]["code"], -32602)
        self.assertEqual(response["id"], "invalid-arguments")
        self.assertEqual(response["error"]["data"][0]["code"], "MCP_ARGUMENT_TYPE_INVALID")
        call_tool.assert_not_called()

    def test_subprocess_unknown_tool_error_preserves_session(self):
        root = Path(__file__).resolve().parents[1]
        env = dict(os.environ, PYTHONPATH=str(root / "src"))
        process = subprocess.Popen(
            [sys.executable, "-m", "wps_ai_agent_cli", "mcp-server"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", cwd=root, env=env,
        )
        replies = Queue()

        def read_replies():
            for line in process.stdout:
                replies.put(line)

        reader = Thread(target=read_replies)
        reader.start()
        try:
            initialize = {"jsonrpc": "2.0", "id": "init", "method": "initialize", "params": initialize_params()}
            process.stdin.write(json.dumps(initialize) + "\n")
            process.stdin.flush()
            self.assertEqual(json.loads(replies.get(timeout=10))["id"], "init")
            process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
            unknown = {"jsonrpc": "2.0", "id": "unknown", "method": "tools/call", "params": {
                "name": "wps_agent_not_in_catalog", "arguments": {},
            }}
            process.stdin.write(json.dumps(unknown) + "\n")
            process.stdin.flush()
            invalid = json.loads(replies.get(timeout=10))
            self.assertEqual(invalid["id"], "unknown")
            self.assertEqual(invalid["error"]["code"], -32602)

            invalid_arguments = {"jsonrpc": "2.0", "id": "bad-type", "method": "tools/call", "params": {
                "name": "wps_agent_mcp_tools", "arguments": {"mutates_document": True},
            }}
            process.stdin.write(json.dumps(invalid_arguments) + "\n")
            process.stdin.flush()
            response = json.loads(replies.get(timeout=10))
            self.assertEqual(response["id"], "bad-type")
            self.assertEqual(response["error"]["code"], -32602)

            listing = {"jsonrpc": "2.0", "id": "after-error", "method": "tools/list", "params": {}}
            process.stdin.write(json.dumps(listing) + "\n")
            process.stdin.flush()
            response = json.loads(replies.get(timeout=10))
            self.assertEqual(response["id"], "after-error")
            self.assertTrue(response["result"]["tools"])
        finally:
            process.stdin.close()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            reader.join(timeout=5)
            stderr = process.stderr.read()
            process.stdout.close()
            process.stderr.close()

        self.assertEqual(process.returncode, 0, stderr)
        self.assertFalse(reader.is_alive())
        self.assertTrue(replies.empty())

    def test_handle_mcp_json_reports_parse_error(self):
        response = handle_mcp_json("{not-json")

        self.assertEqual(response["error"]["code"], -32700)

    def test_handle_mcp_json_rejects_duplicate_members_recursively(self):
        for raw in (
            '{"jsonrpc":"2.0","id":"first","id":"second","method":"tools/list"}',
            '{"jsonrpc":"2.0","id":"duplicate-method","method":"tools/list","method":"initialize"}',
            '{"jsonrpc":"2.0","id":"nested","method":"tools/call","params":{"name":"wps_agent_tasks","arguments":{"phase":"phase2","phase":"phase3"}}}',
        ):
            with self.subTest(raw=raw):
                response = handle_mcp_json(raw)
                self.assertEqual(response["error"]["code"], -32600)
                self.assertIsNone(response["id"])

    def test_handle_mcp_json_rejects_nonstandard_numeric_constants_recursively(self):
        for raw in (
            "NaN",
            "Infinity",
            "-Infinity",
            '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"value":NaN}}',
        ):
            with self.subTest(raw=raw):
                response = handle_mcp_json(raw)
                self.assertEqual(response["error"]["code"], -32700)
                self.assertIsNone(response["id"])

    def test_stdio_rejects_nonstandard_constant_and_continues(self):
        root = Path(__file__).resolve().parents[1]
        env = dict(os.environ, PYTHONPATH=str(root / "src"))
        process = subprocess.Popen(
            [sys.executable, "-m", "wps_ai_agent_cli", "mcp-server"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", cwd=root, env=env,
        )
        replies = Queue()

        def read_replies():
            for line in process.stdout:
                replies.put(line)

        reader = Thread(target=read_replies)
        reader.start()
        try:
            initialize = {"jsonrpc": "2.0", "id": "init", "method": "initialize", "params": initialize_params()}
            process.stdin.write(json.dumps(initialize) + "\n")
            process.stdin.flush()
            self.assertEqual(json.loads(replies.get(timeout=10))["id"], "init")
            process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
            process.stdin.write('{"jsonrpc":"2.0","id":"bad","method":"tools/list","params":{"x":-Infinity}}\n')
            process.stdin.flush()
            invalid = json.loads(replies.get(timeout=10))
            self.assertEqual(invalid["error"]["code"], -32700)
            self.assertIsNone(invalid["id"])

            request = {"jsonrpc": "2.0", "id": "valid", "method": "tools/list", "params": {}}
            process.stdin.write(json.dumps(request) + "\n")
            process.stdin.flush()
            response = json.loads(replies.get(timeout=10))
            self.assertEqual(response["id"], "valid")
            self.assertTrue(response["result"]["tools"])
        finally:
            process.stdin.close()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            reader.join(timeout=5)
            stderr = process.stderr.read()
            process.stdout.close()
            process.stderr.close()

        self.assertEqual(process.returncode, 0, stderr)
        self.assertFalse(reader.is_alive())
        self.assertTrue(replies.empty())

    def test_stdio_rejects_nested_duplicate_before_tool_side_effect_and_recovers(self):
        root = Path(__file__).resolve().parents[1]
        env = dict(os.environ, PYTHONPATH=str(root / "src"))
        with TemporaryDirectory() as directory:
            workspace = Path(directory)
            source = workspace / "input"
            source.mkdir()
            (source / "sample.html").write_text("<p>duplicate-key</p>", encoding="utf-8")
            output = workspace / "output"
            process = subprocess.Popen(
                [sys.executable, "-m", "wps_ai_agent_cli", "mcp-server"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", cwd=workspace, env=env,
            )
            replies = Queue()

            def read_replies():
                for line in process.stdout:
                    replies.put(line)

            reader = Thread(target=read_replies)
            reader.start()
            try:
                initialize = {"jsonrpc": "2.0", "id": "init", "method": "initialize", "params": initialize_params()}
                process.stdin.write(json.dumps(initialize) + "\n")
                process.stdin.flush()
                self.assertEqual(json.loads(replies.get(timeout=10))["id"], "init")
                process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")

                duplicate_call = (
                    '{"jsonrpc":"2.0","id":"ambiguous","method":"tools/call","params":'
                    '{"name":"wps_agent_html_batch_convert","arguments":{"input_dir":'
                    + json.dumps(str(source)) + ',"output_dir":' + json.dumps(str(output))
                    + ',"mode":"docx","mode":"pdf"}}}'
                )
                process.stdin.write(duplicate_call + "\n")
                process.stdin.flush()
                invalid = json.loads(replies.get(timeout=10))
                self.assertEqual(invalid["error"]["code"], -32600)
                self.assertIsNone(invalid["id"])
                self.assertFalse(output.exists())

                listing = {"jsonrpc": "2.0", "id": "after-duplicate", "method": "tools/list", "params": {}}
                process.stdin.write(json.dumps(listing) + "\n")
                process.stdin.flush()
                response = json.loads(replies.get(timeout=10))
                self.assertEqual(response["id"], "after-duplicate")
                self.assertTrue(response["result"]["tools"])
                self.assertIsNone(process.poll())
            finally:
                process.stdin.close()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                reader.join(timeout=5)
                stderr = process.stderr.read()
                process.stdout.close()
                process.stderr.close()

            self.assertEqual(process.returncode, 0, stderr)
            self.assertFalse(reader.is_alive())
            self.assertTrue(replies.empty())

    def test_serve_stdio_writes_line_delimited_json_rpc(self):
        messages = (
            {"jsonrpc": "2.0", "id": "init", "method": "initialize", "params": initialize_params()},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
        input_stream = io.StringIO("\n".join(json.dumps(message) for message in messages) + "\n")
        output_stream = io.StringIO()

        exit_code = serve_stdio(input_stream=input_stream, output_stream=output_stream)
        responses = [json.loads(line) for line in output_stream.getvalue().splitlines()]

        self.assertEqual(exit_code, 0)
        self.assertEqual(responses[0]["id"], "init")
        self.assertEqual(responses[1]["id"], 1)
        self.assertIn("tools", responses[1]["result"])

    def test_stdio_line_limit_accepts_boundary_and_recovers_after_oversized_record(self):
        max_chars = 512
        messages = [
            {"jsonrpc": "2.0", "id": "init", "method": "initialize", "params": initialize_params()},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
        ]
        exact_request = json.dumps({"jsonrpc": "2.0", "id": "exact", "method": "unknown/method"})
        exact_line = exact_request + " " * (max_chars - len(exact_request) - 1) + "\n"
        oversized_line = " " * (max_chars + 30000) + "\n"
        following = json.dumps({"jsonrpc": "2.0", "id": "following", "method": "tools/list", "params": {}}) + "\n"
        payload = "\n".join(json.dumps(message) for message in messages) + "\n"
        output_stream = io.StringIO()
        with patch("wps_ai_agent_cli.mcp_server.MCP_STDIO_MAX_LINE_CHARS", max_chars):
            self.assertEqual(serve_stdio(io.StringIO(payload + exact_line + oversized_line + following), output_stream), 0)

        responses = [json.loads(line) for line in output_stream.getvalue().splitlines()]
        self.assertEqual(responses[1]["id"], "exact")
        self.assertEqual(responses[1]["error"]["code"], -32601)
        self.assertEqual(responses[2]["error"]["code"], -32600)
        self.assertIsNone(responses[2]["id"])
        self.assertLessEqual(len(responses[2]["error"]["message"]), 80)
        self.assertEqual(responses[3]["id"], "following")
        self.assertTrue(responses[3]["result"]["tools"])

    def test_subprocess_drains_oversized_record_and_handles_following_request(self):
        root = Path(__file__).resolve().parents[1]
        env = dict(os.environ, PYTHONPATH=str(root / "src"))
        process = subprocess.Popen(
            [sys.executable, "-m", "wps_ai_agent_cli", "mcp-server"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", cwd=root, env=env,
        )
        replies = Queue()

        def read_replies():
            for line in process.stdout:
                replies.put(line)

        reader = Thread(target=read_replies)
        reader.start()
        try:
            initialize = {"jsonrpc": "2.0", "id": "init", "method": "initialize", "params": initialize_params()}
            process.stdin.write(json.dumps(initialize) + "\n")
            process.stdin.flush()
            self.assertEqual(json.loads(replies.get(timeout=10))["id"], "init")
            process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
            process.stdin.write(" " * (MCP_STDIO_MAX_LINE_CHARS + 30000) + "\n")
            process.stdin.flush()
            oversized = json.loads(replies.get(timeout=10))
            self.assertEqual(oversized["error"]["code"], -32600)
            self.assertIsNone(oversized["id"])

            request = {"jsonrpc": "2.0", "id": "recovered", "method": "tools/list", "params": {}}
            process.stdin.write(json.dumps(request) + "\n")
            process.stdin.flush()
            response = json.loads(replies.get(timeout=10))
            self.assertEqual(response["id"], "recovered")
            self.assertTrue(response["result"]["tools"])
            self.assertIsNone(process.poll())
        finally:
            process.stdin.close()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            reader.join(timeout=5)
            stderr = process.stderr.read()
            process.stdout.close()
            process.stderr.close()

        self.assertEqual(process.returncode, 0, stderr)
        self.assertFalse(reader.is_alive())
        self.assertTrue(replies.empty())

    def test_stdio_rejects_reused_request_id_before_mutating_dispatch(self):
        root = Path(__file__).resolve().parents[1]
        env = dict(os.environ, PYTHONPATH=str(root / "src"))
        with TemporaryDirectory() as directory:
            workspace = Path(directory)
            source = workspace / "input"
            source.mkdir()
            (source / "sample.html").write_text("<p>request-id</p>", encoding="utf-8")
            output = workspace / "output"
            process = subprocess.Popen(
                [sys.executable, "-m", "wps_ai_agent_cli", "mcp-server"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", cwd=workspace, env=env,
            )
            replies = Queue()

            def read_replies():
                for line in process.stdout:
                    replies.put(line)

            reader = Thread(target=read_replies)
            reader.start()
            try:
                invalid_initialize = {
                    "jsonrpc": "2.0", "id": "reserved", "method": "initialize", "params": {},
                }
                process.stdin.write(json.dumps(invalid_initialize) + "\n")
                process.stdin.flush()
                self.assertEqual(json.loads(replies.get(timeout=10))["error"]["code"], -32602)

                initialize = {"jsonrpc": "2.0", "id": "init", "method": "initialize", "params": initialize_params()}
                process.stdin.write(json.dumps(initialize) + "\n")
                process.stdin.flush()
                self.assertEqual(json.loads(replies.get(timeout=10))["id"], "init")
                process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")

                duplicate_call = {"jsonrpc": "2.0", "id": "reserved", "method": "tools/call", "params": {
                    "name": "wps_agent_html_batch_convert", "arguments": {
                        "input_dir": str(source), "output_dir": str(output), "mode": "docx",
                    },
                }}
                process.stdin.write(json.dumps(duplicate_call) + "\n")
                process.stdin.flush()
                duplicate_response = json.loads(replies.get(timeout=10))
                self.assertEqual(duplicate_response["id"], "reserved")
                self.assertEqual(duplicate_response["error"]["code"], -32600)
                self.assertFalse(output.exists())

                listing = {"jsonrpc": "2.0", "id": "unique", "method": "tools/list", "params": {}}
                process.stdin.write(json.dumps(listing) + "\n")
                process.stdin.flush()
                response = json.loads(replies.get(timeout=10))
                self.assertEqual(response["id"], "unique")
                self.assertTrue(response["result"]["tools"])
                self.assertIsNone(process.poll())
            finally:
                process.stdin.close()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                reader.join(timeout=5)
                stderr = process.stderr.read()
                process.stdout.close()
                process.stderr.close()

            self.assertEqual(process.returncode, 0, stderr)
            self.assertFalse(reader.is_alive())
            self.assertTrue(replies.empty())

    def test_stdio_requires_initialize_and_initialized_before_operations(self):
        root = Path(__file__).resolve().parents[1]
        env = dict(os.environ, PYTHONPATH=str(root / "src"))
        process = subprocess.Popen(
            [sys.executable, "-m", "wps_ai_agent_cli", "mcp-server"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", cwd=root, env=env,
        )
        replies = Queue()

        def read_replies():
            for line in process.stdout:
                replies.put(line)

        reader = Thread(target=read_replies)
        reader.start()
        try:
            preinit = {"jsonrpc": "2.0", "id": "preinit", "method": "tools/list", "params": {}}
            process.stdin.write(json.dumps(preinit) + "\n")
            process.stdin.flush()
            response = json.loads(replies.get(timeout=10))
            self.assertEqual(response["id"], "preinit")
            self.assertEqual(response["error"]["code"], -32600)

            initialize = {"jsonrpc": "2.0", "id": "init", "method": "initialize", "params": initialize_params()}
            process.stdin.write(json.dumps(initialize) + "\n")
            process.stdin.flush()
            response = json.loads(replies.get(timeout=10))
            self.assertEqual(response["id"], "init")
            self.assertIn("result", response)

            early = {"jsonrpc": "2.0", "id": "early", "method": "tools/list", "params": {}}
            process.stdin.write(json.dumps(early) + "\n")
            process.stdin.flush()
            response = json.loads(replies.get(timeout=10))
            self.assertEqual(response["id"], "early")
            self.assertEqual(response["error"]["code"], -32600)

            process.stdin.write(json.dumps({
                "jsonrpc": "2.0", "method": "notifications/initialized",
            }) + "\n")
            ready = {"jsonrpc": "2.0", "id": "ready", "method": "tools/list", "params": {}}
            duplicate_init = {"jsonrpc": "2.0", "id": "duplicate", "method": "initialize", "params": initialize_params()}
            process.stdin.write(json.dumps(ready) + "\n" + json.dumps(duplicate_init) + "\n")
            process.stdin.flush()
            ready_response = json.loads(replies.get(timeout=10))
            duplicate_response = json.loads(replies.get(timeout=10))
            self.assertEqual(ready_response["id"], "ready")
            self.assertTrue(ready_response["result"]["tools"])
            self.assertEqual(duplicate_response["id"], "duplicate")
            self.assertEqual(duplicate_response["error"]["code"], -32600)
            self.assertIsNone(process.poll())
        finally:
            process.stdin.close()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            reader.join(timeout=5)
            stderr = process.stderr.read()
            process.stdout.close()
            process.stderr.close()

        self.assertEqual(process.returncode, 0, stderr)
        self.assertFalse(reader.is_alive())
        self.assertTrue(replies.empty())

    def test_stdio_batch_call_can_be_cancelled_by_following_mcp_call(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "input", root / "output"
            source.mkdir()
            for name in ("a", "b"):
                (source / f"{name}.html").write_text(name, encoding="utf-8")
            started, release = Event(), Event()
            batch_request = {
                "jsonrpc": "2.0", "id": "batch", "method": "tools/call",
                "params": {"name": "wps_agent_html_batch_convert", "arguments": {
                    "input_dir": str(source), "output_dir": str(output), "mode": "pdf", "task_id": "stdio_cancel",
                }},
            }
            cancel_request = {
                "jsonrpc": "2.0", "id": "cancel", "method": "tools/call",
                "params": {"name": "wps_agent_task_status_update", "arguments": {
                    "task_id": "stdio_cancel", "state": "cancelled", "message": "stdio cancellation",
                }},
            }
            overlapping_request = {
                "jsonrpc": "2.0", "id": "overlap", "method": "tools/call",
                "params": {"name": "wps_agent_html_batch_convert", "arguments": {
                    "input_dir": str(source), "output_dir": str(root / "other-output"), "mode": "pdf", "task_id": "stdio_overlap",
                }},
            }

            class RequestStream:
                def __iter__(self):
                    yield json.dumps({
                        "jsonrpc": "2.0", "id": "init", "method": "initialize",
                        "params": initialize_params(),
                    })
                    yield json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})
                    yield json.dumps(batch_request)
                    if not started.wait(5):
                        raise AssertionError("batch renderer did not start")
                    yield json.dumps(overlapping_request)
                    yield "{broken"
                    yield json.dumps({"jsonrpc": "1.0", "id": "invalid", "method": "tools/list"})
                    yield json.dumps(cancel_request)
                    release.set()

            def render(path, destination, output_format):
                destination.write_bytes(b"PDF")
                started.set()
                if not release.wait(5):
                    raise AssertionError("batch renderer was not released")
                return True, {}, []

            output_stream = io.StringIO()
            with patch("wps_ai_agent_cli.task_status.task_status_state_path", side_effect=lambda workspace=".": root / "statuses.json"), \
                 patch("wps_ai_agent_cli.batch_conversion.render_html", side_effect=render):
                self.assertEqual(serve_stdio(RequestStream(), output_stream), 0)

            responses = {item["id"]: item for item in map(json.loads, output_stream.getvalue().splitlines())}
            self.assertEqual(responses["overlap"]["error"]["code"], -32000)
            parse_error = next(item for item in map(json.loads, output_stream.getvalue().splitlines()) if item.get("error", {}).get("code") == -32700)
            self.assertIsNone(parse_error["id"])
            invalid_request = next(
                item for item in map(json.loads, output_stream.getvalue().splitlines())
                if item.get("error", {}).get("code") == -32600
            )
            self.assertIsNone(invalid_request["id"])
            self.assertTrue(responses["cancel"]["result"]["structuredContent"]["mcp_call"]["response"]["ok"])
            batch_response = responses["batch"]["result"]["structuredContent"]["mcp_call"]["response"]
            self.assertTrue(batch_response["data"]["cancelled"])
            self.assertEqual(batch_response["data"]["summary"]["processed"], 1)
            self.assertEqual(batch_response["data"]["task_status"]["state"], "cancelled")
            self.assertTrue(Path(batch_response["data"]["manifest_path"]).is_file())

    def test_stdio_drains_completed_batch_once_at_eof(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "input", root / "output"
            source.mkdir()
            for name in ("a", "b"):
                (source / f"{name}.html").write_text(name, encoding="utf-8")
            request = {
                "jsonrpc": "2.0", "id": "complete", "method": "tools/call",
                "params": {"name": "wps_agent_html_batch_convert", "arguments": {
                    "input_dir": str(source), "output_dir": str(output), "mode": "pdf",
                }},
            }
            initialize = {"jsonrpc": "2.0", "id": "init", "method": "initialize", "params": initialize_params()}
            initialized = {"jsonrpc": "2.0", "method": "notifications/initialized"}

            def render(path, destination, output_format):
                destination.write_bytes(b"PDF")
                return True, {}, []

            output_stream = io.StringIO()
            with patch("wps_ai_agent_cli.batch_conversion.render_html", side_effect=render):
                session = "\n".join(map(json.dumps, (initialize, initialized, request))) + "\n"
                self.assertEqual(serve_stdio(io.StringIO(session), output_stream), 0)

            lines = output_stream.getvalue().splitlines()
            self.assertEqual(len(lines), 2)
            response = json.loads(lines[1])
            self.assertEqual(response["id"], "complete")
            batch_response = response["result"]["structuredContent"]["mcp_call"]["response"]
            self.assertEqual(batch_response["data"]["summary"]["passed"], 2)

    def test_stdio_contains_unexpected_batch_worker_exception(self):
        batch = {"jsonrpc": "2.0", "id": "broken-batch", "method": "tools/call", "params": {
            "name": "wps_agent_html_batch_convert", "arguments": {},
        }}
        listing = {"jsonrpc": "2.0", "id": "list", "method": "tools/list", "params": {}}
        initialize = {"jsonrpc": "2.0", "id": "init", "method": "initialize", "params": initialize_params()}
        initialized = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        stream = io.StringIO("\n".join(map(json.dumps, (initialize, initialized, batch, listing))) + "\n")
        output_stream = io.StringIO()
        with patch("wps_ai_agent_cli.mcp_server.handle_mcp_json", side_effect=RuntimeError("private failure detail")):
            self.assertEqual(serve_stdio(stream, output_stream), 0)

        responses = {item["id"]: item for item in map(json.loads, output_stream.getvalue().splitlines())}
        del responses["init"]
        self.assertEqual(responses["broken-batch"]["error"]["code"], -32603)
        self.assertNotIn("private failure detail", output_stream.getvalue())
        self.assertIn("tools", responses["list"]["result"])


if __name__ == "__main__":
    unittest.main()
