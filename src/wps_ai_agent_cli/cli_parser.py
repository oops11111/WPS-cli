from __future__ import annotations

import argparse

from .mcp_catalog_drift import DEFAULT_MCP_CATALOG_GUARD


def _add_environment_and_status_commands(subparsers: argparse._SubParsersAction) -> None:
    subparsers.add_parser("inspect-env", help="Inspect OS, pywin32, and WPS ProgID registration.")
    process_audit_parser = subparsers.add_parser(
        "wps-process-audit",
        help="List WPS-related processes and safe cleanup guidance without terminating anything.",
    )
    process_audit_parser.add_argument("--timeout-seconds", type=int, default=10, help="Timeout for process inspection.")
    cleanup_plan_parser = subparsers.add_parser(
        "cleanup-plan",
        help="Build a read-only local cleanup plan with approval-required candidates.",
    )
    cleanup_plan_parser.add_argument(
        "--workspace",
        default=".",
        help="Workspace root to inspect. Defaults to the current directory.",
    )
    cleanup_approval_parser = subparsers.add_parser(
        "cleanup-approval-manifest",
        help="Build a read-only cleanup approval manifest grouped by category.",
    )
    cleanup_approval_parser.add_argument(
        "--workspace",
        default=".",
        help="Workspace root to inspect. Defaults to the current directory.",
    )
    subparsers.add_parser("plan", help="Return the staged development roadmap.")

    tasks_parser = subparsers.add_parser("tasks", help="Return staged development tasks.")
    tasks_parser.add_argument("--phase", help="Filter by phase id, for example phase0.")
    tasks_parser.add_argument("--status", help="Filter by task status, for example next.")


