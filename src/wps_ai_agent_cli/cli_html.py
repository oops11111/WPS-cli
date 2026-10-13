"""HTML render, conversion, batch, round-trip and directory-scan commands."""

from __future__ import annotations

from .batch_conversion import convert_html_batch, inspect_batch_request
from .batch_report import build_batch_report
from .cli_common import BACKEND
from .file_scan import scan_directory
from .html_office import BACKENDS as HTML_OFFICE_BACKENDS
from .html_office import convert_html_to_office
from .html_render import render_html
from .html_roundtrip import (
    build_html_roundtrip_mapping,
    export_controlled_html,
    import_controlled_html,
    verify_controlled_document,
)
from .models import CommandResponse, ValidationResult
from .template_report import render_batch_template_report


def html_render_response(request_id: str, input_path: str, output_path: str, output_format: str,
                         page_size: str, viewport_width: int, viewport_height: int,
                         timeout_seconds: int, allow_javascript: bool) -> CommandResponse:
    ok, data, errors = render_html(
        input_path, output_path, output_format, page_size=page_size,
        viewport_width=viewport_width, viewport_height=viewport_height,
        timeout_seconds=timeout_seconds, allow_javascript=allow_javascript,
    )
    return CommandResponse(
        ok=ok, command="html-render", request_id=request_id, backend="playwright-edge",
        summary="HTML rendered successfully." if ok else "HTML rendering could not complete.",
        data=data, validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[{"name": "output_artifact_verified", "passed": ok, "details": data.get("output_path")}],
        ), errors=errors,
    )


def html_editable_response(request_id: str, input_path: str, output_path: str, output_format: str = "docx") -> CommandResponse:
    ok, data, errors = convert_html_to_office(input_path, output_path, output_format)
    backend = HTML_OFFICE_BACKENDS.get(output_format, "python-docx")
    native_objects = data.get("mapped_objects") or data.get("rows") or data.get("slides")
    return CommandResponse(
        ok=ok, command="html-editable", request_id=request_id, backend=backend,
        summary=(f"HTML mapped to editable {output_format.upper()} content." if ok else "Editable HTML conversion could not complete."),
        data=data, validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {"name": "output_created", "passed": ok, "details": data.get("output_path")},
                {"name": "native_objects_reported", "passed": ok and bool(native_objects), "details": native_objects},
            ],
        ), errors=errors,
    )


def html_batch_convert_response(request_id: str, input_directory: str, output_directory: str,
                                mode: str, recursive: bool, progress_callback=None) -> CommandResponse:
    ok, data, errors = convert_html_batch(
        input_directory, output_directory, mode, recursive=recursive,
        request_id=request_id,
        progress_callback=progress_callback,
    )
    summary = data.get("summary", {})
    cancelled = bool(data.get("cancelled"))
    return CommandResponse(
        ok=ok, command="html-batch-convert", request_id=request_id, backend="local-python",
        summary=(f"Batch conversion cancelled after {summary.get('processed', 0)} of {summary.get('total', 0)} files."
                 if cancelled else f"Batch conversion finished: {summary.get('passed', 0)} passed, {summary.get('failed', 0)} failed."),
        data=data, validation=ValidationResult(status="passed" if ok else "partial" if data else "failed", checks=[
            {"name": "per_file_results_recorded", "passed": bool(data.get("files")), "details": summary},
            {"name": "provenance_manifest_created", "passed": bool(data.get("manifest_path")), "details": data.get("manifest_path")},
            {"name": "cancelled_with_partial_manifest", "passed": not cancelled or bool(data.get("manifest_path")), "details": cancelled},
        ]), errors=errors,
    )


def html_batch_request_response(request_id: str, batch_request_id: str, verify: bool = False) -> CommandResponse:
    ok, record, errors = inspect_batch_request(batch_request_id, verify=verify)
    validation_status = "failed" if not ok else "warning" if record["evidence_status"] == "failed" else "passed"
    return CommandResponse(
        ok=ok, command="html-batch-request", request_id=request_id, backend="local-python",
        summary="Batch request returned." if ok else "Batch request inspection failed.",
        data={"batch_request": record} if ok else {},
        validation=ValidationResult(status=validation_status, checks=[
            {"name": "batch_request_record_valid", "passed": ok, "details": batch_request_id},
            {"name": "batch_request_evidence_valid", "passed": record.get("evidence_status") != "failed", "details": record.get("evidence_status")},
        ]), errors=errors,
    )


def batch_template_report_response(request_id: str, manifest_path: str, template_path: str,
                                   output_path: str) -> CommandResponse:
    ok, data, errors = render_batch_template_report(manifest_path, template_path, output_path)
    return CommandResponse(
        ok=ok, command="batch-template-report", request_id=request_id, backend=BACKEND,
        summary="Batch template report created." if ok else "Batch template report was rejected.",
        data=data, validation=ValidationResult(status="passed" if ok else "failed", checks=[
            {"name": "manifest_and_template_verified", "passed": ok, "details": data.get("manifest_sha256")},
            {"name": "report_created_without_overwrite", "passed": ok, "details": data.get("output_path")},
        ]), errors=errors,
    )


