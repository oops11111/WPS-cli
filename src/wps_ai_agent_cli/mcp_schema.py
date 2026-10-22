from __future__ import annotations

from typing import Any

from .mcp_config_audit import (
    MCP_CONFIG_AUDIT_MAX_EXPECTED_TOOLS,
    MCP_CONFIG_AUDIT_MAX_SERVER_NAME_CHARS,
    MCP_CONFIG_AUDIT_MIN_EXPECTED_TOOLS,
    MCP_CONFIG_AUDIT_TIMEOUT_MAX_SECONDS,
    MCP_CONFIG_AUDIT_TIMEOUT_MIN_SECONDS,
)

SCHEMA_VERSION = "draft-2026-10-03"

MCP_TOOL_RESULT_OUTPUT_CONTRACT: dict[str, Any] = {
    "type": "object",
    "description": "The structuredContent envelope returned by tools/call.",
    "required": ["mcp_call", "errors"],
    "properties": {
        "mcp_call": {
            "type": "object",
            "description": "Adapter call metadata and the underlying CLI CommandResponse, when available.",
        },
        "errors": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["code", "message"],
                "properties": {"code": {"type": "string"}, "message": {"type": "string"}},
            },
        },
    },
    "additionalProperties": False,
}


def _string(description: str, enum: list[str] | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "string", "description": description}
    if enum:
        schema["enum"] = enum
    return schema


def _integer(description: str, minimum: int | None = None, maximum: int | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "integer", "description": description}
    if minimum is not None:
        schema["minimum"] = minimum
    if maximum is not None:
        schema["maximum"] = maximum
    return schema


def _boolean(description: str) -> dict[str, Any]:
    return {"type": "boolean", "description": description}


def _array(description: str) -> dict[str, Any]:
    return {"type": "array", "description": description, "items": {"type": "string"}}


def _object_schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    merged = {
        "request_id": _string("Optional stable idempotency key for the CLI request."),
        **properties,
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": required or [],
        "properties": merged,
    }


def _tool(
    name: str,
    cli_command: str,
    title: str,
    description: str,
    category: str,
    required: list[str] | None = None,
    properties: dict[str, Any] | None = None,
    mutates_document: bool = False,
    requires_wps: bool = False,
    idempotency: str = "Optional request_id is accepted for traceability.",
    cli_example: str | None = None,
    safety_notes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "name": name,
        "cli_command": cli_command,
        "title": title,
        "description": description,
        "category": category,
        "mutates_document": mutates_document,
        "requires_wps": requires_wps,
        "idempotency": idempotency,
        "input_schema": _object_schema(properties or {}, required),
        "output_contract": MCP_TOOL_RESULT_OUTPUT_CONTRACT,
        "cli_example": cli_example or f"python -m wps_ai_agent_cli {cli_command}",
        "safety_notes": safety_notes or [],
    }