def _add_conversion_commands(subparsers: argparse._SubParsersAction) -> None:
    smoke_parser = subparsers.add_parser(
        "com-smoke",
        help="Run the Phase 0 minimal COM open/save/close prototype.",
    )
    smoke_parser.add_argument(
        "--component",
        choices=["writer", "spreadsheets", "presentation"],
        required=True,
        help="WPS component to exercise.",
    )
    smoke_parser.add_argument("--input", required=True, help="Input document path.")
    smoke_parser.add_argument("--output", required=True, help="Output copy path.")
    smoke_parser.add_argument("--visible", action="store_true", help="Show WPS during the smoke run.")

    calc_parser = subparsers.add_parser(
        "calc-smoke",
        help="Run the Phase 0 WPS spreadsheet formula calculation verification.",
    )
    calc_parser.add_argument("--input", required=True, help="Input workbook path.")
    calc_parser.add_argument("--output", required=True, help="Output workbook copy path.")
    calc_parser.add_argument("--timeout-seconds", type=int, default=120, help="Timeout for the WPS spreadsheet COM smoke.")

    convert_parser = subparsers.add_parser(
        "convert-smoke",
        help="Run a Phase 0 WPS conversion smoke test.",
    )
    convert_parser.add_argument("--component", choices=["writer"], required=True)
    convert_parser.add_argument("--input", required=True, help="Input file path.")
    convert_parser.add_argument("--output", required=True, help="Output file path.")
    convert_parser.add_argument("--format", choices=["pdf"], required=True, help="Output format.")

    html_render_parser = subparsers.add_parser("html-render", help="Render local HTML to PDF or PNG with a sandboxed browser.")
    html_render_parser.add_argument("--input", required=True, help="Local HTML or HTM input path.")
    html_render_parser.add_argument("--output", required=True, help="New PDF or PNG output path; existing files are never overwritten.")
    html_render_parser.add_argument("--format", choices=["pdf", "png"], required=True)
    html_render_parser.add_argument("--page-size", choices=["A4", "Letter", "Legal", "Tabloid"], default="A4")
    html_render_parser.add_argument("--viewport-width", type=int, default=1280)
    html_render_parser.add_argument("--viewport-height", type=int, default=900)
    html_render_parser.add_argument("--timeout-seconds", type=int, default=30)
    html_render_parser.add_argument("--allow-javascript", action="store_true", help="Enable page scripts explicitly; scripts remain network-isolated.")
    html_render_parser.add_argument("--task-id", help="Optional long-running task status id.")

    html_batch_parser = subparsers.add_parser("html-batch-convert", help="Convert a bounded directory of HTML files with per-file results.")
    html_batch_parser.add_argument("--input-dir", required=True)
    html_batch_parser.add_argument("--output-dir", required=True)
    html_batch_parser.add_argument("--mode", choices=["pdf", "png", "docx"], required=True)
    html_batch_parser.add_argument("--recursive", action="store_true")
    html_batch_parser.add_argument("--task-id")

    batch_request_parser = subparsers.add_parser("html-batch-request", help="Inspect a recorded HTML batch request without changing files.")
    batch_request_parser.add_argument("--batch-request-id", required=True, help="Original batch conversion request_id to inspect.")
    batch_request_parser.add_argument("--verify", action="store_true", help="Verify current manifest and source/output hashes without modifying state.")

    template_report_parser = subparsers.add_parser("batch-template-report", help="Render a local text or DOCX template from a verified batch conversion manifest.")
    template_report_parser.add_argument("--manifest", required=True)
    template_report_parser.add_argument("--template", required=True)
    template_report_parser.add_argument("--output", required=True)
    template_report_parser.add_argument("--task-id")

    html_editable_parser = subparsers.add_parser("html-editable", help="Map semantic local HTML to an editable Writer DOCX.")
    html_editable_parser.add_argument("--input", required=True, help="Local HTML or HTM source path.")
    html_editable_parser.add_argument("--output", required=True, help="New DOCX output path; existing files are never overwritten.")
    html_editable_parser.add_argument("--task-id", help="Optional long-running task status id.")

    html_roundtrip_parser = subparsers.add_parser("html-roundtrip-plan", help="Validate owned HTML schema and build a read-only object identity map.")
    html_roundtrip_parser.add_argument("--input", required=True, help="Owned HTML v1 source path.")
    html_import_parser = subparsers.add_parser("html-controlled-import", help="Import owned HTML to DOCX with stable object bookmarks and a mapping sidecar.")
    html_import_parser.add_argument("--input", required=True)
    html_import_parser.add_argument("--output", required=True)
    html_import_parser.add_argument("--task-id")
    html_verify_parser = subparsers.add_parser("html-roundtrip-verify", help="Verify mapped object bookmark identity in an edited DOCX.")
    html_verify_parser.add_argument("--docx", required=True)
    html_verify_parser.add_argument("--mapping", required=True)
    html_export_parser = subparsers.add_parser("html-roundtrip-export", help="Serialize a verified controlled DOCX back to owned HTML v1.")
    html_export_parser.add_argument("--docx", required=True)
    html_export_parser.add_argument("--mapping", required=True)
    html_export_parser.add_argument("--output", required=True)
    html_export_parser.add_argument("--task-id")


