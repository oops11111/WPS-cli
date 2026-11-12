from __future__ import annotations

import argparse

from .mcp_catalog_drift import DEFAULT_MCP_CATALOG_GUARD
from .mcp_config_audit import (
    MCP_CONFIG_AUDIT_MAX_EXPECTED_TOOLS,
    MCP_CONFIG_AUDIT_MAX_SERVER_NAME_CHARS,
    MCP_CONFIG_AUDIT_MIN_EXPECTED_TOOLS,
    MCP_CONFIG_AUDIT_TIMEOUT_MAX_SECONDS,
    MCP_CONFIG_AUDIT_TIMEOUT_MIN_SECONDS,
)


def _mcp_config_audit_timeout(value: str) -> int:
    try:
        timeout = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if not MCP_CONFIG_AUDIT_TIMEOUT_MIN_SECONDS <= timeout <= MCP_CONFIG_AUDIT_TIMEOUT_MAX_SECONDS:
        raise argparse.ArgumentTypeError(
            f"must be between {MCP_CONFIG_AUDIT_TIMEOUT_MIN_SECONDS} and {MCP_CONFIG_AUDIT_TIMEOUT_MAX_SECONDS} seconds"
        )
    return timeout


def _mcp_config_audit_expected_tools(value: str) -> int:
    try:
        count = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if not MCP_CONFIG_AUDIT_MIN_EXPECTED_TOOLS <= count <= MCP_CONFIG_AUDIT_MAX_EXPECTED_TOOLS:
        raise argparse.ArgumentTypeError(
            f"must be between {MCP_CONFIG_AUDIT_MIN_EXPECTED_TOOLS} and {MCP_CONFIG_AUDIT_MAX_EXPECTED_TOOLS}"
        )
    return count


def _mcp_config_audit_server_name(value: str) -> str:
    if not value.strip() or len(value) > MCP_CONFIG_AUDIT_MAX_SERVER_NAME_CHARS:
        raise argparse.ArgumentTypeError("must be nonempty and at most 256 characters")
    return value