MCP_TOOL_SCHEMAS: tuple[dict[str, Any], ...] = (
    _tool(
        "wps_agent_inspect_env",
        "inspect-env",
        "Inspect WPS environment",
        "Inspect OS, pywin32 availability, and WPS COM ProgID registration.",
        "environment",
    ),
    _tool(
        "wps_agent_wps_version_compare",
        "wps-version-compare",
        "Compare persisted WPS versions",
        "Compare observed Writer, Spreadsheets, and Presentation version strings with the workspace baseline. Does not launch WPS or modify documents.",
        "environment",
        properties={
            "workspace": _string("Workspace whose .wps-agent/wps-versions.json stores the baseline."),
            "record": _boolean("Persist parsable observed versions without launching WPS or modifying documents."),
            "writer_version": _string("Observed Writer version, for example 12.8.2.18913."),
            "spreadsheets_version": _string("Observed Spreadsheets version."),
            "presentation_version": _string("Observed Presentation version."),
        },
        cli_example="python -m wps_ai_agent_cli wps-version-compare --writer-version 12.0 --record",
        safety_notes=[
            "This tool never launches WPS and never edits a document.",
            "Recording writes only .wps-agent/wps-versions.json in the selected workspace.",
        ],
    ),
    _tool(
        "wps_agent_wps_process_audit",
        "wps-process-audit",
        "Audit WPS processes",
        "List WPS-related processes and safe cleanup guidance without terminating anything.",
        "environment",
        properties={
            "timeout_seconds": _integer("Timeout for process inspection.", minimum=1),
        },
        cli_example="python -m wps_ai_agent_cli wps-process-audit",
    ),
    _tool(
        "wps_agent_cleanup_plan",
        "cleanup-plan",
        "Build cleanup plan",
        "Build a read-only local cleanup plan with approval-required candidates.",
        "maintenance",
        properties={
            "workspace": _string("Workspace root to inspect. Defaults to the current directory."),
        },
        cli_example="python -m wps_ai_agent_cli cleanup-plan",
        safety_notes=[
            "This tool is read-only and never deletes files.",
            "Every cleanup candidate requires explicit user approval before removal.",
        ],
    ),
    _tool(
        "wps_agent_cleanup_approval_manifest",
        "cleanup-approval-manifest",
        "Build cleanup approval manifest",
        "Build a read-only cleanup approval manifest grouped by category.",
        "maintenance",
        properties={
            "workspace": _string("Workspace root to inspect. Defaults to the current directory."),
        },
        cli_example="python -m wps_ai_agent_cli cleanup-approval-manifest",
        safety_notes=[
            "This tool is read-only and never deletes files.",
            "Use it to review exact cleanup categories before any separate approval-gated cleanup.",
        ],
    ),
    _tool(
        "wps_agent_plan",
        "plan",
        "Return roadmap",
        "Return the staged implementation roadmap.",
        "project",
    ),
    _tool(
        "wps_agent_tasks",
        "tasks",
        "List development tasks",
        "List staged development tasks with optional phase and status filters.",
        "project",
        properties={
            "phase": _string("Optional phase id such as phase0, phase1, or phase2."),
            "status": _string("Optional task status such as next or done."),
        },
        cli_example="python -m wps_ai_agent_cli tasks --phase phase2",
    ),
    _tool(
        "wps_agent_com_smoke",
        "com-smoke",
        "Run COM smoke test",
        "Open, save a copy, and close a WPS Writer, Spreadsheets, or Presentation file.",
        "smoke",
        required=["component", "input", "output"],
        properties={
            "component": _string("WPS component to exercise.", ["writer", "spreadsheets", "presentation"]),
            "input": _string("Input document path."),
            "output": _string("Output copy path."),
            "visible": _boolean("Show WPS during the smoke run."),
        },
        requires_wps=True,
        cli_example="python -m wps_ai_agent_cli com-smoke --component writer --input input.docx --output output.docx",
        safety_notes=[
            "Only one running WPS instance can be attached. When more than one WPS process of the component has a main window (in this user session) and the document is not already open in the attached instance, the command refuses and lists the pids and window titles; close the extra WPS windows, or set WPS_AGENT_ALLOW_MULTI_INSTANCE=1 to skip this check. Extra background processes without a window do not block the command; they add a warning to the result.",
            "Works in the running WPS instance when there is one. A document that is not open yet is opened there only for the duration of the command (its window may briefly appear) and closed again afterwards; a document that was already open is never closed.",
        ],
    ),
    _tool(
        "wps_agent_calc_smoke",
        "calc-smoke",
        "Run spreadsheet calculation smoke test",
        "Verify formula calculation through WPS Spreadsheets.",
        "smoke",
        required=["input", "output"],
        properties={
            "input": _string("Input workbook path."),
            "output": _string("Output workbook path."),
            "timeout_seconds": _integer("Timeout for the WPS spreadsheet COM smoke.", minimum=1),
        },
        requires_wps=True,
        safety_notes=[
            "Only one running WPS instance can be attached. When more than one WPS process of the component has a main window (in this user session) and the document is not already open in the attached instance, the command refuses and lists the pids and window titles; close the extra WPS windows, or set WPS_AGENT_ALLOW_MULTI_INSTANCE=1 to skip this check. Extra background processes without a window do not block the command; they add a warning to the result.",
            "Works in the running WPS instance when there is one. A document that is not open yet is opened there only for the duration of the command (its window may briefly appear) and closed again afterwards; a document that was already open is never closed.",
        ],
    ),
    _tool(
        "wps_agent_convert_smoke",
        "convert-smoke",
        "Run conversion smoke test",
        "Convert a Writer, Spreadsheet, or Presentation file to PDF through WPS COM and report conversion evidence.",
        "smoke",
        required=["component", "input", "output", "format"],
        properties={
            "component": _string(
                "Component to convert.",
                ["writer", "spreadsheets", "presentation"],
            ),
            "input": _string("Input file path."),
            "output": _string("Output file path."),
            "format": _string("Output format.", ["pdf"]),
        },
        requires_wps=True,
        cli_example="python -m wps_ai_agent_cli convert-smoke --component spreadsheets --input book.xlsx --output book.pdf --format pdf",
        safety_notes=[
            "Only one running WPS instance can be attached. When more than one WPS process of the component has a main window (in this user session) and the document is not already open in the attached instance, the command refuses and lists the pids and window titles; close the extra WPS windows, or set WPS_AGENT_ALLOW_MULTI_INSTANCE=1 to skip this check. Extra background processes without a window do not block the command; they add a warning to the result.",
            "Attaches to a running WPS instance of the selected component first and launches one only when none is running, opens the input, writes a new PDF, then closes the document.",
            "Refuses an input that is already open in WPS, so a user's document is never closed or saved under another name.",
            "Never overwrites the input path; still prefer a disposable copy when validating on real desktop files.",
            "Quit runs only for an instance this command launched itself, and only when it has no remaining documents, workbooks, or presentations; an attached instance is never Quit().",
        ],
    ),
    _tool(
        "wps_agent_html_render",
        "html-render",
        "Render local HTML",
        "Render local HTML to PDF or PNG using headless Microsoft Edge with local-only resources and JavaScript disabled by default.",
        "conversion",
        required=["input", "output", "format"],
        properties={
            "input": _string("Local .html or .htm source path."),
            "output": _string("New .pdf or .png output path; existing files are never overwritten."),
            "format": _string("Rendered artifact format.", ["pdf", "png"]),
            "page_size": _string("PDF page size.", ["A4", "Letter", "Legal", "Tabloid"]),
            "viewport_width": _integer("Browser viewport width.", minimum=320, maximum=3840),
            "viewport_height": _integer("Browser viewport height.", minimum=240, maximum=2160),
            "timeout_seconds": _integer("Render timeout.", minimum=1, maximum=120),
            "allow_javascript": _boolean("Explicitly enable page scripts; network requests remain blocked."),
            "task_id": _string("Optional long-running task status id."),
        },
        mutates_document=True,
        idempotency="Optional request_id is accepted for traceability; creates a new artifact and refuses to overwrite an existing output path.",
        cli_example="python -m wps_ai_agent_cli html-render --input page.html --output page.pdf --format pdf",
        safety_notes=[
            "Only local resources under the input HTML directory are allowed; network and other protocols are blocked.",
            "JavaScript is disabled by default. When enabled, WebSocket connections are still aborted so network_access remains false.",
            "Render timeouts kill the Node process tree (including Edge children on Windows via taskkill /T).",
            "Input is limited to 10 MiB; individual resources to 20 MiB and total local resources to 100 MiB.",
            "Creates a new PDF or PNG and never modifies the source HTML or overwrites an existing output.",
        ],
    ),
    _tool(
        "wps_agent_html_editable",
        "html-editable",
        "Convert HTML to editable Office content",
        'Map semantic local HTML to editable DOCX (Writer paragraphs, headings, nested lists, tables with merged cells, bold/italic/underline/strike/sub/superscript, hyperlinks, local images and figure captions), XLSX (each table becomes a worksheet, with merged cells, numbers with their number format, dates and local images) or PPTX (each section or h1/h2 becomes a slide, with tables, local images and media, speaker notes from <aside class="notes">, CSS @keyframes animations as entrance effects and data-transition as slide transitions); report what could not be converted in warnings.',
        "conversion",
        required=["input", "output"],
        properties={
            "input": _string("Local .html or .htm source path."),
            "output": _string("New output path matching format; existing files are never overwritten."),
            "format": _string("Output format; defaults to docx.", enum=["docx", "xlsx", "pptx"]),
            "fidelity": _string(
                "editable (default) maps to native, editable objects styled from the computed CSS; appearance "
                "(pptx) places every element where the browser lays it out.",
                enum=["editable", "appearance"],
            ),
            "task_id": _string("Optional task status id."),
        },
        mutates_document=True,
        idempotency="Optional request_id is accepted for traceability; creates a new editable artifact and refuses to overwrite an existing output path.",
        cli_example="python -m wps_ai_agent_cli html-editable --input page.html --output page.docx --format docx",
        safety_notes=[
            "Creates a new DOCX, XLSX or PPTX artifact; source HTML is unchanged and existing outputs are never overwritten.",
            "Only local images under the HTML directory are embedded; remote images, scripts, and unsupported elements are omitted and reported.",
            "Semantic content is mapped to native editable Word objects; CSS layout is not preserved and is reported as unsupported fidelity.",
        ],
    ),
    _tool(
        "wps_agent_convert",
        "convert",
        "Convert between document formats",
        "Convert one file to another format chosen by the output extension: HTML to DOCX/XLSX/PPTX/PDF/PNG, "
        "DOCX/PPTX/XLSX to clean HTML or Markdown, Markdown to HTML/DOCX/PPTX, CSV/TSV to and from XLSX (GBK and "
        "UTF-8 detected), DOCX to PPTX (a slide per Heading 1/2) and back, a worksheet range to a DOCX or PPTX "
        "table, PDF to DOCX/XLSX/PPTX (headings, lists, tables; OCR for scanned pages), and the WPS (.wps/.et/"
        ".dps), legacy Office (.doc/.xls/.ppt), ODF, PDF and per-page PNG formats through WPS. Pairs without a "
        "direct route go through one intermediate file; the result lists the route and an output_summary (slide "
        "titles, headings, sheets). Write straight to the path the user asked for: the result is final, so check it "
        "with check (or fidelity-check) instead of converting to trial copies first.",
        "conversion",
        required=["input", "output"],
        properties={
            "input": _string("Source file path."),
            "output": _string(
                "New output path; its extension selects the format. Existing files are never overwritten."
            ),
            "fidelity": _string("HTML to Office mapping mode.", enum=["editable", "appearance"]),
            "ocr": _boolean("Read scanned PDF pages with OCR (needs the ocr optional dependency)."),
            "sheet": _string("Worksheet to read for xlsx to csv, docx or pptx; the first sheet by default."),
            "range": _string("Worksheet range for a table, such as A1:D20; the used range by default."),
            "images": _string(
                "HTML output images: embedded data URIs or a <name>_files folder.", enum=["embed", "files"]
            ),
            "encoding": _string("CSV/TSV encoding; detected when reading by default."),
            "delimiter": _string("CSV delimiter; detected when reading by default."),
            "dpi": _integer("PNG page image resolution.", minimum=36, maximum=600),
            "no_browser": _boolean("Use the built-in CSS cascade instead of the browser's computed styles."),
            "check": _boolean("Run fidelity-check (without layout) on the result and include its report."),
            "task_id": _string("Optional task status id."),
        },
        mutates_document=True,
        idempotency="Optional request_id is accepted for traceability; creates a new file and refuses to overwrite an existing output path.",
        cli_example="python -m wps_ai_agent_cli convert --input report.pdf --output report.docx",
        safety_notes=[
            "Creates a new artifact file (or per-page PNG artifacts); the source is never modified and existing "
            "outputs are never overwritten.",
            "WPS-format conversions open the source in a hidden WPS instance and save a copy; they need WPS on Windows.",
            "A pair WPS cannot write is refused with FORMAT_NOT_SUPPORTED_BY_WPS before WPS starts.",
            "A scanned PDF without --ocr is refused with PDF_NEEDS_OCR rather than producing an empty document.",
        ],
    ),
    _tool(
        "wps_agent_fidelity_check",
        "fidelity-check",
        "Check a conversion's fidelity",
        "Compare a converted file with its source and score text, structure (headings, lists, tables, images, "
        "slides), character formatting, animations, table data and rendered layout (SSIM per page, rendered by WPS "
        "on Windows or LibreOffice), against the Phase 13 thresholds for that kind of conversion.",
        "conversion",
        required=["source", "target"],
        properties={
            "source": _string("The original file."),
            "target": _string("The converted file."),
            "renderer": _string("Layout renderer.", enum=["auto", "wps", "libreoffice", "none"]),
            "no_layout": _boolean("Skip the rendered-page comparison."),
            "baseline": {"type": "number", "description": "Recorded LibreOffice layout score to compare against."},
            "no_browser": _boolean("Read HTML with the built-in cascade instead of the browser."),
        },
        mutates_document=False,
        idempotency="Read-only; repeated calls give the same scores for the same files and renderer.",
        cli_example="python -m wps_ai_agent_cli fidelity-check --source page.html --target page.docx",
        safety_notes=["Reads both files; layout rendering writes only temporary files that are removed."],
    ),
    _tool(
        "wps_agent_html_roundtrip_plan",
        "html-roundtrip-plan",
        "Validate controlled HTML round-trip identity",
        "Validate owned HTML schema v1 and return a deterministic read-only map from stable object IDs to native object types and indices.",
        "conversion",
        required=["input"],
        properties={
            "input": _string("Local owned HTML file using wps-agent-html/v1 and stable data-wps-object-id attributes.")
        },
        safety_notes=[
            "Read-only: does not modify HTML, create a DOCX, launch WPS, or fetch resources.",
            "Rejects missing/duplicate IDs, unsupported ID-bearing elements, CSS and executable content instead of silently losing identity.",
        ],
    ),
    _tool(
        "wps_agent_html_controlled_import",
        "html-controlled-import",
        "Import owned HTML with identity metadata",
        "Convert validated owned HTML into editable DOCX, preserve stable IDs as DOCX bookmarks, and write a mapping sidecar.",
        "conversion",
        required=["input", "output"],
        properties={
            "input": _string("Owned HTML v1 source."),
            "output": _string("New DOCX path; existing DOCX or mapping sidecar is never overwritten."),
            "task_id": _string("Optional task status id."),
        },
        mutates_document=True,
        idempotency="Optional request_id is accepted for traceability; refuses to overwrite either output artifact.",
        safety_notes=[
            "Source HTML is unchanged; creates a new DOCX and adjacent .wpsmap.json sidecar.",
            "Rejects invalid schema/IDs and fails closed if mapping metadata cannot be persisted.",
        ],
    ),
    _tool(
        "wps_agent_html_roundtrip_verify",
        "html-roundtrip-verify",
        "Verify controlled HTML object identity",
        "Read a DOCX and its mapping sidecar to detect missing, duplicate, or reordered mapped object bookmarks after edits.",
        "conversion",
        required=["docx", "mapping"],
        properties={
            "docx": _string("Edited DOCX path."),
            "mapping": _string("Adjacent .wpsmap.json identity sidecar path."),
        },
        safety_notes=["Read-only; does not modify the DOCX or mapping sidecar and does not launch WPS."],
    ),
    _tool(
        "wps_agent_html_roundtrip_export",
        "html-roundtrip-export",
        "Export controlled DOCX to owned HTML",
        "Serialize a verified controlled DOCX and identity sidecar back to owned HTML v1 while preserving stable object IDs.",
        "conversion",
        required=["docx", "mapping", "output"],
        properties={
            "docx": _string("Controlled DOCX path."),
            "mapping": _string("Identity sidecar path."),
            "output": _string("New .html/.htm output; existing files are never overwritten."),
            "task_id": _string("Optional task status id."),
        },
        mutates_document=True,
        idempotency="Optional request_id is accepted for traceability; refuses to overwrite an existing HTML output.",
        safety_notes=[
            "Creates a new HTML artifact only after all mapped identities verify; source DOCX and sidecar remain unchanged.",
            "Unsupported WordprocessingML elements or untracked content are rejected instead of silently dropped.",
        ],
    ),
    _tool(
        "wps_agent_html_batch_convert",
        "html-batch-convert",
        "Batch convert local HTML files",
        "Convert a bounded directory of local HTML files to PDF, PNG, or editable DOCX with per-file isolation and a SHA-256 provenance manifest.",
        "conversion",
        required=["input_dir", "output_dir", "mode"],
        properties={
            "input_dir": _string("Directory containing local .html/.htm files."),
            "output_dir": _string(
                "Output directory outside the input tree; new outputs and manifest are never overwritten."
            ),
            "mode": _string("Output format.", ["pdf", "png", "docx"]),
            "recursive": _boolean("Include nested directories."),
            "task_id": _string("Optional task status id for tracking the batch."),
        },
        mutates_document=True,
        idempotency="Optional request_id is accepted for traceability; refuses to overwrite existing outputs or the batch manifest.",
        safety_notes=[
            "Creates output artifacts only; source files are unchanged. Processes at most 100 HTML files and 500 MiB total input.",
            "Each file is reported independently, and failures do not stop subsequent files. Existing files are never overwritten.",
            "Runs locally without WPS; HTML rendering keeps JavaScript disabled and network isolation enabled by default.",
            "With task_id, progress is updated between files and task-status-update --state cancelled requests cooperative cancellation; completed results remain in the manifest.",
        ],
    ),
    _tool(
        "wps_agent_html_batch_request",
        "html-batch-request",
        "Inspect HTML batch request",
        "Return a recorded HTML batch request state, arguments, manifest path, and recovery guidance without changing files.",
        "batch",
        required=["batch_request_id"],
        properties={
            "batch_request_id": _string("Original batch conversion request_id to inspect."),
            "verify": _boolean("Verify current manifest and source/output hashes without modifying state."),
        },
        safety_notes=["Reads only local request records; does not render or mutate files."],
    ),
    _tool(
        "wps_agent_batch_template_report",
        "batch-template-report",
        "Render a batch report from a local template",
        "Validate a bounded HTML batch conversion manifest and render its summary and per-file provenance into a local Markdown/text or DOCX template.",
        "conversion",
        required=["manifest", "template", "output"],
        properties={
            "manifest": _string("Existing wps-agent-batch-conversion/v1 JSON manifest."),
            "template": _string("Existing local Markdown, text, or DOCX template with supported placeholders."),
            "output": _string(
                "New Markdown/text output for text templates, or .docx for DOCX templates; existing reports are never overwritten."
            ),
            "task_id": _string("Optional task status id for tracking report generation."),
        },
        mutates_document=True,
        idempotency="Optional request_id is accepted for traceability; refuses to overwrite an existing report.",
        safety_notes=[
            "Creates one local report artifact; the manifest and template are unchanged. Template expressions are never executed.",
            "Validates per-file source/output hashes and summary counts before rendering; unknown placeholders are rejected.",
            "Manifest, template, report size, and file count are bounded; output must be a new file.",
        ],
    ),
    _tool(
        "wps_agent_register_document",
        "register-document",
        "Register document",
        "Register a supported local file and return a stable document_id.",
        "documents",
        required=["component", "path"],
        properties={
            "component": _string("Document component.", ["writer", "spreadsheets", "presentation"]),
            "path": _string("Document path to register."),
        },
        cli_example="python -m wps_ai_agent_cli register-document --component writer --path input.docx",
    ),
    _tool(
        "wps_agent_documents",
        "documents",
        "List documents",
        "List registered documents and their current existence status.",
        "documents",
    ),
    _tool(
        "wps_agent_backup_document",
        "backup-document",
        "Create backup",
        "Create a recoverable backup for a registered document_id.",
        "safety",
        required=["document_id"],
        properties={
            "document_id": _string("Registered document_id."),
            "dry_run": _boolean("Preview the backup path without copying."),
            "task_id": _string("Optional long-running task status id."),
        },
        mutates_document=True,
        idempotency="Mutating command; request_id should be supplied and is replayed by the operation ledger.",
        safety_notes=[
            "Creates a filesystem backup under .wps-agent/backups; dry_run previews without copying.",
            "Use before document-changing commands when an explicit backup is needed.",
        ],
    ),
    _tool(
        "wps_agent_list_backups",
        "list-backups",
        "List backups",
        "List recoverable backups, optionally scoped to one document_id.",
        "safety",
        properties={"document_id": _string("Optional registered document_id.")},
    ),
    _tool(
        "wps_agent_restore_backup",
        "restore-backup",
        "Restore backup",
        "Restore a selected backup after first protecting the current file.",
        "safety",
        required=["document_id"],
        properties={
            "document_id": _string("Registered document_id."),
            "backup_name": _string("Backup filename from list-backups."),
            "backup_path": _string("Backup path from list-backups. With backup_name, both must name the same file."),
            "dry_run": _boolean("Preview restore without copying."),
            "close_in_wps": _boolean(
                "If the document is open in WPS with no unsaved changes, close it there without saving before restoring."
            ),
            "task_id": _string("Optional long-running task status id."),
        },
        mutates_document=True,
        idempotency="Mutating command; request_id should be supplied and is replayed by the operation ledger.",
        safety_notes=[
            "Restores a registered document from a backup and creates a pre-restore backup before overwriting.",
            "Provide backup_name or backup_path (both are accepted when they name the same file); dry_run previews without copying.",
            "close_in_wps closes the document in the running WPS without saving, and only when WPS reports no unsaved changes; with unsaved changes it refuses with DOCUMENT_HAS_UNSAVED_CHANGES and nothing is closed or restored. When WPS refuses the close and still lists the document, it returns WPS_CLOSE_REFUSED and nothing is restored: the user closes it in WPS, then the restore runs without close_in_wps. Without it, WPS is never touched. With dry_run it only reports whether it would close the document.",
        ],
    ),
    _tool(
        "wps_agent_writer_replace",
        "writer-replace",
        "Replace Writer text",
        "Replace body text in a registered WPS Writer document with backup, dry-run, and validation.",
        "writer",
        required=["document_id", "find", "replace"],
        properties={
            "document_id": _string("Registered writer document_id."),
            "find": _string("Text to find."),
            "replace": _string("Replacement text."),
            "dry_run": _boolean("Preview matches without modifying the file."),
            "paragraph_index": _integer("Optional 1-based paragraph index.", minimum=1),
            "task_id": _string("Optional long-running task status id."),
        },
        mutates_document=True,
        requires_wps=True,
        idempotency="Mutating command; request_id should be supplied and is replayed by the operation ledger.",
        safety_notes=[
            "Only one running WPS instance can be attached. When more than one WPS process of the component has a main window (in this user session) and the document is not already open in the attached instance, the command refuses and lists the pids and window titles; close the extra WPS windows, or set WPS_AGENT_ALLOW_MULTI_INSTANCE=1 to skip this check. Extra background processes without a window do not block the command; they add a warning to the result.",
            "Works in the running WPS instance when there is one. A document that is not open yet is opened there only for the duration of the command (its window may briefly appear) and closed again afterwards; a document that was already open is never closed.",
            "Uses WPS to mutate a registered Writer document and creates a backup before mutation.",
            "Use dry_run before mutation when possible.",
        ],
    ),
    _tool(
        "wps_agent_writer_fill_bookmark",
        "writer-fill-bookmark",
        "Fill Writer bookmark",
        "Fill a unique same-paragraph direct-body or direct table-cell bookmark with backup and exact read-back validation.",
        "writer",
        required=["document_id", "bookmark_name", "text"],
        properties={
            "document_id": _string("Registered writer document_id."),
            "bookmark_name": _string("Unique, non-reserved supported bookmark name."),
            "text": _string("Text to write into the bookmark range."),
            "dry_run": _boolean("Preview the bookmark target without modifying the file."),
            "task_id": _string("Optional long-running task status id."),
        },
        mutates_document=True,
        requires_wps=True,
        idempotency="Mutating command; request_id should be supplied and is replayed by the operation ledger.",
        safety_notes=[
            "Only one running WPS instance can be attached. When more than one WPS process of the component has a main window (in this user session) and the document is not already open in the attached instance, the command refuses and lists the pids and window titles; close the extra WPS windows, or set WPS_AGENT_ALLOW_MULTI_INSTANCE=1 to skip this check. Extra background processes without a window do not block the command; they add a warning to the result.",
            "Works in the running WPS instance when there is one. A document that is not open yet is opened there only for the duration of the command (its window may briefly appear) and closed again afterwards; a document that was already open is never closed.",
            "Uses WPS to fill a unique same-paragraph direct-body or direct table-cell bookmark and creates a backup before mutation.",
            "Rejects missing, ambiguous, cross-paragraph, nested-table, and header/footer write scopes; use dry_run to inspect the target.",
        ],
    ),
    _tool(
        "wps_agent_writer_table_write",
        "writer-table-write",
        "Write Writer table cell",
        "Write text to a table cell in a registered WPS Writer document with backup, dry-run, and validation. "
        "A dry run returns the cell's current text and the table's row count, column count and header row.",
        "writer",
        required=["document_id", "table_index", "row", "column", "text"],
        properties={
            "document_id": _string("Registered writer document_id."),
            "table_index": _integer("1-based table index.", minimum=1),
            "row": _integer("1-based row index.", minimum=1),
            "column": _integer("1-based column index.", minimum=1),
            "text": _string("Replacement cell text."),
            "dry_run": _boolean("Preview target cell without modifying the file."),
            "allow_rich_content": _boolean(
                "Allow replacing a cell that contains drawings, fields, hyperlinks, nested tables, or content controls; those contents are discarded."
            ),
            "task_id": _string("Optional long-running task status id."),
        },
        mutates_document=True,
        requires_wps=True,
        idempotency="Mutating command; request_id should be supplied and is replayed by the operation ledger.",
        safety_notes=[
            "Only one running WPS instance can be attached. When more than one WPS process of the component has a main window (in this user session) and the document is not already open in the attached instance, the command refuses and lists the pids and window titles; close the extra WPS windows, or set WPS_AGENT_ALLOW_MULTI_INSTANCE=1 to skip this check. Extra background processes without a window do not block the command; they add a warning to the result.",
            "Works in the running WPS instance when there is one. A document that is not open yet is opened there only for the duration of the command (its window may briefly appear) and closed again afterwards; a document that was already open is never closed.",
            "Uses WPS to mutate a registered Writer table cell and creates a backup before mutation.",
            "Use dry_run before mutation; table, row, and column are 1-based and validated before write.",
            "Cells with rich content are refused unless allow_rich_content is set; a text write discards that content.",
        ],
    ),
    _tool(
        "wps_agent_open_documents",
        "open-documents",
        "List open WPS documents",
        "Attach to already running WPS instances without launching WPS and list their open documents with saved state and stable document_id.",
        "documents",
        properties={
            "component": _string("Limit the probe to one component.", enum=["writer", "spreadsheets", "presentation"]),
            "register": _boolean("Register saved open documents so they receive a stable document_id."),
        },
        requires_wps=True,
        safety_notes=[
            "Read-only against WPS: never launches WPS and never closes or saves a running instance.",
            "Only register=true writes local state (registration); target documents by document_id, not the active window.",
        ],
    ),
    _tool(
        "wps_agent_save_open_document",
        "save-open-document",
        "Save open document",
        "Explicitly Save() a registered Writer, Presentation, or Spreadsheet document that is open on a disk path in a running WPS instance, with backup when there are unsaved changes.",
        "documents",
        required=["document_id"],
        properties={
            "document_id": _string("Registered writer, presentation, or spreadsheet document_id."),
            "dry_run": _boolean("Preview whether Save() would write the open document."),
            "task_id": _string("Optional long-running task status id."),
        },
        mutates_document=True,
        requires_wps=True,
        idempotency="Mutating command; request_id should be supplied and is replayed by the operation ledger.",
        safety_notes=[
            "Attaches only: never launches WPS and never Quit()s the attached instance.",
            "Requires a registered on-disk path; untitled documents without a path should use save-as-open-document instead. Read-only documents are refused before backup.",
            "When Saved is already true, no backup and no write occur. Dirty documents are backed up from the last saved file, then Save() is called. Other commands still refuse unsaved documents instead of saving implicitly.",
        ],
    ),
    _tool(
        "wps_agent_save_as_open_document",
        "save-as-open-document",
        "SaveAs untitled open document",
        "SaveAs an untitled open Writer, Presentation, or Spreadsheet document that has no disk path yet to a new native path, then register a stable document_id.",
        "documents",
        required=["component", "name", "output"],
        properties={
            "component": _string(
                "WPS component hosting the untitled document.",
                enum=["writer", "spreadsheets", "presentation"],
            ),
            "name": _string("Exact open-document Name from open-documents (for example Document1)."),
            "output": _string("New native path (.docx / .xlsx / .pptx); existing files are never overwritten."),
            "dry_run": _boolean("Preview whether SaveAs would write the untitled document."),
            "task_id": _string("Optional long-running task status id."),
        },
        mutates_document=True,
        requires_wps=True,
        idempotency="Mutating command; request_id should be supplied and is replayed by the operation ledger.",
        safety_notes=[
            "Attaches only: never launches WPS and never Quit()s the attached instance.",
            "Targets untitled documents by component+Name; ambiguous duplicate names and already-pathed documents are refused before write.",
            "No backup is created (untitled has no source file to back up). The only file written is the new --output path: it must not already exist, its parent directory must exist, and the extension must match the component (.docx/.xlsx/.pptx); existing files are never overwritten. After success the document is registered under a path-based document_id for later commands.",
        ],
    ),
    _tool(
        "wps_agent_writer_selection_read",
        "writer-selection-read",
        "Read Writer selection",
        "Read the current selection range, text, paragraph index and best-effort page number of a registered Writer document open in a running WPS instance.",
        "writer",
        required=["document_id"],
        properties={"document_id": _string("Registered writer document_id.")},
        requires_wps=True,
        safety_notes=[
            "Read-only: does not change the document or the selection.",
            "page_number is unverified; prefer selection, paragraph, bookmark or keyword targeting over page numbers.",
        ],
    ),
    _tool(
        "wps_agent_writer_selection_replace",
        "writer-selection-replace",
        "Replace Writer selection",
        "Replace the current selection text of a registered Writer document that is open and saved in a running WPS instance, with backup, dry-run, and read-back validation.",
        "writer",
        required=["document_id", "text"],
        properties={
            "document_id": _string("Registered writer document_id."),
            "text": _string("Replacement text, single line, at most 4096 characters."),
            "expected_selection_text": _string("Refuse to write unless the current selection equals this text."),
            "dry_run": _boolean("Preview the selection replacement without modifying the file."),
            "task_id": _string("Optional long-running task status id."),
        },
        mutates_document=True,
        requires_wps=True,
        idempotency="Mutating command; request_id should be supplied and is replayed by the operation ledger.",
        safety_notes=[
            "Uses WPS to edit the open document by range and creates a backup of the saved file before mutation.",
            "Refuses unsaved documents (use save-open-document first), empty selections, selections containing paragraph or table marks, and selections that change between preview and write.",
            "Use dry_run first and pass expected_selection_text; the user's selection is not restored after the edit.",
        ],
    ),
    _tool(
        "wps_agent_writer_selection_insert",
        "writer-selection-insert",
        "Insert text at Writer caret",
        "Insert text at the collapsed caret of a registered Writer document that is open and saved in a running WPS instance, with backup, dry-run, and read-back validation.",
        "writer",
        required=["document_id", "text"],
        properties={
            "document_id": _string("Registered writer document_id."),
            "text": _string("Text to insert, single line, nonempty, at most 4096 characters."),
            "expected_start": _integer("Refuse to write unless the caret start offset equals this value.", minimum=0),
            "dry_run": _boolean("Preview the caret insert without modifying the file."),
            "task_id": _string("Optional long-running task status id."),
        },
        mutates_document=True,
        requires_wps=True,
        idempotency="Mutating command; request_id should be supplied and is replayed by the operation ledger.",
        safety_notes=[
            "Uses WPS to insert at the caret by range and creates a backup of the saved file before mutation.",
            "Refuses unsaved documents (use save-open-document first), read-only documents, non-collapsed selections, empty insert text, and caret positions that change between preview and write.",
            "Use dry_run first and pass expected_start; the user's selection is not restored after the edit. Prefer writer-selection-replace when text is already selected.",
        ],
    ),
    _tool(
        "wps_agent_writer_selection_delete",
        "writer-selection-delete",
        "Delete Writer selection",
        "Delete the current selection text of a registered Writer document that is open and saved in a running WPS instance, with backup, dry-run, and read-back validation.",
        "writer",
        required=["document_id"],
        properties={
            "document_id": _string("Registered writer document_id."),
            "expected_selection_text": _string("Refuse to delete unless the current selection equals this text."),
            "dry_run": _boolean("Preview the selection deletion without modifying the file."),
            "task_id": _string("Optional long-running task status id."),
        },
        mutates_document=True,
        requires_wps=True,
        idempotency="Mutating command; request_id should be supplied and is replayed by the operation ledger.",
        safety_notes=[
            "Uses WPS to clear the selected range and creates a backup of the saved file before mutation.",
            "Refuses unsaved documents (use save-open-document first), empty selections, selections containing paragraph or table marks, and selections that change between preview and write.",
            "Use dry_run first and pass expected_selection_text; the user's selection is not restored after the edit.",
        ],
    ),
    _tool(
        "wps_agent_export_open_document",
        "export-open-document",
        "Export open document to HTML",
        "Export a registered Writer, Presentation, or Spreadsheet document that is open and saved in a running WPS instance to HTML without closing it or changing the source file.",
        "conversion",
        required=["document_id", "output"],
        properties={
            "document_id": _string("Registered writer, presentation, or spreadsheet document_id."),
            "output": _string("New .html or .htm output path; existing files are never overwritten."),
        },
        requires_wps=True,
        idempotency="Creates an artifact; request_id should be supplied and is replayed by the operation ledger.",
        safety_notes=[
            "Writer exports a Documents.Add copy; Presentation uses SaveCopyAs with an HTML format code; Spreadsheet SaveCopyAs has no format argument so HTML is written through a temporary copy + SaveAs.",
            "Rejects unsaved documents with DOCUMENT_HAS_UNSAVED_CHANGES (use save-open-document first); rejects non-HTML bytes for Presentation/Spreadsheet; refuses to overwrite an existing file; checks the source file hash afterwards.",
            "Never launches WPS and never Quit()s an attached instance; the open source workbook is not renamed or closed.",
        ],
    ),
    _tool(
        "wps_agent_export_open_document_pdf",
        "export-open-document-pdf",
        "Export open document to PDF",
        "Export a registered Writer, Presentation, or Spreadsheet document that is open and saved in a running WPS instance to PDF without closing it or changing the source file.",
        "conversion",
        required=["document_id", "output"],
        properties={
            "document_id": _string("Registered writer, presentation, or spreadsheet document_id."),
            "output": _string("New .pdf output path; existing files are never overwritten."),
        },
        requires_wps=True,
        idempotency="Creates an artifact; request_id should be supplied and is replayed by the operation ledger.",
        safety_notes=[
            "Writer exports a Documents.Add copy; Presentation tries ExportAsFixedFormat and falls back to a temporary SaveCopyAs plus SaveAs; Spreadsheet calls ExportAsFixedFormat on the open workbook.",
            "Rejects unsaved documents with DOCUMENT_HAS_UNSAVED_CHANGES (use save-open-document first); rejects non-PDF bytes; refuses to overwrite an existing file; checks the source file hash afterwards.",
            "Never launches WPS and never Quit()s an attached instance; the open source document is not renamed or closed.",
        ],
    ),
    _tool(
        "wps_agent_export_open_document_copy",
        "export-open-document-copy",
        "Save a native copy of an open document",
        "Save a same-format native copy of a registered Writer, Presentation, or Spreadsheet document that is open and saved in a running WPS instance, without closing or renaming the source file.",
        "conversion",
        required=["document_id", "output"],
        properties={
            "document_id": _string("Registered writer, presentation, or spreadsheet document_id."),
            "output": _string(
                "New output path with the same extension as the source; existing files are never overwritten."
            ),
        },
        requires_wps=True,
        idempotency="Creates an artifact; request_id should be supplied and is replayed by the operation ledger.",
        safety_notes=[
            "Uses SaveCopyAs when available; Writer falls back to Documents.Add plus SaveAs if SaveCopyAs is missing.",
            "Rejects unsaved documents with DOCUMENT_HAS_UNSAVED_CHANGES (use save-open-document first); output extension must match the source; OOXML outputs are checked for a ZIP/package signature; existing files are never overwritten.",
            "Never launches WPS and never Quit()s an attached instance; the open source document is not renamed or closed.",
        ],
    ),
    _tool(
        "wps_agent_export_open_document_text",
        "export-open-document-text",
        "Export open document to plain text",
        "Export a registered Writer, Presentation, or Spreadsheet document that is open and saved in a running WPS instance to a plain-text .txt file without closing it or changing the source file.",
        "conversion",
        required=["document_id", "output"],
        properties={
            "document_id": _string("Registered writer, presentation, or spreadsheet document_id."),
            "output": _string("New .txt output path; existing files are never overwritten."),
        },
        requires_wps=True,
        idempotency="Creates an artifact; request_id should be supplied and is replayed by the operation ledger.",
        safety_notes=[
            "Writer exports a Documents.Add copy via text SaveAs; Presentation extracts shape text per slide to UTF-8; Spreadsheet uses a temporary SaveCopyAs then Unicode/Windows text SaveAs.",
            "Rejects unsaved documents with DOCUMENT_HAS_UNSAVED_CHANGES (use save-open-document first); rejects non-text bytes (for example packages or PDF); refuses to overwrite an existing file; checks the source file hash afterwards. data.text_encoding names the file's encoding (utf-16 or utf-8-sig with a byte order mark; utf-8; gbk when WPS writes the Chinese Windows code page; utf-16-le without a byte order mark).",
            "Never launches WPS and never Quit()s an attached instance; the open source document is not renamed or closed.",
        ],
    ),
    _tool(
        "wps_agent_writer_table_smoke",
        "writer-table-smoke",
        "Smoke Writer table cell update",
        "Run a repeatable WPS Writer table cell update smoke test against an output copy with backup and restore dry-run checks.",
        "smoke",
        required=["input", "output", "table_index", "row", "column", "text"],
        properties={
            "input": _string("Input Writer fixture path."),
            "output": _string("Output copy path."),
            "table_index": _integer("1-based table index.", minimum=1),
            "row": _integer("1-based row index.", minimum=1),
            "column": _integer("1-based column index.", minimum=1),
            "text": _string("Replacement cell text."),
            "task_id": _string("Optional long-running task status id."),
        },
        mutates_document=True,
        requires_wps=True,
        idempotency="Mutating smoke command; request_id should be supplied for traceable child write and restore-check operations.",
        safety_notes=[
            "Copies the input fixture to the requested output path before launching WPS.",
            "Uses WPS to mutate the output Writer table cell, creates a backup, and verifies restore dry-run availability.",
        ],
    ),
    _tool(
        "wps_agent_validate_document",
        "validate-document",
        "Validate document",
        "Check one expected value in a registered document and fail when it is not there: for Writer, pass contains (text that must appear in the body); for Spreadsheets, pass cell and equals (a cell on the first sheet and the value it must hold). document_id alone is not enough and returns INVALID_ARGUMENT. Presentation is not supported. To read a document's content, use snapshot_document.",
        "validation",
        required=["document_id"],
        properties={
            "document_id": _string("Registered document_id."),
            "contains": _string(
                "Writer: required. Text that must appear in the document body, matched exactly within one paragraph."
            ),
            "cell": _string("Spreadsheets: required with equals. One A1 cell address on the first sheet, such as B2."),
            "equals": _string(
                "Spreadsheets: required with cell. The value the cell must hold, as text; 42.0 is compared as 42."
            ),
        },
    ),
    _tool(
        "wps_agent_snapshot_document",
        "snapshot-document",
        "Snapshot document",
        "Return a structural validation snapshot for a registered document.",
        "validation",
        required=["document_id"],
        properties={"document_id": _string("Registered document_id.")},
    ),
    _tool(
        "wps_agent_writer_structure",
        "writer-structure",
        "Inspect Writer structure",
        "Read bounded heading, style, and bookmark structure from a registered DOCX without WPS.",
        "writer",
        required=["document_id"],
        properties={
            "document_id": _string("Registered Writer document_id."),
            "limit": _integer("Maximum items per section.", minimum=1, maximum=200),
            "section": _string(
                "Structure list to inspect.", enum=["all", "headings", "styles", "bookmarks", "warnings"]
            ),
            "offset": _integer("Zero-based offset for a selected section.", minimum=0),
            "bookmark_name": _string("Exact bookmark name; requires bookmarks section."),
            "expected_sha256": _string("Require the DOCX hash from the preceding page."),
            "include_text": _boolean("Read bounded text from a unique supported bookmark."),
            "text_limit": _integer("Maximum returned bookmark text characters.", minimum=1, maximum=4096),
        },
        safety_notes=["Read-only offline OOXML inspection; WPS layout and rendering are not validated."],
    ),
    _tool(
        "wps_agent_writer_structure_parity",
        "writer-structure-parity",
        "Audit Writer structure parity",
        "Compare a controlled DOCX fixture with read-only local WPS Writer observations.",
        "writer",
        properties={
            "run_wps": _boolean("Explicitly launch WPS Writer for this audit."),
            "timeout_seconds": _integer("WPS audit timeout.", minimum=1, maximum=300),
            "scope": _string("Controlled Writer fixture to compare.", enum=["structure", "nested"]),
            "artifact_dir": _string("Local JSON report directory."),
        },
        requires_wps=True,
        safety_notes=[
            "Requires run_wps=true; opens the controlled fixture read-only, writes a local report, and uses no remote Git."
        ],
    ),
    _tool(
        "wps_agent_operation",
        "operation",
        "Get operation",
        "Return a recorded operation by request_id.",
        "operations",
        required=["request"],
        properties={"request": _string("Recorded operation request_id.")},
    ),
    _tool(
        "wps_agent_operations",
        "operations",
        "List operations",
        "List recorded operation ledger entries.",
        "operations",
    ),
    _tool(
        "wps_agent_mutation_request_inspect",
        "mutation-request-inspect",
        "Inspect mutation request",
        "Read the main operation and derived backup evidence without changing files.",
        "operations",
        required=["request"],
        properties={"request": _string("Mutation request_id to inspect.")},
        safety_notes=["Read-only local file identity and ledger inspection; does not launch WPS."],
    ),
    _tool(
        "wps_agent_task_status_create",
        "task-status-create",
        "Create task status",
        "Create a reusable status record for a long-running task.",
        "tasks",
        required=["command", "operation_request_id"],
        properties={
            "task_id": _string("Optional stable task id."),
            "command": _string("Command or workflow being tracked."),
            "operation_request_id": _string("Request id for the tracked operation."),
            "document_id": _string("Optional related document_id."),
            "message": _string("Initial status message."),
            "recovery_guidance": _array("Recovery guidance items."),
        },
    ),
    _tool(
        "wps_agent_task_status_update",
        "task-status-update",
        "Update task status",
        "Update a long-running task status record.",
        "tasks",
        required=["task_id", "state"],
        properties={
            "task_id": _string("Task id to update."),
            "state": _string("New task state.", ["pending", "running", "succeeded", "failed", "cancelled"]),
            "progress_percent": _integer("Progress percentage.", minimum=0, maximum=100),
            "message": _string("Updated status message."),
            "recovery_guidance": _array("Recovery guidance items."),
            "result_ref": _string("Optional operation request id or output reference."),
        },
    ),
    _tool(
        "wps_agent_task_status",
        "task-status",
        "Get task status",
        "Return one long-running task status record.",
        "tasks",
        required=["task_id"],
        properties={"task_id": _string("Task id to return.")},
    ),
    _tool(
        "wps_agent_task_statuses",
        "task-statuses",
        "List task statuses",
        "List long-running task status records.",
        "tasks",
    ),
    _tool(
        "wps_agent_task_recovery",
        "task-recovery",
        "Get recovery playbook",
        "Return a recovery playbook for a long-running task status.",
        "recovery",
        required=["task_id"],
        properties={"task_id": _string("Task id to recover or inspect.")},
    ),
    _tool(
        "wps_agent_task_recovery_playbooks",
        "task-recovery-playbooks",
        "List recovery playbooks",
        "List available long-running task recovery playbooks.",
        "recovery",
    ),
    _tool(
        "wps_agent_mcp_tools",
        "mcp-tools",
        "List MCP tool schemas",
        "List draft MCP tool schemas mapped from CLI commands.",
        "mcp",
        properties={
            "category": _string("Optional tool category filter."),
            "mutates_document": _string("Optional mutation filter.", ["true", "false"]),
        },
    ),
    _tool(
        "wps_agent_mcp_catalog_snapshot",
        "mcp-catalog-snapshot",
        "Summarize MCP tool catalog",
        "Summarize MCP tool catalog counts, categories, WPS requirements, and safety-note coverage.",
        "mcp",
    ),
    _tool(
        "wps_agent_mcp_catalog_drift",
        "mcp-catalog-drift",
        "Check MCP catalog drift",
        "Compare the current MCP catalog against a read-only baseline guard.",
        "mcp",
        properties={
            "guard": _string("Path to MCP catalog guard baseline JSON."),
        },
        cli_example="python -m wps_ai_agent_cli mcp-catalog-drift",
        safety_notes=[
            "This tool is read-only and does not launch WPS.",
            "It reports drift for review instead of mutating the baseline.",
        ],
    ),
    _tool(
        "wps_agent_mcp_tool_schema",
        "mcp-tool-schema",
        "Get MCP tool schema",
        "Return one draft MCP tool schema by MCP tool name or CLI command.",
        "mcp",
        required=["name"],
        properties={"name": _string("MCP tool name or CLI command.")},
    ),
    _tool(
        "wps_agent_mcp_call",
        "mcp-call",
        "Call MCP tool adapter",
        "Invoke a draft MCP tool by mapping JSON arguments to the existing CLI response layer.",
        "mcp",
        required=["name"],
        properties={
            "name": _string("MCP tool name or CLI command."),
            "arguments_json": _string("JSON object of tool arguments."),
        },
    ),
    _tool(
        "wps_agent_mcp_server",
        "mcp-server",
        "Run MCP server prototype",
        "Run a local MCP-compatible JSON-RPC server prototype over stdio.",
        "mcp",
        properties={
            "once_json": _string("Optional single JSON-RPC request for smoke tests."),
        },
    ),
    _tool(
        "wps_agent_mcp_smoke",
        "mcp-smoke",
        "Run MCP server smoke checks",
        "Run repeatable MCP server smoke checks for initialize, tools/list, and tools/call.",
        "mcp",
        properties={
            "expected_min_tools": _integer("Minimum number of tools expected from tools/list.", minimum=1),
            "tool_name": _string("Tool name to exercise through tools/call."),
            "arguments_json": _string("Optional JSON object for a local read-only tool call."),
        },
    ),
    _tool(
        "wps_agent_mcp_config_audit",
        "mcp-config-audit",
        "Audit MCP client config",
        "Audit a local MCP client config and run a configured tools/list smoke check.",
        "mcp",
        properties={
            "config": _string("Path to MCP client config JSON."),
            "server_name": {
                **_string("Server key under mcpServers."),
                "minLength": 1,
                "maxLength": MCP_CONFIG_AUDIT_MAX_SERVER_NAME_CHARS,
                "pattern": r".*\S.*",
            },
            "expected_min_tools": _integer(
                "Minimum number of tools expected from tools/list.",
                minimum=MCP_CONFIG_AUDIT_MIN_EXPECTED_TOOLS,
                maximum=MCP_CONFIG_AUDIT_MAX_EXPECTED_TOOLS,
            ),
            "timeout_seconds": _integer(
                "Timeout for the configured tools/list smoke.",
                minimum=MCP_CONFIG_AUDIT_TIMEOUT_MIN_SECONDS,
                maximum=MCP_CONFIG_AUDIT_TIMEOUT_MAX_SECONDS,
            ),
        },
    ),
    _tool(
        "wps_agent_regression_manifest",
        "regression-manifest",
        "List regression manifest scenarios",
        "List regression manifest scenarios and smoke matrix metadata.",
        "regression",
        properties={
            "manifest": _string("Path to regression manifest JSON."),
            "profile": _string("Optional scenario profile filter."),
            "include_wps": _boolean("Include scenarios that require WPS."),
        },
    ),
    _tool(
        "wps_agent_regression_run",
        "regression-run",
        "Run regression manifest",
        "Run regression scenarios from the manifest.",
        "regression",
        properties={
            "manifest": _string("Path to regression manifest JSON."),
            "profile": _string("Optional scenario profile filter."),
            "include_wps": _boolean("Include scenarios that require WPS."),
            "artifact_dir": _string(
                "Optional directory where a timestamped regression-run JSON artifact will be written."
            ),
        },
    ),
    _tool(
        "wps_agent_scan_dir",
        "scan-dir",
        "Scan directory",
        "Scan a directory for supported WPS files and registration status.",
        "batch",
        required=["path"],
        properties={"path": _string("Directory to scan."), "recursive": _boolean("Scan recursively.")},
    ),
    _tool(
        "wps_agent_batch_report",
        "batch-report",
        "Build batch report",
        "Combine directory scan, registration status, and validation snapshots.",
        "batch",
        required=["path"],
        properties={
            "path": _string("Directory to report on."),
            "recursive": _boolean("Report recursively."),
            "no_snapshots": _boolean("Skip validation snapshots."),
        },
    ),
    _tool(
        "wps_agent_spreadsheet_selection_read",
        "spreadsheet-selection-read",
        "Read Spreadsheet selection",
        "Read the current selection address, sheet, cell count, sampled display text, and best-effort chart/shape object metadata of a registered Spreadsheet open in a running WPS instance.",
        "spreadsheet",
        required=["document_id"],
        properties={"document_id": _string("Registered spreadsheet document_id.")},
        requires_wps=True,
        safety_notes=[
            "Read-only: does not change the workbook or the selection, never launches WPS, and never Quit()s an attached instance.",
            "Multi-cell selection_text is sampled (at most 100 cells); use address with spreadsheet-read for full values.",
            "For non-range selections, object_kind/object_name/has_text_frame/has_chart_title/has_axis_title/has_series_values are best-effort and unverified; shape TextFrame, chart ChartTitle/AxisTitle, and Series Values may be replaced or cleared when those flags are true; geometry mutation is not supported.",
        ],
    ),
    _tool(
        "wps_agent_spreadsheet_selection_replace",
        "spreadsheet-selection-replace",
        "Replace Spreadsheet selection",
        "Replace the current cell, range, multi-area, shape TextFrame, chart title, or series Values selection of a registered Spreadsheet open in a running WPS instance using a constant fill or a per-cell values_json matrix, with backup, dry-run, and read-back validation.",
        "spreadsheet",
        required=["document_id"],
        properties={
            "document_id": _string("Registered spreadsheet document_id."),
            "text": _string(
                "Constant replacement text written to every selected cell (including multi-area), "
                "or TAB-joined Series Values / plain ChartTitle/AxisTitle/shape text. Mutually exclusive with values_json."
            ),
            "values_json": _string(
                "Rectangular JSON matrix of cell values. Single-area: shape must match rows×columns. "
                'Multi-area: row-major flatten onto Areas→Cells order (for example [["a","b"]] for two singleton areas). '
                "Mutually exclusive with text."
            ),
            "expected_selection_text": _string(
                "Refuse to write unless the current selection display text equals this value (multi-cell/series values are TAB-joined)."
            ),
            "dry_run": _boolean("Preview the selection replacement without modifying the file."),
            "task_id": _string("Optional long-running task status id."),
        },
        mutates_document=True,
        requires_wps=True,
        idempotency="Mutating command; request_id should be supplied and is replayed by the operation ledger.",
        safety_notes=[
            "Attaches to a running Spreadsheet only: never launches WPS and never Quit()s the attached instance.",
            "Requires worksheet cells (at most 100), a shape with has_text_frame, a chart with has_chart_title/has_axis_title, or a series with has_series_values; constant fill and values_json allow multi-area cells (matrix flattens row-major); shape/title text and series Values support constant --text only (series: TAB-joined, same point count); rejects geometry, shapes without TextFrame, charts without editable title/series API, unsaved (use save-open-document first), read-only, oversized, shape-mismatched, and text-mismatched selections before backup.",
            "Provide exactly one of text (constant fill) or values_json (per-cell matrix). Formula prefixes in values are rejected.",
            "Series Values replace writes a literal array into Series.Values: a series that was bound to worksheet cells is detached from them and no longer follows later cell edits; edit the source cells instead to keep the link.",
        ],
    ),
    _tool(
        "wps_agent_spreadsheet_selection_delete",
        "spreadsheet-selection-delete",
        "Delete Spreadsheet selection",
        "Clear the current cell, range, multi-area, shape TextFrame, chart title, or series Values selection of a registered Spreadsheet open in a running WPS instance, with backup, dry-run, and read-back validation.",
        "spreadsheet",
        required=["document_id"],
        properties={
            "document_id": _string("Registered spreadsheet document_id."),
            "expected_selection_text": _string(
                "Refuse to clear unless the current selection display text equals this value (multi-cell/series values are TAB-joined)."
            ),
            "dry_run": _boolean("Preview the selection deletion without modifying the file."),
            "task_id": _string("Optional long-running task status id."),
        },
        mutates_document=True,
        requires_wps=True,
        idempotency="Mutating command; request_id should be supplied and is replayed by the operation ledger.",
        safety_notes=[
            "Attaches to a running Spreadsheet only: never launches WPS and never Quit()s the attached instance.",
            "Requires worksheet cells (at most 100) with display text/formula, a shape TextFrame with text, a chart ChartTitle/AxisTitle with text, or a series with Values; rejects geometry, shapes without TextFrame, charts without editable title/series API, unsaved (use save-open-document first), read-only, empty, oversized, and text-mismatched selections before backup.",
            "Cell ClearContents removes values and formulas; series delete clears Values to empty points; number formats are left as WPS leaves them. The user's selection is not restored.",
            "Series delete writes literal empty Values, which detaches a cell-bound series from its worksheet range; clear the source cells instead to keep the link.",
        ],
    ),
    _tool(
        "wps_agent_spreadsheet_sheets",
        "spreadsheet-sheets",
        "List spreadsheet worksheets",
        "List worksheet order, names, visibility and used dimensions for a registered workbook.",
        "spreadsheet",
        required=["document_id"],
        properties={
            "document_id": _string("Registered spreadsheet document_id."),
        },
        safety_notes=[
            "Reads the workbook package without launching WPS or modifying the file.",
            "Worksheet order follows the workbook's stored sheet order.",
        ],
    ),
    _tool(
        "wps_agent_spreadsheet_read",
        "spreadsheet-read",
        "Read spreadsheet range",
        "Read an A1 range from a registered spreadsheet document.",
        "spreadsheet",
        required=["document_id", "range"],
        properties={
            "document_id": _string("Registered spreadsheet document_id."),
            "range": _string("A1 range to read, for example A1:D6."),
            "sheet": _string("Optional sheet name. Defaults to first sheet."),
        },
    ),
    _tool(
        "wps_agent_spreadsheet_inspect",
        "spreadsheet-inspect",
        "Inspect spreadsheet calculation and display",
        "Read formulas and saved cached values, recalculate in WPS memory, and return raw results and displayed text without saving the workbook.",
        "spreadsheet",
        required=["document_id", "range"],
        properties={
            "document_id": _string("Registered spreadsheet document_id."),
            "range": _string("Finite A1 range to inspect, for example A1:D6."),
            "sheet": _string("Optional sheet name. Defaults to first sheet."),
        },
        requires_wps=True,
        safety_notes=[
            "Works in the running WPS instance when there is one. A document that is not open yet is opened there only for the duration of the command (its window may briefly appear) and closed again afterwards; a document that was already open is never closed.",
            "Opens the registered workbook read-only and closes it without saving.",
            "Full recalculation (CalculateFullRebuild) runs only in a WPS instance this command launched itself. When attached to a running WPS it is skipped because it recalculates every open workbook and can mark user documents as modified; the result then reports calculation_performed_in_memory=false and does not compare saved caches.",
            "Saved caches are reported separately from WPS values and display text.",
        ],
    ),
    _tool(
        "wps_agent_spreadsheet_rename_sheet",
        "spreadsheet-rename-sheet",
        "Rename spreadsheet worksheet",
        "Rename a worksheet with Excel title validation, backup and ordered name read-back.",
        "spreadsheet",
        required=["document_id", "old_name", "new_name"],
        properties={
            "document_id": _string("Registered spreadsheet document_id."),
            "old_name": _string("Current worksheet name."),
            "new_name": _string("New worksheet name."),
            "dry_run": _boolean("Validate and preview without backup or WPS."),
            "task_id": _string("Optional long-running task status id."),
        },
        mutates_document=True,
        requires_wps=True,
        idempotency="Mutating command; request_id is bound to document, source and target worksheet names.",
        safety_notes=[
            "Only one running WPS instance can be attached. When more than one WPS process of the component has a main window (in this user session) and the document is not already open in the attached instance, the command refuses and lists the pids and window titles; close the extra WPS windows, or set WPS_AGENT_ALLOW_MULTI_INSTANCE=1 to skip this check. Extra background processes without a window do not block the command; they add a warning to the result.",
            "Works in the running WPS instance when there is one. A document that is not open yet is opened there only for the duration of the command (its window may briefly appear) and closed again afterwards; a document that was already open is never closed.",
            "Creates a backup before WPS mutation and verifies the complete ordered worksheet-name list after save.",
            "Rejects invalid or duplicate worksheet names before backup or WPS launch.",
        ],
    ),
    _tool(
        "wps_agent_spreadsheet_create_sheet",
        "spreadsheet-create-sheet",
        "Create spreadsheet worksheet",
        "Create a worksheet at a 1-based position with title validation, backup and ordered name read-back.",
        "spreadsheet",
        required=["document_id", "name"],
        properties={
            "document_id": _string("Registered spreadsheet document_id."),
            "name": _string("New worksheet name."),
            "index": {"type": "integer", "description": "1-based insertion index; defaults to the end."},
            "dry_run": _boolean("Validate and preview without backup or WPS."),
            "task_id": _string("Optional long-running task status id."),
        },
        mutates_document=True,
        requires_wps=True,
        idempotency="Mutating command; request_id is bound to document, worksheet name, insertion index and dry_run.",
        safety_notes=[
            "Only one running WPS instance can be attached. When more than one WPS process of the component has a main window (in this user session) and the document is not already open in the attached instance, the command refuses and lists the pids and window titles; close the extra WPS windows, or set WPS_AGENT_ALLOW_MULTI_INSTANCE=1 to skip this check. Extra background processes without a window do not block the command; they add a warning to the result.",
            "Works in the running WPS instance when there is one. A document that is not open yet is opened there only for the duration of the command (its window may briefly appear) and closed again afterwards; a document that was already open is never closed.",
            "Creates a backup before WPS mutation and verifies the complete ordered worksheet-name list after save.",
            "Rejects invalid or duplicate worksheet names and out-of-range positions before backup or WPS launch.",
        ],
    ),
    _tool(
        "wps_agent_spreadsheet_set_sheet_visibility",
        "spreadsheet-set-sheet-visibility",
        "Set spreadsheet worksheet visibility",
        "Show or hide a worksheet with a visible-sheet safeguard, backup and ordered state read-back.",
        "spreadsheet",
        required=["document_id", "sheet_name", "visible"],
        properties={
            "document_id": _string("Registered spreadsheet document_id."),
            "sheet_name": _string("Worksheet to show or hide."),
            "visible": {"type": "string", "enum": ["true", "false"], "description": "Set worksheet visible or hidden."},
            "dry_run": _boolean("Validate and preview without backup or WPS."),
            "task_id": _string("Optional long-running task status id."),
        },
        mutates_document=True,
        requires_wps=True,
        idempotency="Mutating command; request_id is bound to document, worksheet name, visibility and dry_run.",
        safety_notes=[
            "Only one running WPS instance can be attached. When more than one WPS process of the component has a main window (in this user session) and the document is not already open in the attached instance, the command refuses and lists the pids and window titles; close the extra WPS windows, or set WPS_AGENT_ALLOW_MULTI_INSTANCE=1 to skip this check. Extra background processes without a window do not block the command; they add a warning to the result.",
            "Works in the running WPS instance when there is one. A document that is not open yet is opened there only for the duration of the command (its window may briefly appear) and closed again afterwards; a document that was already open is never closed.",
            "Creates a backup before WPS mutation and verifies the complete ordered worksheet visibility list after save.",
            "Refuses to hide the last visible worksheet before backup or WPS launch.",
        ],
    ),
    _tool(
        "wps_agent_spreadsheet_delete_sheet",
        "spreadsheet-delete-sheet",
        "Delete spreadsheet worksheet",
        "Delete a worksheet with last-sheet protection, backup and ordered name read-back.",
        "spreadsheet",
        required=["document_id", "sheet_name"],
        properties={
            "document_id": _string("Registered spreadsheet document_id."),
            "sheet_name": _string("Worksheet to delete."),
            "dry_run": _boolean("Validate and preview without backup or WPS."),
            "task_id": _string("Optional long-running task status id."),
        },
        mutates_document=True,
        requires_wps=True,
        idempotency="Mutating command; request_id is bound to document, worksheet name and dry_run.",
        safety_notes=[
            "Only one running WPS instance can be attached. When more than one WPS process of the component has a main window (in this user session) and the document is not already open in the attached instance, the command refuses and lists the pids and window titles; close the extra WPS windows, or set WPS_AGENT_ALLOW_MULTI_INSTANCE=1 to skip this check. Extra background processes without a window do not block the command; they add a warning to the result.",
            "Works in the running WPS instance when there is one. A document that is not open yet is opened there only for the duration of the command (its window may briefly appear) and closed again afterwards; a document that was already open is never closed.",
            "Creates a backup before WPS mutation and verifies the complete ordered worksheet-name list after save.",
            "Refuses to delete the final worksheet before backup or WPS launch; dry_run previews the exact resulting order.",
        ],
    ),
    _tool(
        "wps_agent_spreadsheet_copy_sheet",
        "spreadsheet-copy-sheet",
        "Copy spreadsheet worksheet",
        "Copy a worksheet with title and position validation, backup and ordered name plus sample-cell read-back.",
        "spreadsheet",
        required=["document_id", "source_name", "new_name"],
        properties={
            "document_id": _string("Registered spreadsheet document_id."),
            "source_name": _string("Worksheet to copy."),
            "new_name": _string("Name for the copied worksheet."),
            "index": {"type": "integer", "description": "1-based insertion index; defaults to the end."},
            "dry_run": _boolean("Validate and preview without backup or WPS."),
            "task_id": _string("Optional long-running task status id."),
        },
        mutates_document=True,
        requires_wps=True,
        idempotency="Mutating command; request_id is bound to document, source and new worksheet, index and dry_run.",
        safety_notes=[
            "Only one running WPS instance can be attached. When more than one WPS process of the component has a main window (in this user session) and the document is not already open in the attached instance, the command refuses and lists the pids and window titles; close the extra WPS windows, or set WPS_AGENT_ALLOW_MULTI_INSTANCE=1 to skip this check. Extra background processes without a window do not block the command; they add a warning to the result.",
            "Works in the running WPS instance when there is one. A document that is not open yet is opened there only for the duration of the command (its window may briefly appear) and closed again afterwards; a document that was already open is never closed.",
            "Creates a backup before WPS mutation and verifies ordered names and a copied cell value after save.",
            "Rejects invalid/duplicate titles and out-of-range positions before backup or WPS launch.",
        ],
    ),
    _tool(
        "wps_agent_spreadsheet_set_sheet_tab_color",
        "spreadsheet-set-sheet-tab-color",
        "Set worksheet tab color",
        "Set or clear a worksheet tab color with strict hex validation, backup and read-back validation.",
        "spreadsheet",
        required=["document_id", "sheet_name", "color"],
        properties={
            "document_id": _string("Registered spreadsheet document_id."),
            "sheet_name": _string("Worksheet whose tab color will change."),
            "color": _string("Hex color in #RRGGBB form, or 'none' to clear it."),
            "dry_run": _boolean("Validate and preview without backup or WPS."),
            "task_id": _string("Optional long-running task status id."),
        },
        mutates_document=True,
        requires_wps=True,
        idempotency="Mutating command; request_id is bound to document, sheet name, normalized color and dry_run.",
        safety_notes=[
            "Only one running WPS instance can be attached. When more than one WPS process of the component has a main window (in this user session) and the document is not already open in the attached instance, the command refuses and lists the pids and window titles; close the extra WPS windows, or set WPS_AGENT_ALLOW_MULTI_INSTANCE=1 to skip this check. Extra background processes without a window do not block the command; they add a warning to the result.",
            "Works in the running WPS instance when there is one. A document that is not open yet is opened there only for the duration of the command (its window may briefly appear) and closed again afterwards; a document that was already open is never closed.",
            "Creates a backup before WPS mutation and checks the saved tab color through an independent workbook read-back.",
            "Accepts only #RRGGBB or the explicit 'none' reset value before backup or WPS launch.",
        ],
    ),
    _tool(
        "wps_agent_spreadsheet_write",
        "spreadsheet-write",
        "Write spreadsheet range",
        "Write a JSON matrix to an A1 range in a registered spreadsheet document.",
        "spreadsheet",
        required=["document_id", "range", "values_json"],
        properties={
            "document_id": _string("Registered spreadsheet document_id."),
            "range": _string("A1 range to write, for example A1:B2."),
            "values_json": _string("Rectangular JSON matrix, for example [[1,2],[3,4]]."),
            "sheet": _string("Optional sheet name. Defaults to first sheet."),
            "dry_run": _boolean("Preview write shape without modifying the file."),
            "task_id": _string("Optional long-running task status id."),
        },
        mutates_document=True,
        requires_wps=True,
        idempotency="Mutating command; request_id should be supplied and is replayed by the operation ledger.",
        safety_notes=[
            "Only one running WPS instance can be attached. When more than one WPS process of the component has a main window (in this user session) and the document is not already open in the attached instance, the command refuses and lists the pids and window titles; close the extra WPS windows, or set WPS_AGENT_ALLOW_MULTI_INSTANCE=1 to skip this check. Extra background processes without a window do not block the command; they add a warning to the result.",
            "Works in the running WPS instance when there is one. A document that is not open yet is opened there only for the duration of the command (its window may briefly appear) and closed again afterwards; a document that was already open is never closed.",
            "Uses WPS to mutate a registered spreadsheet and creates a backup before mutation.",
            "Creates a backup before mutation and validates read-back results.",
            "Rejects non-scalar or non-finite values and text starting with '=', '+', '-' or '@' before backup or WPS launch; use spreadsheet-formula-write for formulas.",
        ],
    ),
    _tool(
        "wps_agent_spreadsheet_formula_write",
        "spreadsheet-formula-write",
        "Write spreadsheet formulas",
        "Write formulas to an A1 range, recalculate with WPS, and validate cached values.",
        "spreadsheet",
        required=["document_id", "range", "formulas_json", "expected_values_json"],
        properties={
            "document_id": _string("Registered spreadsheet document_id."),
            "range": _string("A1 range to write, for example D4:D6."),
            "formulas_json": _string("Rectangular JSON matrix of formulas."),
            "expected_values_json": _string("Rectangular JSON matrix of expected cached values."),
            "sheet": _string("Optional sheet name. Defaults to first sheet."),
            "dry_run": _boolean("Preview formula write shape without modifying the file."),
            "task_id": _string("Optional long-running task status id."),
        },
        mutates_document=True,
        requires_wps=True,
        idempotency="Mutating command; request_id should be supplied and is replayed by the operation ledger.",
        safety_notes=[
            "Only one running WPS instance can be attached. When more than one WPS process of the component has a main window (in this user session) and the document is not already open in the attached instance, the command refuses and lists the pids and window titles; close the extra WPS windows, or set WPS_AGENT_ALLOW_MULTI_INSTANCE=1 to skip this check. Extra background processes without a window do not block the command; they add a warning to the result.",
            "Works in the running WPS instance when there is one. A document that is not open yet is opened there only for the duration of the command (its window may briefly appear) and closed again afterwards; a document that was already open is never closed.",
            "Uses WPS to mutate formulas in a registered spreadsheet and creates a backup before mutation.",
            "Use dry_run before mutation when possible and validate cached calculation results after write.",
        ],
    ),
    _tool(
        "wps_agent_presentation_selection_read",
        "presentation-selection-read",
        "Read Presentation selection",
        "Read the current selection kind, text, slide index and shape name of a registered Presentation open in a running WPS instance.",
        "presentation",
        required=["document_id"],
        properties={"document_id": _string("Registered presentation document_id.")},
        requires_wps=True,
        safety_notes=[
            "Read-only: does not change the presentation or the selection, never launches WPS, and never Quit()s an attached instance.",
            "slide_index is best-effort and unverified; prefer shape text or slide-scoped replace over slide numbers alone.",
        ],
    ),
    _tool(
        "wps_agent_presentation_selection_replace",
        "presentation-selection-replace",
        "Replace Presentation selection",
        "Replace the current text selection of a registered Presentation open in a running WPS instance, with backup, dry-run, and read-back validation.",
        "presentation",
        required=["document_id", "text"],
        properties={
            "document_id": _string("Registered presentation document_id."),
            "text": _string("Replacement text (single line, at most 4096 characters)."),
            "expected_selection_text": _string("Refuse to write unless the current selection text equals this value."),
            "dry_run": _boolean("Preview the selection replacement without modifying the file."),
            "task_id": _string("Optional long-running task status id."),
        },
        mutates_document=True,
        requires_wps=True,
        idempotency="Mutating command; request_id should be supplied and is replayed by the operation ledger.",
        safety_notes=[
            "Attaches to a running Presentation only: never launches WPS and never Quit()s the attached instance.",
            "Requires a text selection; rejects unsaved (use save-open-document first), read-only, empty, oversized, or non-text selections before backup.",
            "Use dry_run and expected_selection_text before mutation when possible.",
        ],
    ),
    _tool(
        "wps_agent_presentation_selection_insert",
        "presentation-selection-insert",
        "Insert text at Presentation caret",
        "Insert text at the collapsed text caret of a registered Presentation that is open and saved in a running WPS instance, with backup, dry-run, and read-back validation.",
        "presentation",
        required=["document_id", "text"],
        properties={
            "document_id": _string("Registered presentation document_id."),
            "text": _string("Text to insert, single line, nonempty, at most 4096 characters."),
            "expected_start": _integer(
                "Refuse to write unless the text caret Start offset equals this value (1-based).", minimum=1
            ),
            "dry_run": _boolean("Preview the caret insert without modifying the file."),
            "task_id": _string("Optional long-running task status id."),
        },
        mutates_document=True,
        requires_wps=True,
        idempotency="Mutating command; request_id should be supplied and is replayed by the operation ledger.",
        safety_notes=[
            "Attaches to a running Presentation only: never launches WPS and never Quit()s the attached instance.",
            "Requires a collapsed text caret inside a shape; rejects unsaved (use save-open-document first), read-only, non-text, and non-collapsed selections before backup.",
            "Use dry_run and expected_start before mutation when possible; prefer presentation-selection-replace when text is already selected.",
        ],
    ),
    _tool(
        "wps_agent_presentation_selection_delete",
        "presentation-selection-delete",
        "Delete Presentation selection",
        "Delete the current text selection of a registered Presentation that is open and saved in a running WPS instance, with backup, dry-run, and read-back validation.",
        "presentation",
        required=["document_id"],
        properties={
            "document_id": _string("Registered presentation document_id."),
            "expected_selection_text": _string("Refuse to delete unless the current selection text equals this value."),
            "dry_run": _boolean("Preview the selection deletion without modifying the file."),
            "task_id": _string("Optional long-running task status id."),
        },
        mutates_document=True,
        requires_wps=True,
        idempotency="Mutating command; request_id should be supplied and is replayed by the operation ledger.",
        safety_notes=[
            "Attaches to a running Presentation only: never launches WPS and never Quit()s the attached instance.",
            "Requires a text selection; rejects unsaved (use save-open-document first), read-only, empty, oversized, or non-text selections before backup.",
            "Use dry_run and expected_selection_text before mutation when possible.",
        ],
    ),
    _tool(
        "wps_agent_presentation_replace",
        "presentation-replace",
        "Replace presentation text",
        "Replace text in a registered presentation with backup, validation, and idempotency.",
        "presentation",
        required=["document_id", "find", "replace"],
        properties={
            "document_id": _string("Registered presentation document_id."),
            "find": _string("Text to find."),
            "replace": _string("Replacement text."),
            "dry_run": _boolean("Preview matches without modifying the file."),
            "slide_index": _integer("Optional 1-based slide index.", minimum=1),
            "task_id": _string("Optional long-running task status id."),
        },
        mutates_document=True,
        requires_wps=True,
        idempotency="Mutating command; request_id should be supplied and is replayed by the operation ledger.",
        safety_notes=[
            "Only one running WPS instance can be attached. When more than one WPS process of the component has a main window (in this user session) and the document is not already open in the attached instance, the command refuses and lists the pids and window titles; close the extra WPS windows, or set WPS_AGENT_ALLOW_MULTI_INSTANCE=1 to skip this check. Extra background processes without a window do not block the command; they add a warning to the result.",
            "Works in the running WPS instance when there is one. A document that is not open yet is opened there only for the duration of the command (its window may briefly appear) and closed again afterwards; a document that was already open is never closed.",
            "Uses WPS to mutate a registered presentation and creates a backup before mutation.",
            "Refused when the presentation is already open in WPS: WPS does not reliably report unsaved presentation changes, so edits in an open presentation cannot be protected. Close it first.",
            "Use dry_run before mutation when possible and validate replacement results after write.",
        ],
    ),
    _tool(
        "wps_agent_security_audit",
        "security-audit",
        "Audit security boundaries",
        "Lint mutating tool schemas for documented safety boundaries and check every tool schema against its CLI parser. This is a schema and parser consistency check, not a behavioral test.",
        "security",
    ),
    _tool(
        "wps_agent_performance_baseline",
        "performance-baseline",
        "Capture performance baseline",
        "Capture runtime and output-size baselines for safe read-only commands.",
        "performance",
    ),
)