def _add_document_commands(subparsers: argparse._SubParsersAction) -> None:
    writer_table_smoke_parser = subparsers.add_parser(
        "writer-table-smoke",
        help="Run a repeatable WPS Writer table cell update smoke test against an output copy.",
    )
    writer_table_smoke_parser.add_argument("--input", required=True, help="Input Writer fixture path.")
    writer_table_smoke_parser.add_argument("--output", required=True, help="Output copy path.")
    writer_table_smoke_parser.add_argument("--table-index", type=int, required=True, help="1-based table index.")
    writer_table_smoke_parser.add_argument("--row", type=int, required=True, help="1-based row index.")
    writer_table_smoke_parser.add_argument("--column", type=int, required=True, help="1-based column index.")
    writer_table_smoke_parser.add_argument("--text", required=True, help="Replacement cell text.")
    writer_table_smoke_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

    register_parser = subparsers.add_parser(
        "register-document",
        help="Register a file and return a stable document_id for later commands.",
    )
    register_parser.add_argument(
        "--component",
        choices=["writer", "spreadsheets", "presentation"],
        required=True,
    )
    register_parser.add_argument("--path", required=True, help="Document path to register.")

    subparsers.add_parser("documents", help="List registered documents.")

    backup_parser = subparsers.add_parser(
        "backup-document",
        help="Create a recoverable backup for a registered document_id.",
    )
    backup_parser.add_argument("--document-id", required=True, help="Registered document_id.")
    backup_parser.add_argument("--dry-run", action="store_true", help="Preview backup path without copying.")
    backup_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

    list_backups_parser = subparsers.add_parser(
        "list-backups",
        help="List recoverable backups, optionally scoped to one document_id.",
    )
    list_backups_parser.add_argument("--document-id", help="Optional registered document_id.")

    restore_backup_parser = subparsers.add_parser(
        "restore-backup",
        help="Restore a selected backup after first protecting the current file.",
    )
    restore_backup_parser.add_argument("--document-id", required=True, help="Registered document_id.")
    backup_selector = restore_backup_parser.add_mutually_exclusive_group(required=True)
    backup_selector.add_argument("--backup-name", help="Backup filename from list-backups.")
    backup_selector.add_argument("--backup-path", help="Backup path from list-backups.")
    restore_backup_parser.add_argument("--dry-run", action="store_true", help="Preview restore without copying.")
    restore_backup_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

    replace_parser = subparsers.add_parser(
        "writer-replace",
        help="Replace text in a registered WPS Writer document with backup, dry-run, and validation.",
    )
    replace_parser.add_argument("--document-id", required=True, help="Registered writer document_id.")
    replace_parser.add_argument("--find", required=True, help="Text to find.")
    replace_parser.add_argument("--replace", required=True, help="Replacement text.")
    replace_parser.add_argument("--dry-run", action="store_true", help="Preview matches without modifying the file.")
    replace_parser.add_argument(
        "--paragraph-index",
        type=int,
        help="Optional 1-based body paragraph index to limit replacement scope.",
    )
    replace_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

    bookmark_fill_parser = subparsers.add_parser(
        "writer-fill-bookmark",
        help="Fill a unique supported body or direct table-cell bookmark with backup and read-back validation.",
    )
    bookmark_fill_parser.add_argument("--document-id", required=True, help="Registered writer document_id.")
    bookmark_fill_parser.add_argument("--bookmark-name", required=True, help="Unique, non-reserved supported bookmark name.")
    bookmark_fill_parser.add_argument("--text", required=True, help="Text to write into the bookmark range.")
    bookmark_fill_parser.add_argument("--dry-run", action="store_true", help="Preview the bookmark target without modifying the file.")
    bookmark_fill_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

    writer_table_parser = subparsers.add_parser(
        "writer-table-write",
        help="Write text to a table cell in a registered WPS Writer document.",
    )
    writer_table_parser.add_argument("--document-id", required=True, help="Registered writer document_id.")
    writer_table_parser.add_argument("--table-index", type=int, required=True, help="1-based table index.")
    writer_table_parser.add_argument("--row", type=int, required=True, help="1-based row index.")
    writer_table_parser.add_argument("--column", type=int, required=True, help="1-based column index.")
    writer_table_parser.add_argument("--text", required=True, help="Replacement cell text.")
    writer_table_parser.add_argument("--dry-run", action="store_true", help="Preview target cell without modifying the file.")
    writer_table_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

    open_documents_parser = subparsers.add_parser(
        "open-documents",
        help="Attach to running WPS instances (never launches WPS) and list their open documents.",
    )
    open_documents_parser.add_argument(
        "--component", choices=["writer", "spreadsheets", "presentation"], help="Limit the probe to one component."
    )
    open_documents_parser.add_argument(
        "--register", action="store_true", help="Register saved open documents and return their stable document_id."
    )

    selection_read_parser = subparsers.add_parser(
        "writer-selection-read",
        help="Read the current selection of a registered Writer document that is open in a running WPS instance.",
    )
    selection_read_parser.add_argument("--document-id", required=True, help="Registered writer document_id.")

    selection_replace_parser = subparsers.add_parser(
        "writer-selection-replace",
        help="Replace the current selection text of an open, saved Writer document with backup and read-back validation.",
    )
    selection_replace_parser.add_argument("--document-id", required=True, help="Registered writer document_id.")
    selection_replace_parser.add_argument("--text", required=True, help="Replacement text (single line, at most 4096 characters).")
    selection_replace_parser.add_argument(
        "--expected-selection-text", help="Refuse to write unless the current selection text equals this value."
    )
    selection_replace_parser.add_argument("--dry-run", action="store_true", help="Preview the selection replacement without modifying the file.")
    selection_replace_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

    export_open_parser = subparsers.add_parser(
        "export-open-document",
        help="Export an open, saved Writer document to HTML without closing it or changing the source.",
    )
    export_open_parser.add_argument("--document-id", required=True, help="Registered writer document_id.")
    export_open_parser.add_argument("--output", required=True, help="New .html or .htm output path; existing files are never overwritten.")

    validate_parser = subparsers.add_parser(
        "validate-document",
        help="Run basic validation checks against a registered document.",
    )
    validate_parser.add_argument("--document-id", required=True, help="Registered document_id.")
    validate_parser.add_argument("--contains", help="Expected body text for writer documents.")
    validate_parser.add_argument("--cell", help="Cell address for spreadsheet validation.")
    validate_parser.add_argument("--equals", help="Expected cell value for spreadsheet validation.")

    snapshot_parser = subparsers.add_parser(
        "snapshot-document",
        help="Return a structural validation snapshot for a registered document.",
    )
    snapshot_parser.add_argument("--document-id", required=True, help="Registered document_id.")

    writer_structure_parser = subparsers.add_parser(
        "writer-structure", help="Inspect bounded Writer headings, styles, and bookmarks from OOXML.",
    )
    writer_structure_parser.add_argument("--document-id", required=True, help="Registered Writer document_id.")
    writer_structure_parser.add_argument("--limit", type=int, default=50, help="Maximum items per section, from 1 to 200.")
    writer_structure_parser.add_argument("--section", choices=["all", "headings", "styles", "bookmarks", "warnings"], default="all", help="Structure list to inspect.")
    writer_structure_parser.add_argument("--offset", type=int, default=0, help="Zero-based offset for a selected section.")
    writer_structure_parser.add_argument("--bookmark-name", help="Exact bookmark name; requires --section bookmarks.")
    writer_structure_parser.add_argument("--expected-sha256", help="Require the DOCX hash from the preceding page.")
    writer_structure_parser.add_argument("--include-text", action="store_true", help="Read bounded text from a unique supported bookmark.")
    writer_structure_parser.add_argument("--text-limit", type=int, default=200, help="Maximum returned bookmark text characters, from 1 to 4096.")

    writer_parity_parser = subparsers.add_parser(
        "writer-structure-parity", help="Compare a controlled Writer fixture with read-only WPS desktop observations.",
    )
    writer_parity_parser.add_argument("--run-wps", action="store_true", help="Explicitly launch WPS Writer for this local audit.")
    writer_parity_parser.add_argument("--timeout-seconds", type=int, default=90, help="WPS audit timeout, from 1 to 300 seconds.")
    writer_parity_parser.add_argument("--scope", choices=["structure", "nested"], default="structure", help="Controlled Writer fixture to compare.")
    writer_parity_parser.add_argument("--artifact-dir", help="Local JSON report directory.")


