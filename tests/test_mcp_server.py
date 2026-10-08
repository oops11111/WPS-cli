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
    MCP_TOOLS_PAGE_SIZE,
    handle_mcp_json,
    handle_mcp_request,
    serve_stdio,
)


class McpServerTests(unittest.TestCase):
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
        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0]["id"], "live")

    def test_initialize_returns_server_capabilities(self):
        response = handle_mcp_request(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
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

    def test_handle_mcp_json_reports_parse_error(self):
        response = handle_mcp_json("{not-json")

        self.assertEqual(response["error"]["code"], -32700)

    def test_serve_stdio_writes_line_delimited_json_rpc(self):
        input_stream = io.StringIO(
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
            + "\n"
        )
        output_stream = io.StringIO()

        exit_code = serve_stdio(input_stream=input_stream, output_stream=output_stream)
        response = json.loads(output_stream.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(response["id"], 1)
        self.assertIn("tools", response["result"])

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
            self.assertEqual(responses["invalid"]["error"]["code"], -32600)
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

            def render(path, destination, output_format):
                destination.write_bytes(b"PDF")
                return True, {}, []

            output_stream = io.StringIO()
            with patch("wps_ai_agent_cli.batch_conversion.render_html", side_effect=render):
                self.assertEqual(serve_stdio(io.StringIO(json.dumps(request) + "\n"), output_stream), 0)

            lines = output_stream.getvalue().splitlines()
            self.assertEqual(len(lines), 1)
            response = json.loads(lines[0])
            self.assertEqual(response["id"], "complete")
            batch_response = response["result"]["structuredContent"]["mcp_call"]["response"]
            self.assertEqual(batch_response["data"]["summary"]["passed"], 2)

    def test_stdio_contains_unexpected_batch_worker_exception(self):
        batch = {"jsonrpc": "2.0", "id": "broken-batch", "method": "tools/call", "params": {
            "name": "wps_agent_html_batch_convert", "arguments": {},
        }}
        listing = {"jsonrpc": "2.0", "id": "list", "method": "tools/list", "params": {}}
        stream = io.StringIO(json.dumps(batch) + "\n" + json.dumps(listing) + "\n")
        output_stream = io.StringIO()
        with patch("wps_ai_agent_cli.mcp_server.handle_mcp_json", side_effect=RuntimeError("private failure detail")):
            self.assertEqual(serve_stdio(stream, output_stream), 0)

        responses = {item["id"]: item for item in map(json.loads, output_stream.getvalue().splitlines())}
        self.assertEqual(responses["broken-batch"]["error"]["code"], -32603)
        self.assertNotIn("private failure detail", output_stream.getvalue())
        self.assertIn("tools", responses["list"]["result"])


if __name__ == "__main__":
    unittest.main()
