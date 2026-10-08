import unittest
import json
import hashlib
import io
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
from unittest.mock import patch

from wps_ai_agent_cli.mcp_adapter import build_cli_argv, call_mcp_tool, validate_mcp_tool_arguments
from wps_ai_agent_cli.mcp_schema import get_mcp_tool_schema, list_mcp_tool_schemas


class McpAdapterTests(unittest.TestCase):
    def test_catalog_input_schemas_use_only_supported_validation_keywords(self):
        supported_types = {"string", "integer", "number", "boolean", "array", "object"}
        supported_property_keywords = {
            "type", "description", "enum", "minimum", "maximum", "items",
            "minLength", "maxLength", "pattern",
        }
        for tool in list_mcp_tool_schemas():
            input_schema = tool["input_schema"]
            self.assertEqual(input_schema.get("type"), "object", tool["name"])
            self.assertIsInstance(input_schema.get("required"), list, tool["name"])
            self.assertIs(input_schema.get("additionalProperties"), False, tool["name"])
            for name, property_schema in input_schema["properties"].items():
                with self.subTest(tool=tool["name"], argument=name):
                    self.assertLessEqual(set(property_schema), supported_property_keywords)
                    self.assertIn(property_schema.get("type"), supported_types)
                    if property_schema.get("type") == "array":
                        self.assertIn(property_schema.get("items", {}).get("type"), supported_types)

    def test_validate_arguments_enforces_type_enum_bounds_and_array_items(self):
        cases = (
            ("wps_agent_spreadsheet_copy_sheet", {"document_id": "doc", "source_name": "A", "new_name": "B", "index": True}, "MCP_ARGUMENT_TYPE_INVALID"),
            ("wps_agent_com_smoke", {"component": "word"}, "MCP_ARGUMENT_ENUM_INVALID"),
            ("wps_agent_writer_structure", {"limit": 201}, "MCP_ARGUMENT_ABOVE_MAXIMUM"),
            ("wps_agent_writer_structure", {"offset": -1}, "MCP_ARGUMENT_BELOW_MINIMUM"),
            ("wps_agent_task_status_create", {"task_id": "task", "recovery_guidance": ["ok", 2]}, "MCP_ARGUMENT_ARRAY_ITEM_INVALID"),
            ("wps_agent_spreadsheet_set_sheet_visibility", {"document_id": "doc", "sheet_name": "S", "visible": False}, "MCP_ARGUMENT_TYPE_INVALID"),
            ("wps_agent_mcp_config_audit", {"server_name": "   "}, "MCP_ARGUMENT_PATTERN_MISMATCH"),
            ("wps_agent_mcp_config_audit", {"server_name": "x" * 257}, "MCP_ARGUMENT_STRING_TOO_LONG"),
        )
        for tool_name, arguments, expected_code in cases:
            with self.subTest(tool=tool_name, arguments=arguments):
                errors = validate_mcp_tool_arguments(tool_name, arguments)
                self.assertIn(expected_code, {error["code"] for error in errors})

    def test_batch_request_inspection_cli_and_mcp_share_read_only_record(self):
        from wps_ai_agent_cli.batch_conversion import _request_record_path
        from wps_ai_agent_cli.cli import run
        import io

        with TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("wps_ai_agent_cli.task_status.task_status_state_path", return_value=root / "statuses.json"):
                path = _request_record_path("inspect-me")
                path.parent.mkdir()
                path.write_text(json.dumps({
                    "request_id": "inspect-me", "state": "running",
                    "arguments": {"output_directory": str(root / "output")},
                }), encoding="utf-8")
                before = {entry: entry.read_bytes() for entry in path.parent.rglob("*") if entry.is_file()}
                output = io.StringIO()
                self.assertEqual(run(["html-batch-request", "--batch-request-id", "inspect-me"], output_stream=output), 0)
                cli_record = json.loads(output.getvalue())["data"]["batch_request"]
                ok, mcp_result, errors = call_mcp_tool("wps_agent_html_batch_request", {"batch_request_id": "inspect-me"})
                self.assertTrue(ok, errors)
                self.assertEqual(mcp_result["response"]["data"]["batch_request"], cli_record)
                verified, verified_result, errors = call_mcp_tool("wps_agent_html_batch_request", {"batch_request_id": "inspect-me", "verify": True})
                self.assertTrue(verified, errors)
                self.assertEqual(verified_result["response"]["validation"]["status"], "warning")
                self.assertEqual(verified_result["response"]["data"]["batch_request"]["evidence_status"], "failed")
                self.assertEqual({entry: entry.read_bytes() for entry in path.parent.rglob("*") if entry.is_file()}, before)
                self.assertFalse((root / "statuses.json").exists())

    def test_completed_batch_replays_through_mcp_without_rendering_again(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "input", root / "output"
            source.mkdir()
            (source / "a.html").write_text("A", encoding="utf-8")
            calls = []

            def render(path, destination, output_format):
                calls.append(path.name)
                destination.write_bytes(b"PDF")
                return True, {}, []

            args = {"input_dir": str(source), "output_dir": str(output), "mode": "pdf",
                    "task_id": "mcp-replay", "request_id": "request-replay"}
            with patch("wps_ai_agent_cli.task_status.task_status_state_path", return_value=root / "statuses.json"), \
                 patch("wps_ai_agent_cli.batch_conversion.render_html", side_effect=render):
                first_ok, first, first_errors = call_mcp_tool("wps_agent_html_batch_convert", args)
                replay_ok, replay, replay_errors = call_mcp_tool("wps_agent_html_batch_convert", args)
                changed = {**args, "output_dir": str(root / "changed-output")}
                changed_ok, changed_result, _ = call_mcp_tool("wps_agent_html_batch_convert", changed)

            self.assertTrue(first_ok, first_errors)
            self.assertTrue(replay_ok, replay_errors)
            self.assertTrue(replay["response"]["data"]["replayed"])
            self.assertEqual(replay["response"]["data"]["task_status"]["state"], "succeeded")
            self.assertEqual(calls, ["a.html"])
            self.assertFalse(changed_ok)
            self.assertEqual(changed_result["response"]["errors"][0]["code"], "BATCH_REPLAY_CONFLICT")
            self.assertFalse((root / "changed-output" / "a.pdf").exists())

    def test_adapter_captures_cli_output_without_process_stdout_mutation(self):
        process_stdout = io.StringIO()
        with patch("sys.stdout", process_stdout):
            ok, result, errors = call_mcp_tool("wps_agent_tasks", {"phase": "phase2"})
        self.assertTrue(ok, errors)
        self.assertEqual(process_stdout.getvalue(), "")
        self.assertEqual(result["response"]["command"], "tasks")

        from wps_ai_agent_cli.cli import run

        direct_output = io.StringIO()
        with patch("sys.stdout", process_stdout):
            self.assertEqual(run(["tasks", "--phase", "phase3"], output_stream=direct_output), 0)
        self.assertEqual(process_stdout.getvalue(), "")
        self.assertIn('"command": "tasks"', direct_output.getvalue())

    def test_controlled_html_import_and_verify_tools_map(self):
        ok, argv, schema, errors = build_cli_argv("wps_agent_html_controlled_import", {"input": "owned.html", "output": "owned.docx"})
        self.assertTrue(ok, errors)
        self.assertTrue(schema["mutates_document"])
        self.assertEqual(argv, ["html-controlled-import", "--input", "owned.html", "--output", "owned.docx"])
        ok, argv, schema, errors = build_cli_argv("wps_agent_html_roundtrip_verify", {"docx": "owned.docx", "mapping": "owned.docx.wpsmap.json"})
        self.assertTrue(ok, errors)
        self.assertFalse(schema["mutates_document"])
        self.assertEqual(argv[0], "html-roundtrip-verify")
        ok, argv, schema, errors = build_cli_argv("wps_agent_html_roundtrip_export", {"docx": "owned.docx", "mapping": "owned.docx.wpsmap.json", "output": "owned.html", "task_id": "export_1"})
        self.assertTrue(ok, errors)
        self.assertTrue(schema["mutates_document"])
        self.assertEqual(argv, ["html-roundtrip-export", "--docx", "owned.docx", "--mapping", "owned.docx.wpsmap.json", "--output", "owned.html", "--task-id", "export_1"])
    def test_html_batch_convert_maps_limits_and_runs_through_adapter(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "input", root / "output"
            source.mkdir()
            (source / "brief.html").write_text("<h1>Batch test</h1><p>Content</p>", encoding="utf-8")
            args = {"input_dir": str(source), "output_dir": str(output), "mode": "docx", "recursive": True, "task_id": "batch_mcp_test"}
            ok, argv, schema, errors = build_cli_argv("wps_agent_html_batch_convert", args)
            self.assertTrue(ok, errors)
            self.assertTrue(schema["mutates_document"])
            self.assertFalse(schema["requires_wps"])
            self.assertEqual(argv, ["html-batch-convert", "--input-dir", str(source), "--output-dir", str(output), "--mode", "docx", "--recursive", "--task-id", "batch_mcp_test"])
            with patch("wps_ai_agent_cli.task_status.task_status_state_path", return_value=root / "statuses.json"):
                ok, result, errors = call_mcp_tool("wps_agent_html_batch_convert", args)
            self.assertTrue(ok, errors)
            response = result["response"]
            self.assertEqual(response["data"]["summary"]["passed"], 1)
            self.assertTrue(Path(response["data"]["manifest_path"]).is_file())

    def test_batch_template_report_maps_and_runs_through_adapter(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "batch.json"
            template = root / "template.md"
            output = root / "report.md"
            source_root, output_root = root / "input", root / "artifacts"
            source_root.mkdir()
            output_root.mkdir()
            source_file, output_file = source_root / "a.html", output_root / "a.docx"
            source_file.write_bytes(b"source")
            output_file.write_bytes(b"docx")
            source_hash = hashlib.sha256(source_file.read_bytes()).hexdigest()
            output_hash = hashlib.sha256(output_file.read_bytes()).hexdigest()
            manifest.write_text(json.dumps({
                "schema_version": "wps-agent-batch-conversion/v1", "mode": "docx",
                "source_directory": str(source_root), "output_directory": str(output_root),
                "summary": {"total": 1, "passed": 1, "failed": 0},
                "files": [{"status": "passed", "relative_source": "a.html", "source": str(source_file), "output": str(output_file), "source_sha256": source_hash, "output_sha256": output_hash, "errors": []}],
            }), encoding="utf-8")
            template.write_text("{{total}} files\n{{files_table}}", encoding="utf-8")
            args = {"manifest": str(manifest), "template": str(template), "output": str(output), "task_id": "report_mcp_test"}
            ok, argv, schema, errors = build_cli_argv("wps_agent_batch_template_report", args)
            self.assertTrue(ok, errors)
            self.assertTrue(schema["mutates_document"])
            self.assertFalse(schema["requires_wps"])
            self.assertEqual(argv, ["batch-template-report", "--manifest", str(manifest), "--template", str(template), "--output", str(output), "--task-id", "report_mcp_test"])
            with patch("wps_ai_agent_cli.task_status.task_status_state_path", return_value=root / "statuses.json"):
                ok, result, errors = call_mcp_tool("wps_agent_batch_template_report", args)
            self.assertTrue(ok, errors)
            self.assertTrue(Path(result["response"]["data"]["output_path"]).is_file())

    def test_batch_adapter_can_be_cancelled_through_task_status_mcp_tool(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "input", root / "output"
            source.mkdir()
            for name in ("a", "b"):
                (source / f"{name}.html").write_text(name, encoding="utf-8")
            started, release = Event(), Event()
            outcome = {}

            def render(path, destination, output_format):
                destination.write_bytes(b"PDF")
                started.set()
                self.assertTrue(release.wait(5))
                return True, {}, []

            def worker():
                with patch("wps_ai_agent_cli.batch_conversion.render_html", side_effect=render):
                    outcome["result"] = call_mcp_tool("wps_agent_html_batch_convert", {
                        "input_dir": str(source), "output_dir": str(output), "mode": "pdf", "task_id": "mcp_batch_cancel",
                    })

            with patch("wps_ai_agent_cli.task_status.task_status_state_path", side_effect=lambda workspace=".": root / "statuses.json"):
                thread = Thread(target=worker)
                thread.start()
                self.assertTrue(started.wait(5))
                cancelled, update_result, errors = call_mcp_tool("wps_agent_task_status_update", {
                    "task_id": "mcp_batch_cancel", "state": "cancelled", "message": "cancelled from MCP",
                })
                self.assertTrue(cancelled, errors)
                self.assertTrue(update_result["response"]["ok"])
                release.set()
                thread.join(10)
                self.assertFalse(thread.is_alive())
            ok, result, errors = outcome["result"]
            self.assertFalse(ok)
            self.assertEqual(errors, [])
            self.assertTrue(result["response"]["data"]["cancelled"])
            self.assertEqual(result["response"]["data"]["summary"]["processed"], 1)
            self.assertEqual(result["response"]["data"]["task_status"]["state"], "cancelled")
            self.assertTrue(Path(result["response"]["data"]["manifest_path"]).is_file())
    def test_html_roundtrip_plan_tool_is_read_only_and_maps_input(self):
        ok, argv, schema, errors = build_cli_argv("wps_agent_html_roundtrip_plan", {"input": "owned.html"})
        self.assertTrue(ok, errors)
        self.assertFalse(schema["mutates_document"])
        self.assertEqual(argv, ["html-roundtrip-plan", "--input", "owned.html"])
    def test_html_editable_tool_maps_to_cli_with_task_id(self):
        ok, argv, schema, errors = build_cli_argv(
            "wps_agent_html_editable",
            {"input": "page.html", "output": "page.docx", "task_id": "html_task", "request_id": "html_req"},
        )
        self.assertTrue(ok, errors)
        self.assertEqual(schema["cli_command"], "html-editable")
        self.assertEqual(argv, ["html-editable", "--input", "page.html", "--output", "page.docx", "--task-id", "html_task", "--request-id", "html_req"])
    def test_spreadsheet_tab_color_tool_maps_to_cli(self):
        ok, argv, schema, errors = build_cli_argv("wps_agent_spreadsheet_set_sheet_tab_color", {"document_id": "sheet_1", "sheet_name": "Summary", "color": "#12ABEF", "dry_run": True})
        self.assertTrue(ok, errors)
        self.assertEqual(schema["cli_command"], "spreadsheet-set-sheet-tab-color")
        self.assertEqual(argv, ["spreadsheet-set-sheet-tab-color", "--document-id", "sheet_1", "--sheet-name", "Summary", "--color", "#12ABEF", "--dry-run"])
    def test_spreadsheet_copy_sheet_tool_maps_to_cli(self):
        ok, argv, schema, errors = build_cli_argv("wps_agent_spreadsheet_copy_sheet", {"document_id": "sheet_1", "source_name": "Source", "new_name": "Copy", "index": 2, "dry_run": True})
        self.assertTrue(ok, errors)
        self.assertEqual(schema["cli_command"], "spreadsheet-copy-sheet")
        self.assertEqual(argv, ["spreadsheet-copy-sheet", "--document-id", "sheet_1", "--source-name", "Source", "--new-name", "Copy", "--index", "2", "--dry-run"])
    def test_spreadsheet_delete_sheet_tool_maps_to_cli(self):
        ok, argv, schema, errors = build_cli_argv("wps_agent_spreadsheet_delete_sheet", {"document_id": "sheet_1", "sheet_name": "Remove", "dry_run": True})
        self.assertTrue(ok, errors)
        self.assertEqual(schema["cli_command"], "spreadsheet-delete-sheet")
        self.assertEqual(argv, ["spreadsheet-delete-sheet", "--document-id", "sheet_1", "--sheet-name", "Remove", "--dry-run"])
    def test_spreadsheet_visibility_tool_maps_to_cli(self):
        ok, argv, schema, errors = build_cli_argv("wps_agent_spreadsheet_set_sheet_visibility", {"document_id": "sheet_1", "sheet_name": "Hidden", "visible": "false"})
        self.assertTrue(ok, errors)
        self.assertEqual(schema["cli_command"], "spreadsheet-set-sheet-visibility")
        self.assertEqual(argv, ["spreadsheet-set-sheet-visibility", "--document-id", "sheet_1", "--sheet-name", "Hidden", "--visible", "false"])
    def test_spreadsheet_create_sheet_tool_maps_to_cli(self):
        ok, argv, schema, errors = build_cli_argv("wps_agent_spreadsheet_create_sheet", {"document_id": "sheet_1", "name": "New", "index": 2, "dry_run": True})
        self.assertTrue(ok, errors)
        self.assertEqual(schema["cli_command"], "spreadsheet-create-sheet")
        self.assertEqual(argv, ["spreadsheet-create-sheet", "--document-id", "sheet_1", "--name", "New", "--index", "2", "--dry-run"])
    def test_spreadsheet_rename_sheet_tool_maps_to_cli(self):
        ok, argv, schema, errors = build_cli_argv(
            "wps_agent_spreadsheet_rename_sheet",
            {"document_id": "sheet_1", "old_name": "Current", "new_name": "Archive", "dry_run": True},
        )
        self.assertTrue(ok)
        self.assertEqual(errors, [])
        self.assertEqual(schema["cli_command"], "spreadsheet-rename-sheet")
        self.assertEqual(argv, [
            "spreadsheet-rename-sheet", "--document-id", "sheet_1", "--old-name", "Current",
            "--new-name", "Archive", "--dry-run",
        ])

    def test_spreadsheet_sheets_tool_maps_to_cli(self):
        ok, argv, schema, errors = build_cli_argv(
            "wps_agent_spreadsheet_sheets", {"document_id": "sheet_1"},
        )
        self.assertTrue(ok)
        self.assertEqual(errors, [])
        self.assertEqual(schema["cli_command"], "spreadsheet-sheets")
        self.assertEqual(argv, ["spreadsheet-sheets", "--document-id", "sheet_1"])
        self.assertFalse(schema["mutates_document"])
        self.assertFalse(schema["requires_wps"])
        self.assertFalse(get_mcp_tool_schema("wps_agent_spreadsheet_sheets")["mutates_document"])

    def test_spreadsheet_inspect_tool_maps_to_cli(self):
        ok, argv, schema, errors = build_cli_argv(
            "wps_agent_spreadsheet_inspect",
            {"document_id": "sheet_1", "range": "A1:F1", "sheet": "Contract"},
        )
        self.assertTrue(ok)
        self.assertEqual(errors, [])
        self.assertEqual(schema["cli_command"], "spreadsheet-inspect")
        self.assertEqual(argv, [
            "spreadsheet-inspect", "--document-id", "sheet_1", "--range", "A1:F1",
            "--sheet", "Contract",
        ])

    def test_bookmark_tool_maps_to_cli_and_keeps_request_id(self):
        ok, argv, schema, errors = build_cli_argv(
            "wps_agent_writer_fill_bookmark",
            {"document_id": "doc_1", "bookmark_name": "Client", "text": "Northwind", "dry_run": True, "request_id": "bookmark-1"},
        )
        self.assertTrue(ok)
        self.assertEqual(errors, [])
        self.assertEqual(schema["cli_command"], "writer-fill-bookmark")
        self.assertEqual(argv, [
            "writer-fill-bookmark", "--document-id", "doc_1", "--bookmark-name", "Client",
            "--text", "Northwind", "--dry-run", "--request-id", "bookmark-1",
        ])

    def test_build_cli_argv_maps_json_arguments_to_cli_flags(self):
        ok, argv, schema, errors = build_cli_argv(
            "wps_agent_tasks",
            {"phase": "phase2", "status": "next", "request_id": "req-1"},
        )

        self.assertTrue(ok)
        self.assertEqual(errors, [])
        self.assertEqual(schema["cli_command"], "tasks")
        self.assertEqual(argv, ["tasks", "--phase", "phase2", "--status", "next", "--request-id", "req-1"])

    def test_call_mcp_tool_uses_cli_response_layer(self):
        ok, result, errors = call_mcp_tool(
            "wps_agent_tasks",
            {"phase": "phase2", "request_id": "mcp-adapter-test-001"},
        )

        self.assertTrue(ok)
        self.assertEqual(errors, [])
        self.assertEqual(result["cli_command"], "tasks")
        self.assertEqual(result["response"]["command"], "tasks")
        self.assertEqual(result["response"]["data"]["filters"]["phase"], "phase2")

    def test_call_mcp_tool_rejects_missing_required_arguments(self):
        ok, result, errors = call_mcp_tool("wps_agent_spreadsheet_write", {"range": "A1:B2"})

        self.assertFalse(ok)
        self.assertIsNone(result["response"])
        self.assertEqual(errors[0]["code"], "MCP_ARGUMENTS_MISSING_REQUIRED")
        self.assertIn("document_id", errors[0]["details"])

    def test_call_mcp_tool_rejects_recursive_mcp_call(self):
        ok, result, errors = call_mcp_tool("wps_agent_mcp_call", {"name": "wps_agent_tasks"})

        self.assertFalse(ok)
        self.assertIsNone(result["response"])
        self.assertEqual(errors[0]["code"], "MCP_ADAPTER_CALL_REJECTED")


if __name__ == "__main__":
    unittest.main()