def _add_operation_and_task_commands(subparsers: argparse._SubParsersAction) -> None:
    operation_parser = subparsers.add_parser(
        "operation",
        help="Return a recorded operation by request_id.",
    )
    operation_parser.add_argument("--request", required=True, help="Recorded operation request_id.")

    inspect_parser = subparsers.add_parser(
        "mutation-request-inspect",
        help="Read operation and derived backup evidence for a mutation request.",
    )
    inspect_parser.add_argument("--request", required=True, help="Mutation request_id to inspect.")

    subparsers.add_parser("operations", help="List recorded operations.")

    task_status_create_parser = subparsers.add_parser(
        "task-status-create",
        help="Create a reusable status record for a long-running task.",
    )
    task_status_create_parser.add_argument("--task-id", help="Optional stable task id.")
    task_status_create_parser.add_argument(
        "--command",
        dest="tracked_command",
        required=True,
        help="Command or workflow being tracked.",
    )
    task_status_create_parser.add_argument("--operation-request-id", required=True, help="Request id for the tracked operation.")
    task_status_create_parser.add_argument("--document-id", help="Optional related document_id.")
    task_status_create_parser.add_argument("--message", help="Initial status message.")
    task_status_create_parser.add_argument(
        "--recovery-guidance",
        action="append",
        default=[],
        help="Recovery guidance item. May be provided more than once.",
    )

    task_status_update_parser = subparsers.add_parser(
        "task-status-update",
        help="Update a long-running task status record.",
    )
    task_status_update_parser.add_argument("--task-id", required=True, help="Task id to update.")
    task_status_update_parser.add_argument(
        "--state",
        choices=["pending", "running", "succeeded", "failed", "cancelled"],
        required=True,
        help="New task state.",
    )
    task_status_update_parser.add_argument("--progress-percent", type=int, help="Progress percentage, 0 through 100.")
    task_status_update_parser.add_argument("--message", help="Updated status message.")
    task_status_update_parser.add_argument(
        "--recovery-guidance",
        action="append",
        help="Recovery guidance item. May be provided more than once.",
    )
    task_status_update_parser.add_argument("--result-ref", help="Optional operation request id or output reference.")

    task_status_parser = subparsers.add_parser(
        "task-status",
        help="Return one long-running task status record.",
    )
    task_status_parser.add_argument("--task-id", required=True, help="Task id to return.")

    subparsers.add_parser("task-statuses", help="List long-running task status records.")

    task_recovery_parser = subparsers.add_parser(
        "task-recovery",
        help="Return a recovery playbook for a long-running task status.",
    )
    task_recovery_parser.add_argument("--task-id", required=True, help="Task id to recover or inspect.")

    subparsers.add_parser(
        "task-recovery-playbooks",
        help="List available long-running task recovery playbooks.",
    )