def html_roundtrip_plan_response(request_id: str, input_path: str) -> CommandResponse:
    ok, data, errors = build_html_roundtrip_mapping(input_path)
    return CommandResponse(
        ok=ok, command="html-roundtrip-plan", request_id=request_id, backend=BACKEND,
        summary="Owned HTML identity mapping is valid." if ok else "Owned HTML identity mapping was rejected.",
        data={"roundtrip_mapping": data},
        validation=ValidationResult(status="passed" if ok else "failed", checks=[
            {"name": "versioned_schema_valid", "passed": ok, "details": data.get("schema_version")},
            {"name": "object_ids_unambiguous", "passed": ok, "details": data.get("mapping_count", 0)},
        ]), errors=errors,
    )


def html_controlled_import_response(request_id: str, input_path: str, output_path: str) -> CommandResponse:
    ok, data, errors = import_controlled_html(input_path, output_path)
    return CommandResponse(
        ok=ok, command="html-controlled-import", request_id=request_id, backend="python-docx",
        summary="Owned HTML imported with stable document bookmarks." if ok else "Controlled HTML import could not complete.",
        data=data, validation=ValidationResult(status="passed" if ok else "failed", checks=[
            {"name": "docx_and_mapping_created", "passed": ok, "details": data.get("mapping_path")},
            {"name": "all_object_bookmarks_written", "passed": ok, "details": data.get("bookmark_count")},
        ]), errors=errors,
    )


def html_roundtrip_verify_response(request_id: str, document_path: str, mapping_path: str) -> CommandResponse:
    ok, data, errors = verify_controlled_document(document_path, mapping_path)
    return CommandResponse(
        ok=ok, command="html-roundtrip-verify", request_id=request_id, backend=BACKEND,
        summary="Controlled document identity is verified." if ok else "Controlled document identity needs review.",
        data=data, validation=ValidationResult(status="passed" if ok else "failed", checks=[
            {"name": "mapped_bookmarks_unique_and_ordered", "passed": ok, "details": data.get("object_count")},
        ]), errors=errors,
    )


def html_roundtrip_export_response(request_id: str, document_path: str, mapping_path: str, output_path: str) -> CommandResponse:
    ok, data, errors = export_controlled_html(document_path, mapping_path, output_path)
    return CommandResponse(
        ok=ok, command="html-roundtrip-export", request_id=request_id, backend="python-docx",
        summary="Controlled DOCX exported to owned HTML." if ok else "Controlled HTML export was rejected.",
        data=data, validation=ValidationResult(status="passed" if ok else "failed", checks=[
            {"name": "owned_html_v1_created", "passed": ok, "details": data.get("output_path")},
            {"name": "all_mapped_object_ids_exported", "passed": ok, "details": data.get("exported_object_count")},
        ]), errors=errors,
    )


def scan_dir_response(request_id: str, path: str, recursive: bool) -> CommandResponse:
    ok, result, errors = scan_directory(path, recursive=recursive)
    return CommandResponse(
        ok=ok,
        command="scan-dir",
        request_id=request_id,
        backend=BACKEND,
        summary=(
            f"Returned {result.get('count', 0)} supported files."
            if ok
            else "Directory scan failed."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok else "failed",
            checks=[
                {
                    "name": "directory_scanned",
                    "passed": ok,
                    "details": path,
                }
            ],
        ),
        errors=errors,
    )


def batch_report_response(
    request_id: str,
    path: str,
    recursive: bool,
    include_snapshots: bool,
) -> CommandResponse:
    ok, result, errors = build_batch_report(
        directory=path,
        recursive=recursive,
        include_snapshots=include_snapshots,
    )
    summary = result.get("summary", {})
    return CommandResponse(
        ok=ok,
        command="batch-report",
        request_id=request_id,
        backend=BACKEND,
        summary=(
            f"Batch report returned {summary.get('total_files', 0)} supported files."
            if ok
            else "Batch report failed."
        ),
        data=result,
        validation=ValidationResult(
            status="passed" if ok and not summary.get("snapshot_failed") else "failed",
            checks=[
                {
                    "name": "directory_scanned",
                    "passed": ok,
                    "details": path,
                },
                {
                    "name": "registration_status_included",
                    "passed": ok,
                    "details": {
                        "registered_files": summary.get("registered_files"),
                        "unregistered_files": summary.get("unregistered_files"),
                    },
                },
                {
                    "name": "snapshots_collected",
                    "passed": bool(ok and (not include_snapshots or summary.get("snapshot_failed") == 0)),
                    "details": {
                        "enabled": include_snapshots,
                        "passed": summary.get("snapshot_passed"),
                        "failed": summary.get("snapshot_failed"),
                        "skipped": summary.get("snapshot_skipped"),
                    },
                },
            ],
        ),
        errors=errors,
    )
