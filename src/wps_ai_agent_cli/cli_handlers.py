from __future__ import annotations

import argparse
import sys
from typing import Any, Callable, TextIO

from .models import CommandResponse


def build_command_handlers(cli: Any) -> dict[str, Callable[[argparse.Namespace, str, TextIO | None], CommandResponse | int]]:
    def _handle_inspect_env(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.inspect_env_response(request_id)
        return response

    def _handle_wps_process_audit(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.wps_process_audit_response(request_id, timeout_seconds=args.timeout_seconds)
        return response

    def _handle_cleanup_plan(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.cleanup_plan_response(request_id, workspace=args.workspace)
        return response

    def _handle_cleanup_approval_manifest(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.cleanup_approval_manifest_response(request_id, workspace=args.workspace)
        return response

    def _handle_plan(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.plan_response(request_id)
        return response

    def _handle_tasks(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.tasks_response(request_id, phase=args.phase, status=args.status)
        return response

    def _handle_com_smoke(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.com_smoke_response(request_id, component=args.component, input_path=args.input, output_path=args.output, visible=args.visible)
        return response

    def _handle_calc_smoke(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.calc_smoke_response(request_id, input_path=args.input, output_path=args.output, timeout_seconds=args.timeout_seconds)
        return response

    def _handle_convert_smoke(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.convert_smoke_response(request_id, component=args.component, input_path=args.input, output_path=args.output, output_format=args.format)
        return response

    def _handle_html_render(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli._with_optional_task_status(lambda: cli.html_render_response(request_id, args.input, args.output, args.format, args.page_size, args.viewport_width, args.viewport_height, args.timeout_seconds, args.allow_javascript), task_id=args.task_id, tracked_command='html-render', operation_request_id=request_id)
        return response

    def _handle_html_batch_convert(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        progress_callback = None
        if args.task_id:

            def progress_callback(completed: int, total: int, message: str) -> bool:
                current = cli.get_task_status(args.task_id)
                if current and current.get('state') == 'cancelled':
                    return False
                percent = min(95, 10 + int(85 * completed / max(1, total)))
                cli.update_task_status(args.task_id, 'running', progress_percent=percent, message=message)
                current = cli.get_task_status(args.task_id)
                return not current or current.get('state') != 'cancelled'
        response = cli._with_optional_task_status(lambda: cli.html_batch_convert_response(request_id, args.input_dir, args.output_dir, args.mode, args.recursive, progress_callback), task_id=args.task_id, tracked_command='html-batch-convert', operation_request_id=request_id)
        return response

    def _handle_html_batch_request(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.html_batch_request_response(request_id, args.batch_request_id, args.verify)
        return response

    def _handle_batch_template_report(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli._with_optional_task_status(lambda: cli.batch_template_report_response(request_id, args.manifest, args.template, args.output), task_id=args.task_id, tracked_command='batch-template-report', operation_request_id=request_id)
        return response

    def _handle_html_editable(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli._with_optional_task_status(lambda: cli.html_editable_response(request_id, args.input, args.output), task_id=args.task_id, tracked_command='html-editable', operation_request_id=request_id)
        return response

    def _handle_html_roundtrip_plan(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.html_roundtrip_plan_response(request_id, args.input)
        return response

    def _handle_html_controlled_import(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli._with_optional_task_status(lambda: cli.html_controlled_import_response(request_id, args.input, args.output), task_id=args.task_id, tracked_command='html-controlled-import', operation_request_id=request_id)
        return response

    def _handle_html_roundtrip_verify(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.html_roundtrip_verify_response(request_id, args.docx, args.mapping)
        return response

    def _handle_html_roundtrip_export(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli._with_optional_task_status(lambda: cli.html_roundtrip_export_response(request_id, args.docx, args.mapping, args.output), task_id=args.task_id, tracked_command='html-roundtrip-export', operation_request_id=request_id)
        return response

    def _handle_writer_table_smoke(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli._with_optional_task_status(lambda: cli.writer_table_smoke_response(request_id, input_path=args.input, output_path=args.output, table_index=args.table_index, row=args.row, column=args.column, text=args.text), task_id=args.task_id, tracked_command='writer-table-smoke', operation_request_id=request_id)
        return response

    def _handle_register_document(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.register_document_response(request_id, component=args.component, path=args.path)
        return response

    def _handle_documents(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.documents_response(request_id)
        return response

    def _handle_backup_document(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli._with_optional_task_status(lambda: cli.backup_document_response(request_id, document_id=args.document_id, dry_run=args.dry_run), task_id=args.task_id, tracked_command='backup-document', operation_request_id=request_id, document_id=args.document_id)
        return response

    def _handle_list_backups(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.list_backups_response(request_id, document_id=args.document_id)
        return response

    def _handle_restore_backup(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli._with_optional_task_status(lambda: cli.restore_backup_response(request_id, document_id=args.document_id, backup_name=args.backup_name, backup_path=args.backup_path, dry_run=args.dry_run), task_id=args.task_id, tracked_command='restore-backup', operation_request_id=request_id, document_id=args.document_id)
        return response

    def _handle_writer_replace(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli._with_optional_task_status(lambda: cli.writer_replace_response(request_id, document_id=args.document_id, find_text=args.find, replace_text=args.replace, dry_run=args.dry_run, paragraph_index=args.paragraph_index), task_id=args.task_id, tracked_command='writer-replace', operation_request_id=request_id, document_id=args.document_id)
        return response

    def _handle_writer_fill_bookmark(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli._with_optional_task_status(lambda: cli.writer_fill_bookmark_response(request_id, document_id=args.document_id, bookmark_name=args.bookmark_name, text=args.text, dry_run=args.dry_run), task_id=args.task_id, tracked_command='writer-fill-bookmark', operation_request_id=request_id, document_id=args.document_id)
        return response

    def _handle_writer_table_write(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli._with_optional_task_status(lambda: cli.writer_table_write_response(request_id, document_id=args.document_id, table_index=args.table_index, row=args.row, column=args.column, text=args.text, dry_run=args.dry_run, allow_rich_content=args.allow_rich_content), task_id=args.task_id, tracked_command='writer-table-write', operation_request_id=request_id, document_id=args.document_id)
        return response

    def _handle_open_documents(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.open_documents_response(request_id, component=args.component, register=args.register)
        return response

    def _handle_writer_selection_read(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.writer_selection_read_response(request_id, document_id=args.document_id)
        return response

    def _handle_writer_selection_replace(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli._with_optional_task_status(lambda: cli.writer_selection_replace_response(request_id, document_id=args.document_id, text=args.text, expected_selection_text=args.expected_selection_text, dry_run=args.dry_run), task_id=args.task_id, tracked_command='writer-selection-replace', operation_request_id=request_id, document_id=args.document_id)
        return response

    def _handle_export_open_document(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.export_open_document_response(request_id, document_id=args.document_id, output=args.output)
        return response

    def _handle_validate_document(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.validate_document_response(request_id, document_id=args.document_id, contains=args.contains, cell=args.cell, equals=args.equals)
        return response

    def _handle_snapshot_document(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.snapshot_document_response(request_id, document_id=args.document_id)
        return response

    def _handle_writer_structure(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.writer_structure_response(request_id, args.document_id, args.limit, args.section, args.offset, args.bookmark_name, args.expected_sha256, args.include_text, args.text_limit)
        return response

    def _handle_writer_structure_parity(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.writer_structure_parity_response(request_id, args.run_wps, args.timeout_seconds, args.artifact_dir, args.scope)
        return response

    def _handle_operation(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.operation_response(request_id, operation_request_id=args.request)
        return response

    def _handle_operations(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.operations_response(request_id)
        return response

    def _handle_mutation_request_inspect(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.mutation_request_inspect_response(request_id, args.request)
        return response

    def _handle_task_status_create(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.task_status_create_response(request_id, task_id=args.task_id, command=args.tracked_command, operation_request_id=args.operation_request_id, document_id=args.document_id, message=args.message, recovery_guidance=args.recovery_guidance)
        return response

    def _handle_task_status_update(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.task_status_update_response(request_id, task_id=args.task_id, state=args.state, progress_percent=args.progress_percent, message=args.message, recovery_guidance=args.recovery_guidance, result_ref=args.result_ref)
        return response

    def _handle_task_status(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.task_status_response(request_id, task_id=args.task_id)
        return response

    def _handle_task_statuses(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.task_statuses_response(request_id)
        return response

    def _handle_task_recovery(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.task_recovery_response(request_id, task_id=args.task_id)
        return response

    def _handle_task_recovery_playbooks(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.task_recovery_playbooks_response(request_id)
        return response

    def _handle_mcp_tools(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.mcp_tools_response(request_id, category=args.category, mutates_document=args.mutates_document)
        return response

    def _handle_mcp_catalog_snapshot(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.mcp_catalog_snapshot_response(request_id)
        return response

    def _handle_mcp_catalog_drift(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.mcp_catalog_drift_response(request_id, guard_path=args.guard)
        return response

    def _handle_mcp_tool_schema(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.mcp_tool_schema_response(request_id, name=args.name)
        return response

    def _handle_mcp_call(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.mcp_call_response(request_id, name=args.name, arguments_json=args.arguments_json)
        return response

    def _handle_mcp_server(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse | int:
        if args.once_json:
            rpc_response = cli.handle_mcp_json(args.once_json)
            if rpc_response is not None:
                print(cli.dumps_json(rpc_response), file=output_stream or sys.stdout)
            return 0
        return cli.serve_stdio()

    def _handle_mcp_smoke(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.mcp_smoke_response(request_id, expected_min_tools=args.expected_min_tools, tool_name=args.tool_name, arguments_json=args.arguments_json)
        return response

    def _handle_mcp_config_audit(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.mcp_config_audit_response(request_id, config_path=args.config, server_name=args.server_name, expected_min_tools=args.expected_min_tools, timeout_seconds=args.timeout_seconds)
        return response

    def _handle_regression_manifest(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.regression_manifest_response(request_id, manifest_path=args.manifest, profile=args.profile, include_wps=args.include_wps)
        return response

    def _handle_regression_run(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.regression_run_response(request_id, manifest_path=args.manifest, profile=args.profile, include_wps=args.include_wps, artifact_dir=args.artifact_dir)
        return response

    def _handle_security_audit(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.security_audit_response(request_id)
        return response

    def _handle_performance_baseline(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.performance_baseline_response(request_id)
        return response

    def _handle_scan_dir(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.scan_dir_response(request_id, path=args.path, recursive=args.recursive)
        return response

    def _handle_batch_report(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.batch_report_response(request_id, path=args.path, recursive=args.recursive, include_snapshots=not args.no_snapshots)
        return response

    def _handle_spreadsheet_read(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.spreadsheet_read_response(request_id, document_id=args.document_id, range_address=args.range, sheet_name=args.sheet)
        return response

    def _handle_spreadsheet_sheets(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.spreadsheet_sheets_response(request_id, document_id=args.document_id)
        return response

    def _handle_spreadsheet_rename_sheet(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli._with_optional_task_status(lambda: cli.spreadsheet_rename_sheet_response(request_id, document_id=args.document_id, old_name=args.old_name, new_name=args.new_name, dry_run=args.dry_run), task_id=args.task_id, tracked_command='spreadsheet-rename-sheet')
        return response

    def _handle_spreadsheet_create_sheet(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli._with_optional_task_status(lambda: cli.spreadsheet_create_sheet_response(request_id, args.document_id, args.name, args.index, args.dry_run), task_id=args.task_id, tracked_command='spreadsheet-create-sheet')
        return response

    def _handle_spreadsheet_set_sheet_visibility(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli._with_optional_task_status(lambda: cli.spreadsheet_set_sheet_visibility_response(request_id, args.document_id, args.sheet_name, args.visible == 'true', args.dry_run), task_id=args.task_id, tracked_command='spreadsheet-set-sheet-visibility')
        return response

    def _handle_spreadsheet_delete_sheet(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli._with_optional_task_status(lambda: cli.spreadsheet_delete_sheet_response(request_id, args.document_id, args.sheet_name, args.dry_run), task_id=args.task_id, tracked_command='spreadsheet-delete-sheet')
        return response

    def _handle_spreadsheet_copy_sheet(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli._with_optional_task_status(lambda: cli.spreadsheet_copy_sheet_response(request_id, args.document_id, args.source_name, args.new_name, args.index, args.dry_run), task_id=args.task_id, tracked_command='spreadsheet-copy-sheet')
        return response

    def _handle_spreadsheet_set_sheet_tab_color(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli._with_optional_task_status(lambda: cli.spreadsheet_set_sheet_tab_color_response(request_id, args.document_id, args.sheet_name, args.color, args.dry_run), task_id=args.task_id, tracked_command='spreadsheet-set-sheet-tab-color')
        return response

    def _handle_spreadsheet_inspect(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli.spreadsheet_inspect_response(request_id, document_id=args.document_id, range_address=args.range, sheet_name=args.sheet)
        return response

    def _handle_spreadsheet_write(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli._with_optional_task_status(lambda: cli.spreadsheet_write_response(request_id, document_id=args.document_id, range_address=args.range, values_json=args.values_json, sheet_name=args.sheet, dry_run=args.dry_run), task_id=args.task_id, tracked_command='spreadsheet-write', operation_request_id=request_id, document_id=args.document_id)
        return response

    def _handle_spreadsheet_formula_write(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli._with_optional_task_status(lambda: cli.spreadsheet_formula_write_response(request_id, document_id=args.document_id, range_address=args.range, formulas_json=args.formulas_json, expected_values_json=args.expected_values_json, sheet_name=args.sheet, dry_run=args.dry_run), task_id=args.task_id, tracked_command='spreadsheet-formula-write', operation_request_id=request_id, document_id=args.document_id)
        return response

    def _handle_presentation_replace(args: argparse.Namespace, request_id: str, output_stream: TextIO | None) -> CommandResponse:
        response = cli._with_optional_task_status(lambda: cli.presentation_replace_response(request_id, document_id=args.document_id, find_text=args.find, replace_text=args.replace, dry_run=args.dry_run, slide_index=args.slide_index), task_id=args.task_id, tracked_command='presentation-replace', operation_request_id=request_id, document_id=args.document_id)
        return response

    return {
        'inspect-env': _handle_inspect_env,
        'wps-process-audit': _handle_wps_process_audit,
        'cleanup-plan': _handle_cleanup_plan,
        'cleanup-approval-manifest': _handle_cleanup_approval_manifest,
        'plan': _handle_plan,
        'tasks': _handle_tasks,
        'com-smoke': _handle_com_smoke,
        'calc-smoke': _handle_calc_smoke,
        'convert-smoke': _handle_convert_smoke,
        'html-render': _handle_html_render,
        'html-batch-convert': _handle_html_batch_convert,
        'html-batch-request': _handle_html_batch_request,
        'batch-template-report': _handle_batch_template_report,
        'html-editable': _handle_html_editable,
        'html-roundtrip-plan': _handle_html_roundtrip_plan,
        'html-controlled-import': _handle_html_controlled_import,
        'html-roundtrip-verify': _handle_html_roundtrip_verify,
        'html-roundtrip-export': _handle_html_roundtrip_export,
        'writer-table-smoke': _handle_writer_table_smoke,
        'register-document': _handle_register_document,
        'documents': _handle_documents,
        'backup-document': _handle_backup_document,
        'list-backups': _handle_list_backups,
        'restore-backup': _handle_restore_backup,
        'writer-replace': _handle_writer_replace,
        'writer-fill-bookmark': _handle_writer_fill_bookmark,
        'writer-table-write': _handle_writer_table_write,
        'open-documents': _handle_open_documents,
        'writer-selection-read': _handle_writer_selection_read,
        'writer-selection-replace': _handle_writer_selection_replace,
        'export-open-document': _handle_export_open_document,
        'validate-document': _handle_validate_document,
        'snapshot-document': _handle_snapshot_document,
        'writer-structure': _handle_writer_structure,
        'writer-structure-parity': _handle_writer_structure_parity,
        'operation': _handle_operation,
        'operations': _handle_operations,
        'mutation-request-inspect': _handle_mutation_request_inspect,
        'task-status-create': _handle_task_status_create,
        'task-status-update': _handle_task_status_update,
        'task-status': _handle_task_status,
        'task-statuses': _handle_task_statuses,
        'task-recovery': _handle_task_recovery,
        'task-recovery-playbooks': _handle_task_recovery_playbooks,
        'mcp-tools': _handle_mcp_tools,
        'mcp-catalog-snapshot': _handle_mcp_catalog_snapshot,
        'mcp-catalog-drift': _handle_mcp_catalog_drift,
        'mcp-tool-schema': _handle_mcp_tool_schema,
        'mcp-call': _handle_mcp_call,
        'mcp-server': _handle_mcp_server,
        'mcp-smoke': _handle_mcp_smoke,
        'mcp-config-audit': _handle_mcp_config_audit,
        'regression-manifest': _handle_regression_manifest,
        'regression-run': _handle_regression_run,
        'security-audit': _handle_security_audit,
        'performance-baseline': _handle_performance_baseline,
        'scan-dir': _handle_scan_dir,
        'batch-report': _handle_batch_report,
        'spreadsheet-read': _handle_spreadsheet_read,
        'spreadsheet-sheets': _handle_spreadsheet_sheets,
        'spreadsheet-rename-sheet': _handle_spreadsheet_rename_sheet,
        'spreadsheet-create-sheet': _handle_spreadsheet_create_sheet,
        'spreadsheet-set-sheet-visibility': _handle_spreadsheet_set_sheet_visibility,
        'spreadsheet-delete-sheet': _handle_spreadsheet_delete_sheet,
        'spreadsheet-copy-sheet': _handle_spreadsheet_copy_sheet,
        'spreadsheet-set-sheet-tab-color': _handle_spreadsheet_set_sheet_tab_color,
        'spreadsheet-inspect': _handle_spreadsheet_inspect,
        'spreadsheet-write': _handle_spreadsheet_write,
        'spreadsheet-formula-write': _handle_spreadsheet_formula_write,
        'presentation-replace': _handle_presentation_replace,
    }