def _add_mcp_commands(subparsers: argparse._SubParsersAction) -> None:
    mcp_tools_parser = subparsers.add_parser(
        "mcp-tools",
        help="List draft MCP tool schemas mapped from CLI commands.",
    )
    mcp_tools_parser.add_argument("--category", help="Optional tool category filter.")
    mcp_tools_parser.add_argument(
        "--mutates-document",
        choices=["true", "false"],
        help="Optional filter for document-mutating tools.",
    )

    subparsers.add_parser(
        "mcp-catalog-snapshot",
        help="Summarize MCP tool catalog counts, categories, WPS requirements, and safety-note coverage.",
    )
    mcp_catalog_drift_parser = subparsers.add_parser(
        "mcp-catalog-drift",
        help="Compare the current MCP catalog against a read-only baseline guard.",
    )
    mcp_catalog_drift_parser.add_argument(
        "--guard",
        default=DEFAULT_MCP_CATALOG_GUARD,
        help="Path to MCP catalog guard baseline JSON.",
    )

    mcp_tool_schema_parser = subparsers.add_parser(
        "mcp-tool-schema",
        help="Return one draft MCP tool schema by MCP tool name or CLI command.",
    )
    mcp_tool_schema_parser.add_argument("--name", required=True, help="MCP tool name or CLI command.")

    mcp_call_parser = subparsers.add_parser(
        "mcp-call",
        help="Invoke a draft MCP tool through the local adapter layer.",
    )
    mcp_call_parser.add_argument("--name", required=True, help="MCP tool name or CLI command.")
    mcp_call_parser.add_argument(
        "--arguments-json",
        default="{}",
        help="JSON object of tool arguments.",
    )

    mcp_server_parser = subparsers.add_parser(
        "mcp-server",
        help="Run the local MCP-compatible JSON-RPC server prototype over stdio.",
    )
    mcp_server_parser.add_argument(
        "--once-json",
        help="Handle one JSON-RPC request and exit; useful for tests and smoke checks.",
    )

    mcp_smoke_parser = subparsers.add_parser(
        "mcp-smoke",
        help="Run repeatable MCP server smoke checks for initialize, tools/list, and tools/call.",
    )
    mcp_smoke_parser.add_argument(
        "--expected-min-tools",
        type=int,
        default=1,
        help="Minimum number of tools expected from tools/list.",
    )
    mcp_smoke_parser.add_argument(
        "--tool-name",
        default="wps_agent_tasks",
        help="Tool name to exercise through tools/call.",
    )
    mcp_smoke_parser.add_argument("--arguments-json", help="JSON object of arguments for a local read-only tool call.")

    mcp_config_audit_parser = subparsers.add_parser(
        "mcp-config-audit",
        help="Audit a local MCP client config and run a configured tools/list smoke check.",
    )
    mcp_config_audit_parser.add_argument(
        "--config",
        default="config/mcp_client_config.example.json",
        help="Path to MCP client config JSON.",
    )
    mcp_config_audit_parser.add_argument(
        "--server-name",
        default="wps-ai-agent-cli",
        help="Server key under mcpServers.",
    )
    mcp_config_audit_parser.add_argument(
        "--expected-min-tools",
        type=int,
        default=33,
        help="Minimum number of tools expected from configured tools/list smoke.",
    )
    mcp_config_audit_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=15,
        help="Timeout for the configured tools/list smoke.",
    )


