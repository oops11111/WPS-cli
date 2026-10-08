import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
import unittest
from unittest.mock import Mock, patch

from wps_ai_agent_cli.cli import (
    _configure_stdout,
    _extract_request_id,
    _with_optional_task_status,
    build_parser,
    regression_run_response,
    local_release_gates_response,
    run,
)
from wps_ai_agent_cli.models import CommandResponse, ValidationResult


class CliParsingTests(unittest.TestCase):
    def test_local_release_gates_run_in_order(self):
        def passed(command, data=None):
            return CommandResponse(True, command, "step", "local-python", "passed", data or {}, ValidationResult("passed"))

        with patch("wps_ai_agent_cli.cli.cloud_sync_package_response", side_effect=[passed("cloud-sync-package"), passed("cloud-sync-package")]) as package, \
             patch("wps_ai_agent_cli.cli.regression_run_response", side_effect=[passed("regression-run", {"artifact": {"path": "safe.json"}}), passed("regression-run", {"artifact": {"path": "release.json"}})]) as regression, \
             patch("wps_ai_agent_cli.cli.sync_package_readiness_response", return_value=passed("sync-package-readiness")) as readiness:
            response = local_release_gates_response("run")
        self.assertTrue(response.ok)
        self.assertEqual([item["name"] for item in response.data["local_release_gates"]["steps"]],
                         ["initial_package", "safe_baseline", "refreshed_package", "package_readiness", "release_gates"])
        self.assertEqual(package.call_count, 2)
        self.assertEqual(regression.call_count, 2)
        readiness.assert_called_once()
        self.assertEqual(regression.call_args_list[0].args[2:4], ("safe", False))
        self.assertEqual(regression.call_args_list[1].args[2:4], ("release", False))

    def test_local_release_gates_stop_and_retain_failed_safe_artifact(self):
        package_response = CommandResponse(True, "cloud-sync-package", "step", "local-python", "passed", {}, ValidationResult("passed"))
        failed_safe = CommandResponse(False, "regression-run", "step", "local-python", "failed",
                                      {"artifact": {"path": "failed-safe.json"}}, ValidationResult("failed"),
                                      [{"code": "REGRESSION_RUN_FAILED", "message": "failed"}])
        with patch("wps_ai_agent_cli.cli.cloud_sync_package_response", return_value=package_response) as package, \
             patch("wps_ai_agent_cli.cli.regression_run_response", return_value=failed_safe) as regression, \
             patch("wps_ai_agent_cli.cli.sync_package_readiness_response") as readiness:
            response = local_release_gates_response("run")
        self.assertFalse(response.ok)
        self.assertEqual(response.data["local_release_gates"]["completed_count"], 2)
        self.assertEqual(response.data["local_release_gates"]["steps"][1]["artifact"]["path"], "failed-safe.json")
        package.assert_called_once()
        regression.assert_called_once()
        readiness.assert_not_called()

    def test_local_release_gates_reject_wps_profile_before_writing(self):
        manifest = {"scenarios": [{"id": "unsafe", "profile": "safe", "requires_wps": True}] + [
            {"id": name, "profile": "release", "requires_wps": False}
            for name in ("local-handoff-summary", "regression-evidence", "regression-history")]}
        with patch("wps_ai_agent_cli.cli.load_regression_manifest", return_value=(True, manifest, [])), \
             patch("wps_ai_agent_cli.cli.cloud_sync_package_response") as package:
            response = local_release_gates_response("run")
        self.assertFalse(response.ok)
        self.assertEqual(response.errors[0]["code"], "LOCAL_RELEASE_PROFILE_INVALID")
        package.assert_not_called()

    def test_failed_or_cancelled_task_does_not_restart_operation(self):
        from wps_ai_agent_cli.task_status import create_task_status, update_task_status

        for state in ("failed", "cancelled"):
            with self.subTest(state=state), TemporaryDirectory() as tmp:
                with patch("wps_ai_agent_cli.task_status.task_status_state_path", return_value=Path(tmp) / "status.json"):
                    create_task_status("html-batch-convert", "original", task_id="owned")
                    update_task_status("owned", state)
                    factory = Mock()
                    result = _with_optional_task_status(factory, "owned", "html-batch-convert", "original")
                    factory.assert_not_called()
                    self.assertFalse(result.ok)
                    self.assertEqual(result.errors[0]["code"], "TASK_ALREADY_TERMINAL")

    def test_cancellation_before_running_transition_prevents_execution(self):
        from wps_ai_agent_cli.task_status import update_task_status

        with TemporaryDirectory() as tmp:
            def cancel_before_start(task_id, state_value, **kwargs):
                self.assertTrue(update_task_status(task_id, "cancelled")[0])
                return update_task_status(task_id, state_value, **kwargs)

            with patch("wps_ai_agent_cli.task_status.task_status_state_path", return_value=Path(tmp) / "status.json"), \
                 patch("wps_ai_agent_cli.cli.update_task_status", side_effect=cancel_before_start):
                factory = Mock()
                result = _with_optional_task_status(factory, "owned", "html-batch-convert", "original")
                factory.assert_not_called()
                self.assertFalse(result.ok)
                self.assertEqual(result.data["task_status"]["state"], "cancelled")

    def test_task_owner_conflict_stops_operation_before_execution(self):
        from wps_ai_agent_cli.task_status import create_task_status, update_task_status

        for terminal in (False, True):
            with self.subTest(terminal=terminal), TemporaryDirectory() as tmp:
                path = Path(tmp) / "statuses.json"
                with patch("wps_ai_agent_cli.task_status.task_status_state_path", return_value=path):
                    create_task_status("html-batch-convert", "original", task_id="owned")
                    if terminal:
                        update_task_status("owned", "succeeded")
                    before = path.read_bytes()
                    factory = Mock()
                    result = _with_optional_task_status(factory, "owned", "html-batch-convert", "different")
                    self.assertFalse(result.ok)
                    self.assertEqual(result.errors[0]["code"], "TASK_ID_CONFLICT")
                    factory.assert_not_called()
                    self.assertEqual(path.read_bytes(), before)

    def test_same_operation_task_replay_reaches_existing_operation_handler(self):
        from wps_ai_agent_cli.task_status import create_task_status, update_task_status

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "statuses.json"
            with patch("wps_ai_agent_cli.task_status.task_status_state_path", return_value=path):
                create_task_status("backup-document", "original", task_id="owned")
                update_task_status("owned", "succeeded")
                before = path.read_bytes()
                response = CommandResponse(ok=True, command="backup-document", request_id="original",
                                           backend="local-python", summary="Replayed operation")
                factory = Mock(return_value=response)
                result = _with_optional_task_status(factory, "owned", "backup-document", "original")
                factory.assert_called_once_with()
                self.assertTrue(result.ok)
                self.assertEqual(path.read_bytes(), before)
                self.assertEqual(result.data["task_status"]["state"], "succeeded")

    def test_html_render_parser_defaults_to_script_disabled(self):
        args = build_parser().parse_args(["html-render", "--input", "a.html", "--output", "a.pdf", "--format", "pdf"])
        self.assertFalse(args.allow_javascript)
        self.assertEqual(args.page_size, "A4")
        self.assertEqual(args.viewport_width, 1280)

    def test_html_editable_parser_accepts_task_tracking(self):
        args = build_parser().parse_args(["html-editable", "--input", "a.html", "--output", "a.docx", "--task-id", "html_1"])
        self.assertEqual(args.task_id, "html_1")

    def test_html_roundtrip_plan_parser(self):
        args = build_parser().parse_args(["html-roundtrip-plan", "--input", "owned.html"])
        self.assertEqual(args.command, "html-roundtrip-plan")
        self.assertEqual(args.input, "owned.html")

    def test_html_controlled_import_and_verify_parsers(self):
        parser = build_parser()
        imported = parser.parse_args(["html-controlled-import", "--input", "owned.html", "--output", "owned.docx", "--task-id", "roundtrip_1"])
        verified = parser.parse_args(["html-roundtrip-verify", "--docx", "owned.docx", "--mapping", "owned.docx.wpsmap.json"])
        self.assertEqual(imported.task_id, "roundtrip_1")
        self.assertEqual(verified.mapping, "owned.docx.wpsmap.json")

    def test_html_roundtrip_export_parser(self):
        args = build_parser().parse_args(["html-roundtrip-export", "--docx", "edited.docx", "--mapping", "edited.docx.wpsmap.json", "--output", "roundtrip.html", "--task-id", "export_1"])
        self.assertEqual(args.output, "roundtrip.html")
        self.assertEqual(args.task_id, "export_1")

    def test_html_batch_convert_parser(self):
        args = build_parser().parse_args(["html-batch-convert", "--input-dir", "in", "--output-dir", "out", "--mode", "pdf", "--recursive"])
        self.assertTrue(args.recursive)
        self.assertEqual(args.mode, "pdf")

    def test_batch_template_report_parser(self):
        args = build_parser().parse_args(["batch-template-report", "--manifest", "batch.json", "--template", "report.md", "--output", "result.md", "--task-id", "report_1"])
        self.assertEqual(args.task_id, "report_1")

    def test_html_batch_convert_cli_writes_per_file_manifest(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "input", root / "output"
            source.mkdir()
            (source / "brief.html").write_text("<h1>Brief</h1><p>Editable</p>", encoding="utf-8")
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = run(["html-batch-convert", "--input-dir", str(source), "--output-dir", str(output), "--mode", "docx"])
            response = json.loads(stdout.getvalue())
            self.assertEqual(code, 0)
            self.assertTrue(response["ok"])
            self.assertTrue((output / "brief.docx").is_file())
            self.assertTrue(Path(response["data"]["manifest_path"]).is_file())

    def test_batch_template_report_cli_creates_rendered_report(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "batch.json"
            template = root / "report.md"
            output = root / "result.md"
            manifest.write_text(json.dumps({
                "schema_version": "wps-agent-batch-conversion/v1", "mode": "docx",
                "source_directory": "in", "output_directory": "out",
                "summary": {"total": 0, "passed": 0, "failed": 0}, "files": [],
            }), encoding="utf-8")
            template.write_text("Batch {{mode}}: {{total}} {{files_table}}", encoding="utf-8")
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = run(["batch-template-report", "--manifest", str(manifest), "--template", str(template), "--output", str(output)])
            response = json.loads(stdout.getvalue())
            self.assertEqual(code, 0)
            self.assertTrue(response["ok"])
            self.assertIn("Batch docx: 0", output.read_text(encoding="utf-8"))

    def test_batch_convert_to_template_report_end_to_end(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, converted = root / "input", root / "converted"
            source.mkdir()
            (source / "brief.html").write_text("<h1>Brief</h1>", encoding="utf-8")
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = run(["html-batch-convert", "--input-dir", str(source), "--output-dir", str(converted), "--mode", "docx"])
            self.assertEqual(code, 0)
            manifest = json.loads(stdout.getvalue())["data"]["manifest_path"]
            template, report = root / "template.md", root / "report.md"
            template.write_text("# Batch {{mode}}\n{{files_table}}", encoding="utf-8")
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = run(["batch-template-report", "--manifest", manifest, "--template", str(template), "--output", str(report)])
            self.assertEqual(code, 0)
            self.assertIn("brief.html", report.read_text(encoding="utf-8"))
            self.assertIn("passed", report.read_text(encoding="utf-8"))

    def test_html_batch_task_progress_cancellation_keeps_manifest(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "input", root / "output"
            source.mkdir()
            (source / "a.html").write_text("A", encoding="utf-8")
            (source / "b.html").write_text("B", encoding="utf-8")
            reads = 0

            def status(task_id):
                nonlocal reads
                reads += 1
                return {"task_id": task_id, "state": "cancelled" if reads >= 3 else "running", "terminal": reads >= 3}

            def render(path, destination, output_format):
                destination.write_bytes(b"PDF")
                return True, {}, []

            stdout = io.StringIO()
            with patch("wps_ai_agent_cli.cli.create_task_status", return_value=(True, {"terminal": False}, [], False)), \
                 patch("wps_ai_agent_cli.cli.update_task_status", return_value=(True, {}, [])), \
                 patch("wps_ai_agent_cli.cli.get_task_status", side_effect=status), \
                 patch("wps_ai_agent_cli.batch_conversion.render_html", side_effect=render), \
                 redirect_stdout(stdout):
                code = run(["html-batch-convert", "--input-dir", str(source), "--output-dir", str(output), "--mode", "pdf", "--task-id", "batch_cancel"])
            response = json.loads(stdout.getvalue())
            self.assertEqual(code, 0)
            self.assertFalse(response["ok"])
            self.assertTrue(response["data"]["cancelled"])
            self.assertEqual(response["data"]["summary"]["processed"], 1)
            self.assertEqual(response["data"]["task_status"]["state"], "cancelled")
            self.assertTrue(Path(response["data"]["manifest_path"]).is_file())

    def test_live_task_status_cancellation_is_polled_between_batch_files(self):
        from wps_ai_agent_cli.task_status import get_task_status, update_task_status

        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "input", root / "output"
            source.mkdir()
            for name in ("a", "b"):
                (source / f"{name}.html").write_text(name, encoding="utf-8")
            started, release = Event(), Event()
            stdout = io.StringIO()
            outcome = {}

            def render(path, destination, output_format):
                destination.write_bytes(b"PDF")
                started.set()
                self.assertTrue(release.wait(5))
                return True, {}, []

            def worker():
                with patch("wps_ai_agent_cli.batch_conversion.render_html", side_effect=render), redirect_stdout(stdout):
                    outcome["exit_code"] = run(["html-batch-convert", "--input-dir", str(source), "--output-dir", str(output), "--mode", "pdf", "--task-id", "live_cancel"])

            with patch("wps_ai_agent_cli.task_status.task_status_state_path", side_effect=lambda workspace=".": root / "task-statuses.json"):
                thread = Thread(target=worker)
                thread.start()
                self.assertTrue(started.wait(5))
                cancelled, _, errors = update_task_status("live_cancel", "cancelled", message="cancel requested")
                self.assertTrue(cancelled, errors)
                release.set()
                thread.join(10)
                self.assertFalse(thread.is_alive())
                self.assertEqual(get_task_status("live_cancel")["state"], "cancelled")
            response = json.loads(stdout.getvalue())
            self.assertEqual(outcome["exit_code"], 0)
            self.assertFalse(response["ok"])
            self.assertTrue(response["data"]["cancelled"])
            self.assertEqual(response["data"]["summary"]["processed"], 1)
            self.assertTrue(Path(response["data"]["manifest_path"]).is_file())

    def test_html_roundtrip_export_cli_preserves_owned_ids(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, document, output_path = root / "owned.html", root / "owned.docx", root / "roundtrip.html"
            source.write_text('<html data-wps-schema="wps-agent-html/v1"><p data-wps-object-id="p1">Before</p></html>', encoding="utf-8")
            from wps_ai_agent_cli.html_roundtrip import import_controlled_html
            ok, imported, errors = import_controlled_html(source, document)
            self.assertTrue(ok, errors)
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = run(["html-roundtrip-export", "--docx", str(document), "--mapping", imported["mapping_path"], "--output", str(output_path)])
            response = json.loads(stdout.getvalue())
            self.assertEqual(code, 0)
            self.assertTrue(response["ok"])
            from wps_ai_agent_cli.html_roundtrip import build_html_roundtrip_mapping
            valid, mapping, errors = build_html_roundtrip_mapping(output_path)
            self.assertTrue(valid, errors)
            self.assertEqual(mapping["mappings"][0]["object_id"], "p1")

    def test_html_roundtrip_plan_cli_returns_identity_mapping(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "owned.html"
            source.write_text(
                '<html data-wps-schema="wps-agent-html/v1"><p data-wps-object-id="p1">Text</p></html>',
                encoding="utf-8",
            )
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = run(["html-roundtrip-plan", "--input", str(source)])
            response = json.loads(output.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertTrue(response["ok"])
            self.assertEqual(response["data"]["roundtrip_mapping"]["mappings"][0]["object_id"], "p1")

    def test_html_editable_cli_returns_object_counts_and_writes_docx(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "page.html"
            output_path = Path(directory) / "page.docx"
            source.write_text("<h1>Heading</h1><p>Editable</p>", encoding="utf-8")
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = run(["html-editable", "--input", str(source), "--output", str(output_path)])
            response = json.loads(stdout.getvalue())
            self.assertEqual(code, 0)
            self.assertTrue(response["ok"])
            self.assertEqual(response["data"]["mapped_objects"]["headings"], 1)
            self.assertTrue(output_path.is_file())

    def test_spreadsheet_inventory_cli_preserves_extended_read_only_metadata(self):
        inventory = {
            "document_id": "doc_1", "component": "spreadsheets", "read_only": True, "saved": False,
            "sheet_count": 1, "sheets": [{"name": "Data", "tab_color": "#123456", "formula_count": 2, "freeze_panes": "B2", "merged_ranges": ["A1:B1"]}],
            "defined_names": [], "defined_name_count": 0, "defined_names_truncated": False,
            "calculation": {"mode": "manual"},
        }
        output = io.StringIO()
        with patch("wps_ai_agent_cli.cli.list_spreadsheet_sheets", return_value=(True, inventory, [])):
            with redirect_stdout(output):
                exit_code = run(["spreadsheet-sheets", "--document-id", "doc_1"])
        self.assertEqual(exit_code, 0)
        response = json.loads(output.getvalue())
        self.assertTrue(response["ok"])
        self.assertEqual(response["data"]["sheets"][0]["tab_color"], "#123456")
        self.assertEqual(response["data"]["sheets"][0]["merged_ranges"], ["A1:B1"])
        self.assertEqual(response["data"]["calculation"]["mode"], "manual")
    def test_extract_request_id_after_subcommand(self):
        argv, request_id = _extract_request_id(
            ["backup-document", "--document-id", "doc_1", "--request-id", "req-1"]
        )

        self.assertEqual(request_id, "req-1")
        self.assertEqual(argv, ["backup-document", "--document-id", "doc_1"])

    def test_extract_request_id_equals_form(self):
        argv, request_id = _extract_request_id(["tasks", "--request-id=req-2"])

        self.assertEqual(request_id, "req-2")
        self.assertEqual(argv, ["tasks"])

    def test_configure_stdout_prefers_utf8(self):
        stream = io.TextIOWrapper(io.BytesIO(), encoding="gbk")
        with patch("sys.stdout", stream):
            _configure_stdout()
            self.assertEqual(stream.encoding.lower().replace("_", "-"), "utf-8")

    def test_mutating_command_parsers_accept_task_id(self):
        parser = build_parser()

        args = parser.parse_args([
            "backup-document",
            "--document-id",
            "doc_1",
            "--task-id",
            "task_1",
        ])

        self.assertEqual(args.command, "backup-document")
        self.assertEqual(args.task_id, "task_1")

    def test_task_recovery_parser_accepts_task_id(self):
        parser = build_parser()

        args = parser.parse_args(["task-recovery", "--task-id", "task_1"])

        self.assertEqual(args.command, "task-recovery")
        self.assertEqual(args.task_id, "task_1")

    def test_mcp_schema_parsers_accept_filters_and_names(self):
        parser = build_parser()

        list_args = parser.parse_args(["mcp-tools", "--category", "spreadsheet", "--mutates-document", "true"])
        catalog_args = parser.parse_args(["mcp-catalog-snapshot"])
        drift_args = parser.parse_args(["mcp-catalog-drift", "--guard", "config/mcp_catalog_guard.json"])
        schema_args = parser.parse_args(["mcp-tool-schema", "--name", "wps_agent_writer_replace"])
        bookmark_args = parser.parse_args(["writer-fill-bookmark", "--document-id", "doc_1", "--bookmark-name", "Client", "--text", "Northwind", "--dry-run"])
        inspect_args = parser.parse_args(["spreadsheet-inspect", "--document-id", "doc_1", "--sheet", "Sheet1", "--range", "A1:F1"])
        sheets_args = parser.parse_args(["spreadsheet-sheets", "--document-id", "doc_1"])
        rename_sheet_args = parser.parse_args(["spreadsheet-rename-sheet", "--document-id", "doc_1", "--old-name", "Sheet1", "--new-name", "Archive", "--dry-run"])
        create_sheet_args = parser.parse_args(["spreadsheet-create-sheet", "--document-id", "doc_1", "--name", "Archive", "--index", "2", "--dry-run"])
        visibility_args = parser.parse_args(["spreadsheet-set-sheet-visibility", "--document-id", "doc_1", "--sheet-name", "Archive", "--visible", "false", "--dry-run"])
        delete_sheet_args = parser.parse_args(["spreadsheet-delete-sheet", "--document-id", "doc_1", "--sheet-name", "Archive", "--dry-run"])
        copy_sheet_args = parser.parse_args(["spreadsheet-copy-sheet", "--document-id", "doc_1", "--source-name", "Sheet1", "--new-name", "Copy", "--index", "2", "--dry-run"])
        tab_color_args = parser.parse_args(["spreadsheet-set-sheet-tab-color", "--document-id", "doc_1", "--sheet-name", "Sheet1", "--color", "#12ABEF", "--dry-run"])
        call_args = parser.parse_args(["mcp-call", "--name", "wps_agent_tasks", "--arguments-json", "{\"phase\":\"phase2\"}"])
        server_args = parser.parse_args(["mcp-server", "--once-json", "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\"}"])
        smoke_args = parser.parse_args(["mcp-smoke", "--expected-min-tools", "10", "--tool-name", "wps_agent_tasks"])
        audit_args = parser.parse_args(["mcp-config-audit", "--config", "config/mcp_client_config.example.json"])
        manifest_args = parser.parse_args(["regression-manifest", "--profile", "safe"])
        run_args = parser.parse_args(["regression-run", "--profile", "safe"])
        run_artifact_args = parser.parse_args(["regression-run", "--profile", "safe", "--artifact-dir", "artifacts/regression"])
        evidence_args = parser.parse_args(["regression-evidence", "--workspace", "."])
        history_args = parser.parse_args(["regression-history", "--workspace", ".", "--limit", "3"])
        cloud_sync_args = parser.parse_args(["cloud-sync-package", "--output", "artifacts/cloud-sync/test.zip", "--no-latest-artifacts"])
        sync_package_inspect_args = parser.parse_args([
            "sync-package-inspect",
            "--workspace",
            ".",
            "--package",
            "artifacts/cloud-sync/test.zip",
        ])
        sync_package_summary_args = parser.parse_args([
            "sync-package-summary",
            "--workspace",
            ".",
            "--package",
            "artifacts/cloud-sync/test.zip",
            "--limit",
            "3",
        ])
        sync_package_manifest_args = parser.parse_args([
            "sync-package-manifest",
            "--workspace",
            ".",
            "--package",
            "artifacts/cloud-sync/test.zip",
            "--prefix",
            "docs",
            "--limit",
            "4",
        ])
        sync_package_coverage_args = parser.parse_args([
            "sync-package-coverage",
            "--workspace",
            ".",
            "--package",
            "artifacts/cloud-sync/test.zip",
            "--limit",
            "5",
        ])
        sync_package_readiness_args = parser.parse_args([
            "sync-package-readiness",
            "--workspace",
            ".",
            "--package",
            "artifacts/cloud-sync/test.zip",
            "--limit",
            "6",
        ])
        security_args = parser.parse_args(["security-audit"])
        performance_args = parser.parse_args(["performance-baseline"])
        process_audit_args = parser.parse_args(["wps-process-audit", "--timeout-seconds", "4"])
        cleanup_plan_args = parser.parse_args(["cleanup-plan", "--workspace", "."])
        cleanup_approval_args = parser.parse_args(["cleanup-approval-manifest", "--workspace", "."])
        artifact_retention_args = parser.parse_args(["artifact-retention-summary", "--workspace", "."])
        project_status_args = parser.parse_args(["project-status", "--workspace", "."])
        workspace_health_args = parser.parse_args(["workspace-health", "--workspace", "."])
        local_handoff_args = parser.parse_args(["local-handoff-summary", "--workspace", "."])
        validation_runbook_args = parser.parse_args(["validation-runbook", "--workspace", "."])
        documentation_freshness_args = parser.parse_args(["documentation-freshness", "--workspace", "."])
        writer_table_args = parser.parse_args([
            "writer-table-write",
            "--document-id",
            "doc_1",
            "--table-index",
            "1",
            "--row",
            "2",
            "--column",
            "3",
            "--text",
            "Approved",
        ])
        writer_table_smoke_args = parser.parse_args([
            "writer-table-smoke",
            "--input",
            "fixtures/phase3/writer_table_fixture.docx",
            "--output",
            "fixtures/phase3/writer_table_regression_smoke.docx",
            "--table-index",
            "1",
            "--row",
            "2",
            "--column",
            "3",
            "--text",
            "Regression",
        ])

        self.assertEqual(list_args.command, "mcp-tools")
        self.assertEqual(list_args.category, "spreadsheet")
        self.assertEqual(list_args.mutates_document, "true")
        self.assertEqual(catalog_args.command, "mcp-catalog-snapshot")
        self.assertEqual(drift_args.command, "mcp-catalog-drift")
        self.assertEqual(drift_args.guard, "config/mcp_catalog_guard.json")
        self.assertEqual(schema_args.command, "mcp-tool-schema")
        self.assertEqual(bookmark_args.command, "writer-fill-bookmark")
        self.assertEqual(bookmark_args.bookmark_name, "Client")
        self.assertEqual(inspect_args.command, "spreadsheet-inspect")
        self.assertEqual(inspect_args.range, "A1:F1")
        self.assertEqual(sheets_args.command, "spreadsheet-sheets")
        self.assertEqual(sheets_args.document_id, "doc_1")
        self.assertEqual(rename_sheet_args.command, "spreadsheet-rename-sheet")
        self.assertTrue(rename_sheet_args.dry_run)
        self.assertEqual(create_sheet_args.command, "spreadsheet-create-sheet")
        self.assertEqual(create_sheet_args.index, 2)
        self.assertTrue(create_sheet_args.dry_run)
        self.assertEqual(visibility_args.command, "spreadsheet-set-sheet-visibility")
        self.assertEqual(visibility_args.visible, "false")
        self.assertEqual(delete_sheet_args.command, "spreadsheet-delete-sheet")
        self.assertEqual(copy_sheet_args.command, "spreadsheet-copy-sheet")
        self.assertEqual(copy_sheet_args.index, 2)
        self.assertEqual(tab_color_args.command, "spreadsheet-set-sheet-tab-color")
        self.assertEqual(tab_color_args.color, "#12ABEF")
        self.assertEqual(schema_args.name, "wps_agent_writer_replace")
        self.assertEqual(call_args.command, "mcp-call")
        self.assertEqual(call_args.name, "wps_agent_tasks")
        self.assertEqual(server_args.command, "mcp-server")
        self.assertIn("tools/list", server_args.once_json)
        calc_args = parser.parse_args(["calc-smoke", "--input", "in.xlsx", "--output", "out.xlsx", "--timeout-seconds", "3"])

        self.assertEqual(smoke_args.command, "mcp-smoke")
        self.assertEqual(smoke_args.expected_min_tools, 10)
        self.assertEqual(smoke_args.tool_name, "wps_agent_tasks")
        self.assertEqual(calc_args.command, "calc-smoke")
        self.assertEqual(calc_args.timeout_seconds, 3)
        self.assertEqual(audit_args.command, "mcp-config-audit")
        self.assertEqual(audit_args.config, "config/mcp_client_config.example.json")
        self.assertEqual(manifest_args.command, "regression-manifest")
        self.assertEqual(manifest_args.profile, "safe")
        self.assertEqual(run_args.command, "regression-run")
        self.assertEqual(run_args.profile, "safe")
        self.assertEqual(run_artifact_args.artifact_dir, "artifacts/regression")
        self.assertEqual(evidence_args.command, "regression-evidence")
        self.assertEqual(evidence_args.workspace, ".")
        self.assertEqual(history_args.command, "regression-history")
        self.assertEqual(history_args.limit, 3)
        self.assertEqual(cloud_sync_args.command, "cloud-sync-package")
        self.assertEqual(cloud_sync_args.output, "artifacts/cloud-sync/test.zip")
        self.assertTrue(cloud_sync_args.no_latest_artifacts)
        self.assertEqual(sync_package_inspect_args.command, "sync-package-inspect")
        self.assertEqual(sync_package_inspect_args.workspace, ".")
        self.assertEqual(sync_package_inspect_args.package, "artifacts/cloud-sync/test.zip")
        self.assertEqual(sync_package_summary_args.command, "sync-package-summary")
        self.assertEqual(sync_package_summary_args.workspace, ".")
        self.assertEqual(sync_package_summary_args.package, "artifacts/cloud-sync/test.zip")
        self.assertEqual(sync_package_summary_args.limit, 3)
        self.assertEqual(sync_package_manifest_args.command, "sync-package-manifest")
        self.assertEqual(sync_package_manifest_args.workspace, ".")
        self.assertEqual(sync_package_manifest_args.package, "artifacts/cloud-sync/test.zip")
        self.assertEqual(sync_package_manifest_args.prefix, "docs")
        self.assertEqual(sync_package_manifest_args.limit, 4)
        self.assertEqual(sync_package_coverage_args.command, "sync-package-coverage")
        self.assertEqual(sync_package_coverage_args.workspace, ".")
        self.assertEqual(sync_package_coverage_args.package, "artifacts/cloud-sync/test.zip")
        self.assertEqual(sync_package_coverage_args.limit, 5)
        self.assertEqual(sync_package_readiness_args.command, "sync-package-readiness")
        self.assertEqual(sync_package_readiness_args.workspace, ".")
        self.assertEqual(sync_package_readiness_args.package, "artifacts/cloud-sync/test.zip")
        self.assertEqual(sync_package_readiness_args.limit, 6)
        self.assertEqual(security_args.command, "security-audit")
        self.assertEqual(performance_args.command, "performance-baseline")
        self.assertEqual(process_audit_args.command, "wps-process-audit")
        self.assertEqual(process_audit_args.timeout_seconds, 4)
        self.assertEqual(cleanup_plan_args.command, "cleanup-plan")
        self.assertEqual(cleanup_plan_args.workspace, ".")
        self.assertEqual(cleanup_approval_args.command, "cleanup-approval-manifest")
        self.assertEqual(cleanup_approval_args.workspace, ".")
        self.assertEqual(artifact_retention_args.command, "artifact-retention-summary")
        self.assertEqual(artifact_retention_args.workspace, ".")
        self.assertEqual(project_status_args.command, "project-status")
        self.assertEqual(project_status_args.workspace, ".")
        self.assertEqual(workspace_health_args.command, "workspace-health")
        self.assertEqual(workspace_health_args.workspace, ".")
        self.assertEqual(local_handoff_args.command, "local-handoff-summary")
        self.assertEqual(local_handoff_args.workspace, ".")
        self.assertEqual(validation_runbook_args.command, "validation-runbook")
        self.assertEqual(validation_runbook_args.workspace, ".")
        self.assertEqual(documentation_freshness_args.command, "documentation-freshness")
        self.assertEqual(documentation_freshness_args.workspace, ".")
        self.assertEqual(writer_table_args.command, "writer-table-write")
        self.assertEqual(writer_table_args.table_index, 1)
        self.assertEqual(writer_table_smoke_args.command, "writer-table-smoke")
        self.assertEqual(writer_table_smoke_args.text, "Regression")

    def test_regression_run_response_writes_artifact(self):
        with TemporaryDirectory() as tmpdir:
            response = regression_run_response(
                "req_artifact_1",
                manifest_path=str(Path(__file__).parent / "fixtures" / "regression_contract.json"),
                profile="safe",
                include_wps=False,
                artifact_dir=tmpdir,
            )

            artifact = response.data["artifact"]
            artifact_path = Path(artifact["path"])
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))

        self.assertTrue(response.ok)
        self.assertTrue(artifact["created"])
        self.assertEqual(artifact_path.name, artifact["filename"])
        self.assertEqual(payload["request_id"], "req_artifact_1")
        self.assertEqual(payload["data"]["regression"]["failed_count"], 0)

    def test_failed_regression_gate_is_preserved_in_artifact(self):
        fixture = Path(__file__).parent / "fixtures" / "regression_contract.json"
        manifest = json.loads(fixture.read_text(encoding="utf-8"))
        manifest["scenarios"][0]["required_checks"][0]["equals"] = "wrong-command"
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            response = regression_run_response("failed-gate", str(path), "safe", False, tmpdir)
            payload = json.loads(Path(response.data["artifact"]["path"]).read_text(encoding="utf-8"))
        self.assertFalse(response.ok)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["data"]["regression"]["failed_count"], 1)
        self.assertEqual(payload["errors"][0]["code"], "REGRESSION_RUN_FAILED")

    def test_optional_task_status_marks_success_and_attaches_status(self):
        statuses = {
            "task_1": {
                "task_id": "task_1",
                "state": "pending",
                "terminal": False,
                "progress_percent": 0,
            }
        }

        def fake_create_task_status(**_kwargs):
            return True, dict(statuses["task_1"]), [], False

        def fake_update_task_status(task_id, state_value, **kwargs):
            statuses[task_id]["state"] = state_value
            statuses[task_id]["terminal"] = state_value in {"succeeded", "failed", "cancelled"}
            if kwargs.get("result_ref"):
                statuses[task_id]["result_ref"] = kwargs["result_ref"]
            return True, dict(statuses[task_id]), []

        def fake_get_task_status(task_id):
            return dict(statuses[task_id])

        response = CommandResponse(
            ok=True,
            command="backup-document",
            request_id="req_1",
            backend="local-python",
            summary="ok",
            validation=ValidationResult(status="passed"),
        )

        with (
            patch("wps_ai_agent_cli.cli.create_task_status", side_effect=fake_create_task_status),
            patch("wps_ai_agent_cli.cli.update_task_status", side_effect=fake_update_task_status),
            patch("wps_ai_agent_cli.cli.get_task_status", side_effect=fake_get_task_status),
        ):
            result = _with_optional_task_status(
                lambda: response,
                task_id="task_1",
                tracked_command="backup-document",
                operation_request_id="req_1",
                document_id="doc_1",
            )

        self.assertEqual(result.data["task_status"]["state"], "succeeded")
        self.assertTrue(result.data["task_status"]["terminal"])
        self.assertEqual(result.data["task_status"]["result_ref"], "req_1")


if __name__ == "__main__":
    unittest.main()