# File-based write tools cannot change a document WPS has open; say so where an agent chooses a tool (P9-001).
_FILE_BASED_ON_OPEN_DOCUMENT = {
    "writer": "Not for a document that is open in WPS: WPS holds the file and the command refuses with DOCUMENT_HELD_OPEN. For an open document use the selection tools (wps_agent_writer_selection_read, _replace, _insert, _delete) after wps_agent_open_documents.",
    "presentation": "Not for a presentation that is open in WPS: the command refuses. For an open presentation use the selection tools (wps_agent_presentation_selection_read, _replace, _insert, _delete) after wps_agent_open_documents.",
    "spreadsheet": "Not for a workbook that is open in WPS: WPS holds the file and the command refuses with DOCUMENT_HELD_OPEN. For an open workbook use the selection tools (wps_agent_spreadsheet_selection_read, _replace, _delete) after wps_agent_open_documents.",
    "sheet": "Not for a workbook that is open in WPS: WPS holds the file and the command refuses with DOCUMENT_HELD_OPEN. There is no open-document tool for sheet structure; save and close the workbook in WPS first.",
}


def _with_open_document_notes(schemas: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    from .open_document_hints import OPEN_DOCUMENT_ALTERNATIVES

    result = []
    for schema in schemas:
        command = schema["cli_command"]
        if command in OPEN_DOCUMENT_ALTERNATIVES:
            kind = command.split("-")[0]
            if command.startswith("spreadsheet-") and "sheet" in command.removeprefix("spreadsheet-"):
                kind = "sheet"
            schema = {**schema, "safety_notes": [*schema["safety_notes"], _FILE_BASED_ON_OPEN_DOCUMENT[kind]]}
        result.append(schema)
    return tuple(result)


# The tools agents still called to check a write that had already verified itself (P10-006, P11-005).
_CHECKING_COMMANDS = ("validate-document", "snapshot-document", "spreadsheet-read")
_CHECKING_NOTE = (
    "Not needed to check an open-document write (writer/presentation/spreadsheet selection replace, insert or "
    "delete, save, save-as, text export): that write's result already holds data.verified_state, the saved file "
    "compared with the pre-write backup, and its check sentence is in the summary."
)


def _with_verified_notes(schemas: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    from .verified_state import VERIFIED_COMMANDS, VERIFIED_NOTE

    def notes(schema: dict[str, Any]) -> list[str]:
        if schema["cli_command"] in VERIFIED_COMMANDS:
            return [*schema["safety_notes"], VERIFIED_NOTE]
        if schema["cli_command"] in _CHECKING_COMMANDS:
            return [*schema["safety_notes"], _CHECKING_NOTE]
        return schema["safety_notes"]

    return tuple({**schema, "safety_notes": notes(schema)} for schema in schemas)


MCP_TOOL_SCHEMAS = _with_verified_notes(_with_open_document_notes(MCP_TOOL_SCHEMAS))


def list_mcp_tool_schemas(
    category: str | None = None,
    mutates_document: bool | None = None,
) -> list[dict[str, Any]]:
    schemas = [dict(schema) for schema in MCP_TOOL_SCHEMAS]
    if category:
        schemas = [schema for schema in schemas if schema["category"] == category]
    if mutates_document is not None:
        schemas = [schema for schema in schemas if schema["mutates_document"] is mutates_document]
    return schemas


def get_mcp_tool_schema(name: str) -> dict[str, Any] | None:
    for schema in MCP_TOOL_SCHEMAS:
        if schema["name"] == name or schema["cli_command"] == name:
            return dict(schema)
    return None


def list_mcp_tool_categories() -> list[str]:
    return sorted({schema["category"] for schema in MCP_TOOL_SCHEMAS})