def _add_regression_and_release_commands(subparsers: argparse._SubParsersAction) -> None:
    regression_manifest_parser = subparsers.add_parser(
        "regression-manifest",
        help="List regression manifest scenarios and smoke matrix metadata.",
    )
    regression_manifest_parser.add_argument(
        "--manifest",
        default="config/regression_manifest.json",
        help="Path to regression manifest JSON.",
    )
    regression_manifest_parser.add_argument("--profile", help="Optional scenario profile filter, for example safe or wps.")
    regression_manifest_parser.add_argument("--include-wps", action="store_true", help="Include scenarios that require WPS.")

    regression_run_parser = subparsers.add_parser(
        "regression-run",
        help="Run regression scenarios from the manifest.",
    )
    regression_run_parser.add_argument(
        "--manifest",
        default="config/regression_manifest.json",
        help="Path to regression manifest JSON.",
    )
    regression_run_parser.add_argument("--profile", help="Optional scenario profile filter. Defaults to manifest default_profile.")
    regression_run_parser.add_argument("--include-wps", action="store_true", help="Include scenarios that require WPS.")
    regression_run_parser.add_argument(
        "--artifact-dir",
        help="Optional directory where a timestamped regression-run JSON artifact will be written.",
    )


    subparsers.add_parser(
        "security-audit",
        help="Audit mutating CLI and MCP tool safety boundaries.",
    )

    subparsers.add_parser(
        "performance-baseline",
        help="Capture runtime and output-size baselines for safe read-only commands.",
    )


def _add_file_scan_commands(subparsers: argparse._SubParsersAction) -> None:
    scan_parser = subparsers.add_parser(
        "scan-dir",
        help="Scan a directory for supported WPS files and registration status.",
    )
    scan_parser.add_argument("--path", required=True, help="Directory to scan.")
    scan_parser.add_argument("--recursive", action="store_true", help="Scan recursively.")

    batch_report_parser = subparsers.add_parser(
        "batch-report",
        help="Combine directory scan, registration status, and validation snapshots.",
    )
    batch_report_parser.add_argument("--path", required=True, help="Directory to report on.")
    batch_report_parser.add_argument("--recursive", action="store_true", help="Report recursively.")
    batch_report_parser.add_argument(
        "--no-snapshots",
        action="store_true",
        help="Skip validation snapshots and only return scan and registration status.",
    )