def _add_environment_and_status_commands(subparsers: argparse._SubParsersAction) -> None:
    subparsers.add_parser("inspect-env", help="Inspect OS, pywin32, and WPS ProgID registration.")
    version_compare_parser = subparsers.add_parser(
        "wps-version-compare",
        help="Compare observed WPS component versions with the persisted workspace baseline.",
    )
    version_compare_parser.add_argument(
        "--workspace",
        default=".",
        help="Workspace whose .wps-agent/wps-versions.json stores the baseline.",
    )
    version_compare_parser.add_argument(
        "--record",
        action="store_true",
        help="Persist parsable observed versions without launching WPS or modifying documents.",
    )
    version_compare_parser.add_argument("--writer-version", default=None, help="Observed Writer version.")
    version_compare_parser.add_argument("--spreadsheets-version", default=None, help="Observed Spreadsheets version.")
    version_compare_parser.add_argument("--presentation-version", default=None, help="Observed Presentation version.")
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
    calc_parser.add_argument(
        "--timeout-seconds", type=int, default=120, help="Timeout for the WPS spreadsheet COM smoke."
    )

    convert_parser = subparsers.add_parser(
        "convert-smoke",
        help="Convert a Writer, Spreadsheet, or Presentation file to PDF through WPS COM.",
    )
    convert_parser.add_argument(
        "--component",
        choices=["writer", "spreadsheets", "presentation"],
        required=True,
    )
    convert_parser.add_argument("--input", required=True, help="Input file path.")
    convert_parser.add_argument("--output", required=True, help="Output file path.")
    convert_parser.add_argument("--format", choices=["pdf"], required=True, help="Output format.")

    html_render_parser = subparsers.add_parser(
        "html-render", help="Render local HTML to PDF or PNG with a sandboxed browser."
    )
    html_render_parser.add_argument("--input", required=True, help="Local HTML or HTM input path.")
    html_render_parser.add_argument(
        "--output", required=True, help="New PDF or PNG output path; existing files are never overwritten."
    )
    html_render_parser.add_argument("--format", choices=["pdf", "png"], required=True)
    html_render_parser.add_argument("--page-size", choices=["A4", "Letter", "Legal", "Tabloid"], default="A4")
    html_render_parser.add_argument("--viewport-width", type=int, default=1280)
    html_render_parser.add_argument("--viewport-height", type=int, default=900)
    html_render_parser.add_argument("--timeout-seconds", type=int, default=30)
    html_render_parser.add_argument(
        "--allow-javascript",
        action="store_true",
        help="Enable page scripts explicitly; scripts remain network-isolated.",
    )
    html_render_parser.add_argument("--task-id", help="Optional long-running task status id.")

    html_batch_parser = subparsers.add_parser(
        "html-batch-convert", help="Convert a bounded directory of HTML files with per-file results."
    )
    html_batch_parser.add_argument("--input-dir", required=True)
    html_batch_parser.add_argument("--output-dir", required=True)
    html_batch_parser.add_argument("--mode", choices=["pdf", "png", "docx"], required=True)
    html_batch_parser.add_argument("--recursive", action="store_true")
    html_batch_parser.add_argument("--task-id")

    batch_request_parser = subparsers.add_parser(
        "html-batch-request", help="Inspect a recorded HTML batch request without changing files."
    )
    batch_request_parser.add_argument(
        "--batch-request-id", required=True, help="Original batch conversion request_id to inspect."
    )
    batch_request_parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify current manifest and source/output hashes without modifying state.",
    )

    template_report_parser = subparsers.add_parser(
        "batch-template-report", help="Render a local text or DOCX template from a verified batch conversion manifest."
    )
    template_report_parser.add_argument("--manifest", required=True)
    template_report_parser.add_argument("--template", required=True)
    template_report_parser.add_argument("--output", required=True)
    template_report_parser.add_argument("--task-id")

    html_editable_parser = subparsers.add_parser(
        "html-editable", help="Map semantic local HTML to an editable DOCX, XLSX or PPTX."
    )
    html_editable_parser.add_argument("--input", required=True, help="Local HTML or HTM source path.")
    html_editable_parser.add_argument(
        "--output", required=True, help="New output path matching --format; existing files are never overwritten."
    )
    html_editable_parser.add_argument(
        "--format",
        choices=["docx", "xlsx", "pptx"],
        default="docx",
        help=(
            "docx: Writer content with inline formatting, merged table cells and images. xlsx: each table becomes a "
            "worksheet with merged cells and typed numbers. pptx: each section or h1/h2 becomes a slide, with "
            "tables, images, speaker notes, CSS entrance animations and slide transitions."
        ),
    )
    html_editable_parser.add_argument(
        "--fidelity",
        choices=["editable", "appearance"],
        default="editable",
        help=(
            "editable (default): native paragraphs, lists and tables styled from the computed CSS. appearance: for "
            "pptx, every element is placed where the browser lays it out, with decorative boxes; needs the browser."
        ),
    )
    html_editable_parser.add_argument("--task-id", help="Optional long-running task status id.")

    convert_parser = subparsers.add_parser(
        "convert",
        help="Convert between HTML, DOCX, XLSX, PPTX, PDF, Markdown, CSV/TSV and the WPS, legacy Office and ODF "
        "formats, picking the converter from the two file extensions.",
    )
    convert_parser.add_argument("--input", required=True, help="Source file.")
    convert_parser.add_argument(
        "--output",
        required=True,
        help="New output file; its extension chooses the format. For .png, pages are written as <name>-001.png ...",
    )
    convert_parser.add_argument("--fidelity", choices=["editable", "appearance"], default="editable")
    convert_parser.add_argument("--ocr", action="store_true", help="Read scanned PDF pages with OCR (ocr extra).")
    convert_parser.add_argument("--sheet", help="Worksheet to read (xlsx to csv, docx or pptx); the first by default.")
    convert_parser.add_argument("--range", dest="cell_range", help="Worksheet range for a table, such as A1:D20.")
    convert_parser.add_argument(
        "--images", choices=["embed", "files"], default="embed", help="HTML output: data URIs or a <name>_files folder."
    )
    convert_parser.add_argument("--encoding", help="CSV/TSV text encoding; detected when reading by default.")
    convert_parser.add_argument("--delimiter", help="CSV delimiter; detected when reading by default.")
    convert_parser.add_argument("--dpi", type=int, default=150, help="PNG resolution (WPS page images).")
    convert_parser.add_argument("--no-browser", action="store_true", help="Use the built-in CSS cascade only.")
    convert_parser.add_argument(
        "--check", action="store_true", help="Run fidelity-check on the result (without layout) and report it."
    )
    convert_parser.add_argument("--task-id", help="Optional long-running task status id.")

    fidelity_parser = subparsers.add_parser(
        "fidelity-check",
        help="Compare a converted file with its source: text, structure, formatting, animations, data and layout.",
    )
    fidelity_parser.add_argument("--source", required=True, help="The original file.")
    fidelity_parser.add_argument("--target", required=True, help="The converted file.")
    fidelity_parser.add_argument(
        "--renderer",
        choices=["auto", "wps", "libreoffice", "none"],
        default="auto",
        help="Layout renderer: WPS is the official one on Windows; LibreOffice is the regression baseline.",
    )
    fidelity_parser.add_argument("--no-layout", action="store_true", help="Skip the rendered-page comparison.")
    fidelity_parser.add_argument(
        "--baseline", type=float, help="Recorded LibreOffice layout score; the check fails below baseline - 0.02."
    )
    fidelity_parser.add_argument("--no-browser", action="store_true", help="Read HTML with the built-in cascade.")

    html_roundtrip_parser = subparsers.add_parser(
        "html-roundtrip-plan", help="Validate owned HTML schema and build a read-only object identity map."
    )
    html_roundtrip_parser.add_argument("--input", required=True, help="Owned HTML v1 source path.")
    html_import_parser = subparsers.add_parser(
        "html-controlled-import", help="Import owned HTML to DOCX with stable object bookmarks and a mapping sidecar."
    )
    html_import_parser.add_argument("--input", required=True)
    html_import_parser.add_argument("--output", required=True)
    html_import_parser.add_argument("--task-id")
    html_verify_parser = subparsers.add_parser(
        "html-roundtrip-verify", help="Verify mapped object bookmark identity in an edited DOCX."
    )
    html_verify_parser.add_argument("--docx", required=True)
    html_verify_parser.add_argument("--mapping", required=True)
    html_export_parser = subparsers.add_parser(
        "html-roundtrip-export", help="Serialize a verified controlled DOCX back to owned HTML v1."
    )
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

    document_new_parser = subparsers.add_parser(
        "document-new",
        help="Create a blank .docx, .xlsx or .pptx offline (no WPS) and register it.",
    )
    document_new_parser.add_argument(
        "--component",
        choices=["writer", "spreadsheets", "presentation"],
        required=True,
    )
    document_new_parser.add_argument(
        "--path", required=True, help="New file path (.docx, .xlsx or .pptx to match --component); never overwritten."
    )
    document_new_parser.add_argument(
        "--title",
        help="Optional title: a Title paragraph (writer), the first worksheet's name (spreadsheets) or a title slide.",
    )
    document_new_parser.add_argument(
        "--no-register", action="store_true", help="Create the file without registering it."
    )
    document_new_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

    pdf_info_parser = subparsers.add_parser("pdf-info", help="Pages, page sizes, metadata and text layer of a PDF.")
    pdf_info_parser.add_argument("--input", required=True, help="PDF path.")
    pdf_merge_parser = subparsers.add_parser("pdf-merge", help="Merge PDFs, in the order given, into a new PDF.")
    pdf_merge_parser.add_argument(
        "--input", action="append", required=True, help="Input PDF; repeat for each file, in order (two or more)."
    )
    pdf_merge_parser.add_argument("--output", required=True, help="New PDF path; never overwritten.")
    pdf_merge_parser.add_argument("--task-id", help="Optional long-running task status id to update.")
    pdf_split_parser = subparsers.add_parser(
        "pdf-split", help="Split a PDF into files of N pages, or one file per range."
    )
    pdf_split_parser.add_argument("--input", required=True, help="PDF path.")
    pdf_split_parser.add_argument("--output-dir", required=True, help="Existing folder for the new files.")
    pdf_split_parser.add_argument("--every", type=int, help="Pages per file (1 by default).")
    pdf_split_parser.add_argument("--ranges", help='One file per item: "1-3,4-6,7-".')
    pdf_split_parser.add_argument("--task-id", help="Optional long-running task status id to update.")
    pdf_extract_parser = subparsers.add_parser("pdf-extract-pages", help="Copy chosen pages into a new PDF.")
    pdf_extract_parser.add_argument("--input", required=True, help="PDF path.")
    pdf_extract_parser.add_argument("--output", required=True, help="New PDF path; never overwritten.")
    pdf_extract_parser.add_argument(
        "--pages",
        required=True,
        help='Pages, 1-based: 1,3-5,8- (8- runs to the last page). Order is kept, so "3,1" reorders.',
    )
    pdf_extract_parser.add_argument("--task-id", help="Optional long-running task status id to update.")
    pdf_watermark_parser = subparsers.add_parser("pdf-watermark", help="Draw a text watermark across PDF pages.")
    pdf_watermark_parser.add_argument("--input", required=True, help="PDF path.")
    pdf_watermark_parser.add_argument("--output", required=True, help="New PDF path; never overwritten.")
    pdf_watermark_parser.add_argument("--text", required=True, help="One line of 1 to 100 characters; Chinese works.")
    pdf_watermark_parser.add_argument(
        "--pages", help="Pages, 1-based: 1,3-5,8- (8- runs to the last page). Every page by default."
    )
    pdf_watermark_parser.add_argument("--font-size", type=int, default=48, help="Points, 6-300 (48).")
    pdf_watermark_parser.add_argument("--opacity", type=int, default=15, help="Percent, 1-100 (15).")
    pdf_watermark_parser.add_argument("--angle", type=int, default=45, help="Degrees counter-clockwise (45).")
    pdf_watermark_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

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
    restore_backup_parser.add_argument("--backup-name", help="Backup filename from list-backups.")
    restore_backup_parser.add_argument(
        "--backup-path", help="Backup path from list-backups. With --backup-name, both must name the same file."
    )
    restore_backup_parser.add_argument("--dry-run", action="store_true", help="Preview restore without copying.")
    restore_backup_parser.add_argument(
        "--close-in-wps",
        action="store_true",
        help=(
            "If the document is open in WPS with no unsaved changes, close it there without saving before restoring. "
            "Refused when WPS has unsaved changes. Without this flag WPS is never touched."
        ),
    )
    restore_backup_parser.add_argument("--task-id", help="Optional long-running task status id to update.")
    restore_backup_parser.add_argument(
        "--confirm",
        action="store_true",
        help="Acknowledge this destructive command (the MCP server requires it when not --dry-run; a person typing the command confirms by running it).",
    )

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

    batch_parser = subparsers.add_parser(
        "batch",
        help="Run a JSON list of tool calls in order, each with its own checks, and report every one.",
    )
    batch_source = batch_parser.add_mutually_exclusive_group(required=True)
    batch_source.add_argument(
        "--commands-json", help='JSON array: [{"tool": "writer-replace", "arguments": {"document_id": "...", ...}}].'
    )
    batch_source.add_argument("--commands-file", help="Path of a UTF-8 JSON file holding that array.")
    batch_parser.add_argument(
        "--continue-on-error", action="store_true", help="Run the remaining commands after one fails."
    )
    batch_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

    get_parser = subparsers.add_parser(
        "get",
        help='Read one part of a registered document by path, such as /sheet["Sheet1"]/cell["C12"] or /paragraph[3].',
    )
    get_parser.add_argument("--document-id", required=True, help="Registered document_id.")
    get_parser.add_argument("--path", required=True, help="Path such as /paragraph[3], /table[1]/cell[2,3], /slide[2].")

    view_parser = subparsers.add_parser(
        "document-view", help="Summarise a registered document: outline, tables, sheets or slides (read-only)."
    )
    view_parser.add_argument("--document-id", required=True, help="Registered document_id.")

    check_parser = subparsers.add_parser(
        "document-check",
        help="List problems in a registered document: unfilled placeholders, heading jumps, formula errors (read-only).",
    )
    check_parser.add_argument("--document-id", required=True, help="Registered document_id.")

    merge_parser = subparsers.add_parser(
        "writer-merge",
        help="Fill {{name}} placeholders (body, tables, headers, footers) from JSON data, with backup and read-back.",
    )
    merge_parser.add_argument("--document-id", required=True, help="Registered writer document_id (.docx).")
    merge_source = merge_parser.add_mutually_exclusive_group(required=True)
    merge_source.add_argument("--data-json", help='JSON object of names and values: {"客户": "甲公司", "金额": 1200}.')
    merge_source.add_argument("--data-file", help="Path of a UTF-8 JSON file holding that object.")
    merge_parser.add_argument(
        "--require-all", action="store_true", help="Refuse, changing nothing, when a placeholder has no value."
    )
    merge_parser.add_argument("--dry-run", action="store_true", help="List the placeholders without changing the file.")
    merge_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

    image_parser = subparsers.add_parser(
        "writer-insert-image",
        help="Insert a picture (inline, own paragraph) after a body paragraph, with an optional caption below.",
    )
    image_parser.add_argument("--document-id", required=True, help="Registered writer document_id (.docx).")
    image_parser.add_argument("--image", required=True, help="Picture file: png, jpg, jpeg, gif or bmp.")
    image_place = image_parser.add_mutually_exclusive_group(required=True)
    image_place.add_argument("--at-paragraph", type=int, help="Insert after body paragraph N (1-based).")
    image_place.add_argument("--after-text", help="Insert after the first body paragraph containing this text.")
    image_place.add_argument("--at-end", action="store_true", help="Insert at the end of the document.")
    image_parser.add_argument(
        "--width-mm",
        type=float,
        help="Width in mm, height kept in proportion; default the picture's own, at most the text width.",
    )
    image_parser.add_argument(
        "--caption", help="Caption paragraph below the picture (宋体 五号, centred); numbering is yours."
    )
    image_parser.add_argument("--dry-run", action="store_true", help="Report the position and size without writing.")
    image_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

    page_parser = subparsers.add_parser(
        "writer-page-setup", help="Set paper, orientation and margins of every section, with backup and read-back."
    )
    page_parser.add_argument("--document-id", required=True, help="Registered writer document_id (.docx).")
    page_parser.add_argument("--paper", choices=["A4", "A3", "A5", "Letter", "Legal", "16K"], help="Paper size.")
    page_parser.add_argument("--orientation", choices=["portrait", "landscape"], help="Page orientation.")
    for side in ("top", "bottom", "left", "right"):
        page_parser.add_argument(f"--margin-{side}-mm", type=float, help=f"{side.capitalize()} margin in mm.")
    page_parser.add_argument(
        "--dry-run", action="store_true", help="Report the current and new values without writing."
    )
    page_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

    style_parser = subparsers.add_parser(
        "writer-style-apply",
        help="Apply the gongwen (GB/T 9704) or report preset: fonts, sizes, spacing, indents, paper, margins, page numbers.",
    )
    style_parser.add_argument("--document-id", required=True, help="Registered writer document_id (.docx).")
    style_parser.add_argument("--preset", required=True, choices=["gongwen", "report"], help="Style preset.")
    style_parser.add_argument(
        "--font-map",
        action="append",
        help="Use an installed font instead of a missing one: 方正小标宋简体=宋体 (repeat).",
    )
    style_parser.add_argument(
        "--allow-missing-fonts",
        action="store_true",
        help="Keep the preset's font names even when they are not installed.",
    )
    style_parser.add_argument("--dry-run", action="store_true", help="Report the roles found and the fonts needed.")
    style_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

    bookmark_fill_parser = subparsers.add_parser(
        "writer-fill-bookmark",
        help="Fill a unique supported body or direct table-cell bookmark with backup and read-back validation.",
    )
    bookmark_fill_parser.add_argument("--document-id", required=True, help="Registered writer document_id.")
    bookmark_fill_parser.add_argument(
        "--bookmark-name", required=True, help="Unique, non-reserved supported bookmark name."
    )
    bookmark_fill_parser.add_argument("--text", required=True, help="Text to write into the bookmark range.")
    bookmark_fill_parser.add_argument(
        "--dry-run", action="store_true", help="Preview the bookmark target without modifying the file."
    )
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
    writer_table_parser.add_argument(
        "--dry-run", action="store_true", help="Preview target cell without modifying the file."
    )
    writer_table_parser.add_argument(
        "--allow-rich-content",
        action="store_true",
        help="Allow replacing a cell that contains drawings, fields, hyperlinks, nested tables, or content controls (those contents are discarded).",
    )
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

    presentation_selection_read_parser = subparsers.add_parser(
        "presentation-selection-read",
        help="Read the current selection of a registered Presentation that is open in a running WPS instance.",
    )
    presentation_selection_read_parser.add_argument(
        "--document-id",
        required=True,
        help="Registered presentation document_id.",
    )

    spreadsheet_selection_read_parser = subparsers.add_parser(
        "spreadsheet-selection-read",
        help="Read the current selection of a registered Spreadsheet that is open in a running WPS instance, including best-effort chart/shape object metadata for non-range selections.",
    )
    spreadsheet_selection_read_parser.add_argument(
        "--document-id",
        required=True,
        help="Registered spreadsheet document_id.",
    )

    spreadsheet_selection_replace_parser = subparsers.add_parser(
        "spreadsheet-selection-replace",
        help="Replace the current cell/range/multi-area selection of an open, saved Spreadsheet with a constant or per-cell matrix, with backup and read-back validation.",
    )
    spreadsheet_selection_replace_parser.add_argument(
        "--document-id",
        required=True,
        help="Registered spreadsheet document_id.",
    )
    spreadsheet_selection_replace_parser.add_argument(
        "--text",
        help="Constant replacement text written to every selected cell, including multi-area (single line, at most 4096 characters). Mutually exclusive with --values-json.",
    )
    spreadsheet_selection_replace_parser.add_argument(
        "--values-json",
        help=(
            "Rectangular JSON matrix of cell values. Single-area: shape must match rows×columns. "
            'Multi-area: row-major flatten onto Areas→Cells order (for example [["a","b"]] for two singleton areas). '
            "Mutually exclusive with --text."
        ),
    )
    spreadsheet_selection_replace_parser.add_argument(
        "--expected-selection-text",
        help="Refuse to write unless the current selection display text equals this value (multi-cell values are TAB-joined).",
    )
    spreadsheet_selection_replace_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the selection replacement without modifying the file.",
    )
    spreadsheet_selection_replace_parser.add_argument(
        "--task-id", help="Optional long-running task status id to update."
    )

    spreadsheet_selection_delete_parser = subparsers.add_parser(
        "spreadsheet-selection-delete",
        help="Clear the current cell/range/multi-area selection of an open, saved Spreadsheet with backup and read-back validation.",
    )
    spreadsheet_selection_delete_parser.add_argument(
        "--document-id",
        required=True,
        help="Registered spreadsheet document_id.",
    )
    spreadsheet_selection_delete_parser.add_argument(
        "--expected-selection-text",
        help="Refuse to clear unless the current selection display text equals this value (multi-cell values are TAB-joined).",
    )
    spreadsheet_selection_delete_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the selection deletion without modifying the file.",
    )
    spreadsheet_selection_delete_parser.add_argument(
        "--task-id", help="Optional long-running task status id to update."
    )
    spreadsheet_selection_delete_parser.add_argument(
        "--confirm",
        action="store_true",
        help="Acknowledge this destructive command (the MCP server requires it when not --dry-run; a person typing the command confirms by running it).",
    )

    presentation_selection_replace_parser = subparsers.add_parser(
        "presentation-selection-replace",
        help="Replace the current text selection of an open, saved Presentation with backup and read-back validation.",
    )
    presentation_selection_replace_parser.add_argument(
        "--document-id",
        required=True,
        help="Registered presentation document_id.",
    )
    presentation_selection_replace_parser.add_argument(
        "--text",
        required=True,
        help="Replacement text (single line, at most 4096 characters).",
    )
    presentation_selection_replace_parser.add_argument(
        "--expected-selection-text",
        help="Refuse to write unless the current selection text equals this value.",
    )
    presentation_selection_replace_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the selection replacement without modifying the file.",
    )
    presentation_selection_replace_parser.add_argument(
        "--task-id",
        help="Optional long-running task status id to update.",
    )

    presentation_selection_insert_parser = subparsers.add_parser(
        "presentation-selection-insert",
        help="Insert text at the collapsed text caret of an open, saved Presentation with backup and read-back validation.",
    )
    presentation_selection_insert_parser.add_argument(
        "--document-id",
        required=True,
        help="Registered presentation document_id.",
    )
    presentation_selection_insert_parser.add_argument(
        "--text",
        required=True,
        help="Text to insert (single line, at most 4096 characters, nonempty).",
    )
    presentation_selection_insert_parser.add_argument(
        "--expected-start",
        type=int,
        help="Refuse to write unless the text caret Start offset equals this value (1-based).",
    )
    presentation_selection_insert_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the caret insert without modifying the file.",
    )
    presentation_selection_insert_parser.add_argument(
        "--task-id",
        help="Optional long-running task status id to update.",
    )

    presentation_selection_delete_parser = subparsers.add_parser(
        "presentation-selection-delete",
        help="Delete the current text selection of an open, saved Presentation with backup and read-back validation.",
    )
    presentation_selection_delete_parser.add_argument(
        "--document-id",
        required=True,
        help="Registered presentation document_id.",
    )
    presentation_selection_delete_parser.add_argument(
        "--expected-selection-text",
        help="Refuse to delete unless the current selection text equals this value.",
    )
    presentation_selection_delete_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the selection deletion without modifying the file.",
    )
    presentation_selection_delete_parser.add_argument(
        "--task-id",
        help="Optional long-running task status id to update.",
    )
    presentation_selection_delete_parser.add_argument(
        "--confirm",
        action="store_true",
        help="Acknowledge this destructive command (the MCP server requires it when not --dry-run; a person typing the command confirms by running it).",
    )

    selection_replace_parser = subparsers.add_parser(
        "writer-selection-replace",
        help="Replace the current selection text of an open, saved Writer document with backup and read-back validation.",
    )
    selection_replace_parser.add_argument("--document-id", required=True, help="Registered writer document_id.")
    selection_replace_parser.add_argument(
        "--text", required=True, help="Replacement text (single line, at most 4096 characters)."
    )
    selection_replace_parser.add_argument(
        "--expected-selection-text", help="Refuse to write unless the current selection text equals this value."
    )
    selection_replace_parser.add_argument(
        "--dry-run", action="store_true", help="Preview the selection replacement without modifying the file."
    )
    selection_replace_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

    selection_insert_parser = subparsers.add_parser(
        "writer-selection-insert",
        help="Insert text at the collapsed caret of an open, saved Writer document with backup and read-back validation.",
    )
    selection_insert_parser.add_argument("--document-id", required=True, help="Registered writer document_id.")
    selection_insert_parser.add_argument(
        "--text", required=True, help="Text to insert (single line, at most 4096 characters, nonempty)."
    )
    selection_insert_parser.add_argument(
        "--expected-start",
        type=int,
        help="Refuse to write unless the caret start offset equals this value.",
    )
    selection_insert_parser.add_argument(
        "--dry-run", action="store_true", help="Preview the caret insert without modifying the file."
    )
    selection_insert_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

    selection_delete_parser = subparsers.add_parser(
        "writer-selection-delete",
        help="Delete the current selection text of an open, saved Writer document with backup and read-back validation.",
    )
    selection_delete_parser.add_argument("--document-id", required=True, help="Registered writer document_id.")
    selection_delete_parser.add_argument(
        "--expected-selection-text", help="Refuse to delete unless the current selection text equals this value."
    )
    selection_delete_parser.add_argument(
        "--dry-run", action="store_true", help="Preview the selection deletion without modifying the file."
    )
    selection_delete_parser.add_argument("--task-id", help="Optional long-running task status id to update.")
    selection_delete_parser.add_argument(
        "--confirm",
        action="store_true",
        help="Acknowledge this destructive command (the MCP server requires it when not --dry-run; a person typing the command confirms by running it).",
    )

    save_open_parser = subparsers.add_parser(
        "save-open-document",
        help="Explicitly Save() a registered Writer, Presentation, or Spreadsheet document that is already open on a disk path, with backup when there are unsaved changes.",
    )
    save_open_parser.add_argument(
        "--document-id",
        required=True,
        help="Registered writer, presentation, or spreadsheet document_id.",
    )
    save_open_parser.add_argument(
        "--dry-run", action="store_true", help="Preview whether Save() would write the open document."
    )
    save_open_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

    save_as_open_parser = subparsers.add_parser(
        "save-as-open-document",
        help="SaveAs an untitled open Writer/Presentation/Spreadsheet document (no disk path yet) to a new native path, then register its document_id.",
    )
    save_as_open_parser.add_argument(
        "--component",
        required=True,
        choices=["writer", "spreadsheets", "presentation"],
        help="WPS component hosting the untitled document.",
    )
    save_as_open_parser.add_argument(
        "--name",
        required=True,
        help="Exact open-document Name from open-documents (for example Document1).",
    )
    save_as_open_parser.add_argument(
        "--output",
        required=True,
        help="New native path (.docx / .xlsx / .pptx); existing files are never overwritten.",
    )
    save_as_open_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview whether SaveAs would write the untitled document to --output.",
    )
    save_as_open_parser.add_argument("--task-id", help="Optional long-running task status id to update.")
    save_as_open_parser.add_argument(
        "--confirm",
        action="store_true",
        help="Acknowledge this destructive command (the MCP server requires it when not --dry-run; a person typing the command confirms by running it).",
    )

    export_open_parser = subparsers.add_parser(
        "export-open-document",
        help="Export an open, saved Writer, Presentation, or Spreadsheet document to HTML without closing it or changing the source.",
    )
    export_open_parser.add_argument(
        "--document-id",
        required=True,
        help="Registered writer, presentation, or spreadsheet document_id.",
    )
    export_open_parser.add_argument(
        "--output", required=True, help="New .html or .htm output path; existing files are never overwritten."
    )

    export_open_pdf_parser = subparsers.add_parser(
        "export-open-document-pdf",
        help="Export an open, saved Writer, Presentation, or Spreadsheet document to PDF without closing it or changing the source.",
    )
    export_open_pdf_parser.add_argument(
        "--document-id",
        required=True,
        help="Registered writer, presentation, or spreadsheet document_id.",
    )
    export_open_pdf_parser.add_argument(
        "--output", required=True, help="New .pdf output path; existing files are never overwritten."
    )

    export_open_copy_parser = subparsers.add_parser(
        "export-open-document-copy",
        help="Save a same-format native copy of an open, saved Writer, Presentation, or Spreadsheet document without closing or renaming the source.",
    )
    export_open_copy_parser.add_argument(
        "--document-id",
        required=True,
        help="Registered writer, presentation, or spreadsheet document_id.",
    )
    export_open_copy_parser.add_argument(
        "--output",
        required=True,
        help="New output path with the same extension as the source; existing files are never overwritten.",
    )

    export_open_text_parser = subparsers.add_parser(
        "export-open-document-text",
        help="Export an open, saved Writer, Presentation, or Spreadsheet document to plain text without closing it or changing the source.",
    )
    export_open_text_parser.add_argument(
        "--document-id",
        required=True,
        help="Registered writer, presentation, or spreadsheet document_id.",
    )
    export_open_text_parser.add_argument(
        "--output", required=True, help="New .txt output path; existing files are never overwritten."
    )

    validate_parser = subparsers.add_parser(
        "validate-document",
        help=(
            "Check one expected value in a registered document: --contains for Writer, --cell and --equals for "
            "Spreadsheets. Use snapshot-document to read a document."
        ),
    )
    validate_parser.add_argument("--document-id", required=True, help="Registered document_id.")
    validate_parser.add_argument(
        "--contains", help="Writer: required. Text that must appear in the body, matched within one paragraph."
    )
    validate_parser.add_argument("--cell", help="Spreadsheets: required with --equals. One A1 cell on the first sheet.")
    validate_parser.add_argument("--equals", help="Spreadsheets: required with --cell. The value the cell must hold.")

    snapshot_parser = subparsers.add_parser(
        "snapshot-document",
        help="Return a structural validation snapshot for a registered document.",
    )
    snapshot_parser.add_argument("--document-id", required=True, help="Registered document_id.")

    writer_structure_parser = subparsers.add_parser(
        "writer-structure",
        help="Inspect bounded Writer headings, styles, and bookmarks from OOXML.",
    )
    writer_structure_parser.add_argument("--document-id", required=True, help="Registered Writer document_id.")
    writer_structure_parser.add_argument(
        "--limit", type=int, default=50, help="Maximum items per section, from 1 to 200."
    )
    writer_structure_parser.add_argument(
        "--section",
        choices=["all", "headings", "styles", "bookmarks", "warnings"],
        default="all",
        help="Structure list to inspect.",
    )
    writer_structure_parser.add_argument(
        "--offset", type=int, default=0, help="Zero-based offset for a selected section."
    )
    writer_structure_parser.add_argument("--bookmark-name", help="Exact bookmark name; requires --section bookmarks.")
    writer_structure_parser.add_argument("--expected-sha256", help="Require the DOCX hash from the preceding page.")
    writer_structure_parser.add_argument(
        "--include-text", action="store_true", help="Read bounded text from a unique supported bookmark."
    )
    writer_structure_parser.add_argument(
        "--text-limit", type=int, default=200, help="Maximum returned bookmark text characters, from 1 to 4096."
    )

    writer_parity_parser = subparsers.add_parser(
        "writer-structure-parity",
        help="Compare a controlled Writer fixture with read-only WPS desktop observations.",
    )
    writer_parity_parser.add_argument(
        "--run-wps", action="store_true", help="Explicitly launch WPS Writer for this local audit."
    )
    writer_parity_parser.add_argument(
        "--timeout-seconds", type=int, default=90, help="WPS audit timeout, from 1 to 300 seconds."
    )
    writer_parity_parser.add_argument(
        "--scope", choices=["structure", "nested"], default="structure", help="Controlled Writer fixture to compare."
    )
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
    task_status_create_parser.add_argument(
        "--operation-request-id", required=True, help="Request id for the tracked operation."
    )
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
        type=_mcp_config_audit_server_name,
        default="wps-ai-agent-cli",
        help="Server key under mcpServers (1-256 non-whitespace characters).",
    )
    mcp_config_audit_parser.add_argument(
        "--expected-min-tools",
        type=_mcp_config_audit_expected_tools,
        default=33,
        help="Minimum expected tools (1-10000).",
    )
    mcp_config_audit_parser.add_argument(
        "--timeout-seconds",
        type=_mcp_config_audit_timeout,
        default=15,
        help="Timeout for configured tools/list smoke (1-120 seconds).",
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
    regression_manifest_parser.add_argument(
        "--profile", help="Optional scenario profile filter, for example safe or wps."
    )
    regression_manifest_parser.add_argument(
        "--include-wps", action="store_true", help="Include scenarios that require WPS."
    )

    regression_run_parser = subparsers.add_parser(
        "regression-run",
        help="Run regression scenarios from the manifest.",
    )
    regression_run_parser.add_argument(
        "--manifest",
        default="config/regression_manifest.json",
        help="Path to regression manifest JSON.",
    )
    regression_run_parser.add_argument(
        "--profile", help="Optional scenario profile filter. Defaults to manifest default_profile."
    )
    regression_run_parser.add_argument("--include-wps", action="store_true", help="Include scenarios that require WPS.")
    regression_run_parser.add_argument(
        "--artifact-dir",
        help="Optional directory where a timestamped regression-run JSON artifact will be written.",
    )

    subparsers.add_parser(
        "security-audit",
        help="Audit mutating CLI and MCP tool safety boundaries.",
    )

    performance_parser = subparsers.add_parser(
        "performance-baseline",
        help="Capture runtime and output-size baselines for safe read-only commands.",
    )
    performance_parser.add_argument(
        "--include-wps",
        action="store_true",
        help="Also time real WPS writes on a temporary workbook and new CLI processes (T-09, the C-10 evidence).",
    )
    performance_parser.add_argument(
        "--repeat", type=int, default=3, help="WPS calls and process starts to time with --include-wps (1-10)."
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
    spreadsheet_rename_parser.add_argument(
        "--dry-run", action="store_true", help="Validate and preview without backup or WPS."
    )
    spreadsheet_rename_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

    spreadsheet_create_parser = subparsers.add_parser(
        "spreadsheet-create-sheet",
        help="Create a worksheet with backup and ordered read-back validation.",
    )
    spreadsheet_create_parser.add_argument("--document-id", required=True, help="Registered spreadsheet document_id.")
    spreadsheet_create_parser.add_argument("--name", required=True, help="New worksheet name.")
    spreadsheet_create_parser.add_argument("--index", type=int, help="1-based insertion index; defaults to the end.")
    spreadsheet_create_parser.add_argument(
        "--dry-run", action="store_true", help="Validate and preview without backup or WPS."
    )
    spreadsheet_create_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

    spreadsheet_visibility_parser = subparsers.add_parser(
        "spreadsheet-set-sheet-visibility",
        help="Set worksheet visibility with backup and ordered state read-back.",
    )
    spreadsheet_visibility_parser.add_argument(
        "--document-id", required=True, help="Registered spreadsheet document_id."
    )
    spreadsheet_visibility_parser.add_argument("--sheet-name", required=True, help="Worksheet to show or hide.")
    spreadsheet_visibility_parser.add_argument(
        "--visible", required=True, choices=("true", "false"), help="Set worksheet visible or hidden."
    )
    spreadsheet_visibility_parser.add_argument(
        "--dry-run", action="store_true", help="Validate and preview without backup or WPS."
    )
    spreadsheet_visibility_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

    spreadsheet_delete_parser = subparsers.add_parser(
        "spreadsheet-delete-sheet", help="Delete a worksheet with backup and ordered read-back validation."
    )
    spreadsheet_delete_parser.add_argument("--document-id", required=True, help="Registered spreadsheet document_id.")
    spreadsheet_delete_parser.add_argument("--sheet-name", required=True, help="Worksheet to delete.")
    spreadsheet_delete_parser.add_argument(
        "--dry-run", action="store_true", help="Validate and preview without backup or WPS."
    )
    spreadsheet_delete_parser.add_argument("--task-id", help="Optional long-running task status id to update.")
    spreadsheet_delete_parser.add_argument(
        "--confirm",
        action="store_true",
        help="Acknowledge this destructive command (the MCP server requires it when not --dry-run; a person typing the command confirms by running it).",
    )

    spreadsheet_copy_parser = subparsers.add_parser(
        "spreadsheet-copy-sheet", help="Copy a worksheet with backup and ordered read-back validation."
    )
    spreadsheet_copy_parser.add_argument("--document-id", required=True, help="Registered spreadsheet document_id.")
    spreadsheet_copy_parser.add_argument("--source-name", required=True, help="Worksheet to copy.")
    spreadsheet_copy_parser.add_argument("--new-name", required=True, help="Name for the copied worksheet.")
    spreadsheet_copy_parser.add_argument("--index", type=int, help="1-based insertion index; defaults to the end.")
    spreadsheet_copy_parser.add_argument(
        "--dry-run", action="store_true", help="Validate and preview without backup or WPS."
    )
    spreadsheet_copy_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

    spreadsheet_chart_parser = subparsers.add_parser(
        "spreadsheet-chart-create",
        help="Add a column, bar, line or pie chart of a range, with backup and read-back of the saved chart.",
    )
    spreadsheet_chart_parser.add_argument("--document-id", required=True, help="Registered spreadsheet document_id.")
    spreadsheet_chart_parser.add_argument("--sheet-name", required=True, help="Worksheet holding the data.")
    spreadsheet_chart_parser.add_argument(
        "--range", required=True, help="Data range with its labels, such as A1:C7 (first row/column as labels)."
    )
    spreadsheet_chart_parser.add_argument(
        "--chart-type", required=True, choices=["column", "bar", "line", "pie"], help="Chart type."
    )
    spreadsheet_chart_parser.add_argument("--title", help="Chart title.")
    spreadsheet_chart_parser.add_argument(
        "--anchor", help="Cell for the chart's top-left corner; one column right of the range by default."
    )
    spreadsheet_chart_parser.add_argument(
        "--series-in", choices=["auto", "rows", "columns"], default="auto", help="Where the series run (auto)."
    )
    spreadsheet_chart_parser.add_argument("--width", type=int, default=480, help="Width in points, 50-2000 (480).")
    spreadsheet_chart_parser.add_argument("--height", type=int, default=288, help="Height in points, 50-2000 (288).")
    spreadsheet_chart_parser.add_argument(
        "--dry-run", action="store_true", help="Validate and preview without backup or WPS."
    )
    spreadsheet_chart_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

    sort_parser = subparsers.add_parser(
        "spreadsheet-sort", help="Sort a range's rows by up to three columns, with backup and read-back."
    )
    sort_parser.add_argument("--document-id", required=True, help="Registered spreadsheet document_id.")
    sort_parser.add_argument("--sheet-name", required=True, help="Worksheet holding the range.")
    sort_parser.add_argument("--range", required=True, help="Range to sort, header row included, such as A1:D20.")
    sort_parser.add_argument(
        "--key",
        action="append",
        required=True,
        help="Sort key: column letter or header name, then :asc or :desc (B:desc, 销量:asc); repeat up to three times.",
    )
    sort_parser.add_argument("--no-header", action="store_true", help="The first row is data, not a header.")
    sort_parser.add_argument("--dry-run", action="store_true", help="Validate and preview without backup or WPS.")
    sort_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

    format_parser = subparsers.add_parser(
        "spreadsheet-conditional-format",
        help="Add a conditional format (cell value, color scale, data bar, duplicates) to a range.",
    )
    format_parser.add_argument("--document-id", required=True, help="Registered spreadsheet document_id.")
    format_parser.add_argument("--sheet-name", required=True, help="Worksheet holding the range.")
    format_parser.add_argument("--range", required=True, help="Range to format, such as C2:C50.")
    format_parser.add_argument(
        "--kind", required=True, choices=["cell-value", "color-scale", "data-bar", "duplicates"], help="Rule kind."
    )
    format_parser.add_argument(
        "--operator",
        choices=[
            "between",
            "not-between",
            "equal",
            "not-equal",
            "greater",
            "less",
            "greater-or-equal",
            "less-or-equal",
        ],
        help="cell-value: how to compare.",
    )
    format_parser.add_argument("--value1", help="cell-value: a number, text, or a formula starting with =.")
    format_parser.add_argument("--value2", help="cell-value: the upper bound for between and not-between.")
    format_parser.add_argument("--fill-color", default="#FFC7CE", help="cell-value/duplicates fill, #RRGGBB.")
    format_parser.add_argument("--font-color", default="#9C0006", help="cell-value/duplicates font colour, #RRGGBB.")
    format_parser.add_argument("--color-scale-points", type=int, default=3, help="color-scale: 2 or 3 colours.")
    format_parser.add_argument("--replace", action="store_true", help="Delete the range's existing rules first.")
    format_parser.add_argument("--dry-run", action="store_true", help="Validate and preview without backup or WPS.")
    format_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

    validation_parser = subparsers.add_parser(
        "spreadsheet-data-validation",
        help="Set the data validation of a range (a drop-down list, number, date or text-length limits).",
    )
    validation_parser.add_argument("--document-id", required=True, help="Registered spreadsheet document_id.")
    validation_parser.add_argument("--sheet-name", required=True, help="Worksheet holding the range.")
    validation_parser.add_argument("--range", required=True, help="Range to validate, such as D2:D100.")
    validation_parser.add_argument(
        "--type", required=True, choices=["list", "whole", "decimal", "date", "text-length"], help="What is allowed."
    )
    validation_parser.add_argument(
        "--value", action="append", help="list: one choice per --value, or a single =range such as =$H$1:$H$5."
    )
    validation_parser.add_argument(
        "--operator",
        choices=[
            "between",
            "not-between",
            "equal",
            "not-equal",
            "greater",
            "less",
            "greater-or-equal",
            "less-or-equal",
        ],
        help="Other types: how to compare (between).",
    )
    validation_parser.add_argument("--value1", help="Other types: a number, a date YYYY-MM-DD, or a formula.")
    validation_parser.add_argument("--value2", help="Other types: the upper bound for between and not-between.")
    validation_parser.add_argument("--no-blank", action="store_true", help="Do not allow empty cells.")
    validation_parser.add_argument("--input-message", help="Message shown when a cell is selected.")
    validation_parser.add_argument("--error-message", help="Message shown when a value is refused.")
    validation_parser.add_argument("--dry-run", action="store_true", help="Validate and preview without backup or WPS.")
    validation_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

    spreadsheet_tab_color_parser = subparsers.add_parser(
        "spreadsheet-set-sheet-tab-color", help="Set worksheet tab color with backup and read-back validation."
    )
    spreadsheet_tab_color_parser.add_argument(
        "--document-id", required=True, help="Registered spreadsheet document_id."
    )
    spreadsheet_tab_color_parser.add_argument(
        "--sheet-name", required=True, help="Worksheet whose tab color will change."
    )
    spreadsheet_tab_color_parser.add_argument(
        "--color", required=True, help="Hex color in #RRGGBB form, or 'none' to clear it."
    )
    spreadsheet_tab_color_parser.add_argument(
        "--dry-run", action="store_true", help="Validate and preview without backup or WPS."
    )
    spreadsheet_tab_color_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

    spreadsheet_inspect_parser = subparsers.add_parser(
        "spreadsheet-inspect",
        help="Inspect formulas, saved cached values, recalculated values, and WPS display text without saving.",
    )
    spreadsheet_inspect_parser.add_argument("--document-id", required=True, help="Registered spreadsheet document_id.")
    spreadsheet_inspect_parser.add_argument(
        "--range", required=True, help="Finite A1 range to inspect, for example A1:D6."
    )
    spreadsheet_inspect_parser.add_argument("--sheet", help="Optional sheet name. Defaults to first sheet.")

    spreadsheet_write_parser = subparsers.add_parser(
        "spreadsheet-write",
        help="Write a JSON matrix to an A1 range in a registered spreadsheet document.",
    )
    spreadsheet_write_parser.add_argument("--document-id", required=True, help="Registered spreadsheet document_id.")
    spreadsheet_write_parser.add_argument("--range", required=True, help="A1 range to write, for example A1:B2.")
    spreadsheet_write_parser.add_argument(
        "--values-json", required=True, help="Rectangular JSON matrix, for example [[1,2],[3,4]]."
    )
    spreadsheet_write_parser.add_argument("--sheet", help="Optional sheet name. Defaults to first sheet.")
    spreadsheet_write_parser.add_argument(
        "--dry-run", action="store_true", help="Preview write shape without modifying the file."
    )
    spreadsheet_write_parser.add_argument("--task-id", help="Optional long-running task status id to update.")

    spreadsheet_formula_parser = subparsers.add_parser(
        "spreadsheet-formula-write",
        help="Write formulas to an A1 range, recalculate with WPS, and validate cached values.",
    )
    spreadsheet_formula_parser.add_argument("--document-id", required=True, help="Registered spreadsheet document_id.")
    spreadsheet_formula_parser.add_argument("--range", required=True, help="A1 range to write, for example D4:D6.")
    spreadsheet_formula_parser.add_argument(
        "--formulas-json", required=True, help='Rectangular JSON matrix of formulas, for example [["=A1+B1"]].'
    )
    spreadsheet_formula_parser.add_argument(
        "--expected-values-json", required=True, help="Rectangular JSON matrix of expected cached values."
    )
    spreadsheet_formula_parser.add_argument("--sheet", help="Optional sheet name. Defaults to first sheet.")
    spreadsheet_formula_parser.add_argument(
        "--dry-run", action="store_true", help="Preview formula write shape without modifying the file."
    )
    spreadsheet_formula_parser.add_argument("--task-id", help="Optional long-running task status id to update.")


def _add_presentation_commands(subparsers: argparse._SubParsersAction) -> None:
    presentation_replace_parser = subparsers.add_parser(
        "presentation-replace",
        help="Replace text in a registered presentation with backup, validation, and idempotency.",
    )
    presentation_replace_parser.add_argument(
        "--document-id", required=True, help="Registered presentation document_id."
    )
    presentation_replace_parser.add_argument("--find", required=True, help="Text to find.")
    presentation_replace_parser.add_argument("--replace", required=True, help="Replacement text.")
    presentation_replace_parser.add_argument(
        "--dry-run", action="store_true", help="Preview matches without modifying the file."
    )
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
    parser.epilog = (
        "Exit status is 1 when the response has ok=false (0 on success, 2 for argument errors). "
        "Add --lenient-exit anywhere to exit 0 on failure instead, as versions before 0.12 did."
    )
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