def _add_spreadsheet_commands(subparsers: argparse._SubParsersAction) -> None:
    spreadsheet_read_parser = subparsers.add_parser(
        "spreadsheet-read",
        help="Read an A1 range from a registered spreadsheet document.",
    )
    spreadsheet_read_parser.add_argument("--document-id", required=True, help="Registered spreadsheet document_id.")
    spreadsheet_read_parser.add_argument("--range", required=True, help="A1 range to read, for example A1:D6.")
    spreadsheet_read_parser.add_argument("--sheet", help="Optional sheet name. Defaults to first sheet.")

    spreadsheet_sheets_parser = subparsers.add_parser(
        "spreadsheet-sheets",
        help="List worksheet order, visibility, and used dimensions without launching WPS.",
    )
    spreadsheet_sheets_parser.add_argument("--document-id", required=True, help="Registered spreadsheet document_id.")

    spreadsheet_rename_parser = subparsers.add_parser(
        "spreadsheet-rename-sheet",
        help="Rename a worksheet with backup and ordered read-back validation.",
    )
    spreadsheet_rename_parser.add_argument("--document-id", required=True, help="Registered spreadsheet document_id.")
    spreadsheet_rename_parser.add_argument("--old-name", required=True, help="Current worksheet name.")
    spreadsheet_rename_parser.add_argument("--new-name", required=True, help="New worksheet name.")
    spreadsheet_rename_parser.add_argument("--dry-run", action="store_true", help="Validate and preview without backup or WPS.")
    spreadsheet_rename_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

    spreadsheet_create_parser = subparsers.add_parser(
        "spreadsheet-create-sheet",
        help="Create a worksheet with backup and ordered read-back validation.",
    )
    spreadsheet_create_parser.add_argument("--document-id", required=True, help="Registered spreadsheet document_id.")
    spreadsheet_create_parser.add_argument("--name", required=True, help="New worksheet name.")
    spreadsheet_create_parser.add_argument("--index", type=int, help="1-based insertion index; defaults to the end.")
    spreadsheet_create_parser.add_argument("--dry-run", action="store_true", help="Validate and preview without backup or WPS.")
    spreadsheet_create_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

    spreadsheet_visibility_parser = subparsers.add_parser(
        "spreadsheet-set-sheet-visibility",
        help="Set worksheet visibility with backup and ordered state read-back.",
    )
    spreadsheet_visibility_parser.add_argument("--document-id", required=True, help="Registered spreadsheet document_id.")
    spreadsheet_visibility_parser.add_argument("--sheet-name", required=True, help="Worksheet to show or hide.")
    spreadsheet_visibility_parser.add_argument("--visible", required=True, choices=("true", "false"), help="Set worksheet visible or hidden.")
    spreadsheet_visibility_parser.add_argument("--dry-run", action="store_true", help="Validate and preview without backup or WPS.")
    spreadsheet_visibility_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

    spreadsheet_delete_parser = subparsers.add_parser("spreadsheet-delete-sheet", help="Delete a worksheet with backup and ordered read-back validation.")
    spreadsheet_delete_parser.add_argument("--document-id", required=True, help="Registered spreadsheet document_id.")
    spreadsheet_delete_parser.add_argument("--sheet-name", required=True, help="Worksheet to delete.")
    spreadsheet_delete_parser.add_argument("--dry-run", action="store_true", help="Validate and preview without backup or WPS.")
    spreadsheet_delete_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

    spreadsheet_copy_parser = subparsers.add_parser("spreadsheet-copy-sheet", help="Copy a worksheet with backup and ordered read-back validation.")
    spreadsheet_copy_parser.add_argument("--document-id", required=True, help="Registered spreadsheet document_id.")
    spreadsheet_copy_parser.add_argument("--source-name", required=True, help="Worksheet to copy.")
    spreadsheet_copy_parser.add_argument("--new-name", required=True, help="Name for the copied worksheet.")
    spreadsheet_copy_parser.add_argument("--index", type=int, help="1-based insertion index; defaults to the end.")
    spreadsheet_copy_parser.add_argument("--dry-run", action="store_true", help="Validate and preview without backup or WPS.")
    spreadsheet_copy_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

    spreadsheet_tab_color_parser = subparsers.add_parser("spreadsheet-set-sheet-tab-color", help="Set worksheet tab color with backup and read-back validation.")
    spreadsheet_tab_color_parser.add_argument("--document-id", required=True, help="Registered spreadsheet document_id.")
    spreadsheet_tab_color_parser.add_argument("--sheet-name", required=True, help="Worksheet whose tab color will change.")
    spreadsheet_tab_color_parser.add_argument("--color", required=True, help="Hex color in #RRGGBB form, or 'none' to clear it.")
    spreadsheet_tab_color_parser.add_argument("--dry-run", action="store_true", help="Validate and preview without backup or WPS.")
    spreadsheet_tab_color_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

    spreadsheet_inspect_parser = subparsers.add_parser(
        "spreadsheet-inspect",
        help="Inspect formulas, saved cached values, recalculated values, and WPS display text without saving.",
    )
    spreadsheet_inspect_parser.add_argument("--document-id", required=True, help="Registered spreadsheet document_id.")
    spreadsheet_inspect_parser.add_argument("--range", required=True, help="Finite A1 range to inspect, for example A1:D6.")
    spreadsheet_inspect_parser.add_argument("--sheet", help="Optional sheet name. Defaults to first sheet.")

    spreadsheet_write_parser = subparsers.add_parser(
        "spreadsheet-write",
        help="Write a JSON matrix to an A1 range in a registered spreadsheet document.",
    )
    spreadsheet_write_parser.add_argument("--document-id", required=True, help="Registered spreadsheet document_id.")
    spreadsheet_write_parser.add_argument("--range", required=True, help="A1 range to write, for example A1:B2.")
    spreadsheet_write_parser.add_argument("--values-json", required=True, help="Rectangular JSON matrix, for example [[1,2],[3,4]].")
    spreadsheet_write_parser.add_argument("--sheet", help="Optional sheet name. Defaults to first sheet.")
    spreadsheet_write_parser.add_argument("--dry-run", action="store_true", help="Preview write shape without modifying the file.")
    spreadsheet_write_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

    spreadsheet_formula_parser = subparsers.add_parser(
        "spreadsheet-formula-write",
        help="Write formulas to an A1 range, recalculate with WPS, and validate cached values.",
    )
    spreadsheet_formula_parser.add_argument("--document-id", required=True, help="Registered spreadsheet document_id.")
    spreadsheet_formula_parser.add_argument("--range", required=True, help="A1 range to write, for example D4:D6.")
    spreadsheet_formula_parser.add_argument("--formulas-json", required=True, help="Rectangular JSON matrix of formulas, for example [[\"=A1+B1\"]].")
    spreadsheet_formula_parser.add_argument("--expected-values-json", required=True, help="Rectangular JSON matrix of expected cached values.")
    spreadsheet_formula_parser.add_argument("--sheet", help="Optional sheet name. Defaults to first sheet.")
    spreadsheet_formula_parser.add_argument("--dry-run", action="store_true", help="Preview formula write shape without modifying the file.")
    spreadsheet_formula_parser.add_argument("--task-id", help="Optional long-running task status id to update.")


def _add_presentation_commands(subparsers: argparse._SubParsersAction) -> None:
    presentation_replace_parser = subparsers.add_parser(
        "presentation-replace",
        help="Replace text in a registered presentation with backup, validation, and idempotency.",
    )
    presentation_replace_parser.add_argument("--document-id", required=True, help="Registered presentation document_id.")
    presentation_replace_parser.add_argument("--find", required=True, help="Text to find.")
    presentation_replace_parser.add_argument("--replace", required=True, help="Replacement text.")
    presentation_replace_parser.add_argument("--dry-run", action="store_true", help="Preview matches without modifying the file.")
    presentation_replace_parser.add_argument(
        "--slide-index",
        type=int,
        help="Optional 1-based slide index to limit replacement scope.",
    )
    presentation_replace_parser.add_argument("--task-id", help="Optional long-running task status id to update.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wps-agent",
        description="Agent-friendly CLI for WPS feasibility validation and automation.",
    )
    parser.add_argument("--request-id", help="Stable request id for idempotent agent calls.")
    parser.epilog = "Add --strict-exit anywhere to exit with status 1 when the response has ok=false (default exit status is 0)."
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_environment_and_status_commands(subparsers)
    _add_conversion_commands(subparsers)
    _add_document_commands(subparsers)
    _add_operation_and_task_commands(subparsers)
    _add_mcp_commands(subparsers)
    _add_regression_and_release_commands(subparsers)
    _add_file_scan_commands(subparsers)
    _add_spreadsheet_commands(subparsers)
    _add_presentation_commands(subparsers)
    return parser
