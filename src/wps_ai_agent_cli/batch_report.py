from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .file_scan import scan_directory
from .snapshots import snapshot_document


def _snapshot_summary(snapshot: dict[str, Any]) -> dict[str, Any]:
    component = snapshot.get("component")
    if component == "writer":
        return {
            "paragraph_count": snapshot.get("paragraph_count"),
            "non_empty_paragraph_count": snapshot.get("non_empty_paragraph_count"),
            "body_text_length": snapshot.get("body_text_length"),
        }
    if component == "spreadsheets":
        return {
            "sheet_count": snapshot.get("sheet_count"),
            "formula_count": snapshot.get("formula_count"),
            "formula_error_count": snapshot.get("formula_error_count"),
        }
    if component == "presentation":
        return {
            "slide_count": snapshot.get("slide_count"),
            "text_object_count": snapshot.get("text_object_count"),
            "non_empty_text_object_count": snapshot.get("non_empty_text_object_count"),
        }
    return {}


def build_batch_report(
    directory: str | Path,
    recursive: bool = False,
    include_snapshots: bool = True,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    scan_ok, scan_result, scan_errors = scan_directory(
        directory,
        recursive=recursive,
        workspace=workspace,
    )
    if not scan_ok:
        return False, {}, scan_errors

    files = []
    snapshot_passed_count = 0
    snapshot_failed_count = 0
    snapshot_skipped_count = 0
    component_counts: Counter[str] = Counter()
    registered_count = 0

    for scanned_file in scan_result["files"]:
        entry = dict(scanned_file)
        component_counts[entry["component"]] += 1
        if entry["registered"]:
            registered_count += 1

        if not include_snapshots:
            entry["snapshot_status"] = "disabled"
            files.append(entry)
            continue

        document_id = entry.get("document_id")
        if not document_id:
            snapshot_skipped_count += 1
            entry["snapshot_status"] = "skipped"
            entry["snapshot_reason"] = "file is not registered"
            files.append(entry)
            continue

        snapshot_ok, snapshot, snapshot_errors = snapshot_document(document_id, workspace=workspace)
        if snapshot_ok:
            snapshot_passed_count += 1
            entry["snapshot_status"] = "passed"
            entry["snapshot_summary"] = _snapshot_summary(snapshot)
            entry["snapshot"] = snapshot
        else:
            snapshot_failed_count += 1
            entry["snapshot_status"] = "failed"
            entry["snapshot_errors"] = snapshot_errors
            entry["snapshot"] = snapshot
        files.append(entry)

    summary = {
        "total_files": scan_result["count"],
        "registered_files": registered_count,
        "unregistered_files": scan_result["count"] - registered_count,
        "component_counts": dict(sorted(component_counts.items())),
        "snapshots_enabled": include_snapshots,
        "snapshot_passed": snapshot_passed_count,
        "snapshot_failed": snapshot_failed_count,
        "snapshot_skipped": snapshot_skipped_count,
    }
    return (
        True,
        {
            "directory": scan_result["directory"],
            "recursive": recursive,
            "summary": summary,
            "files": files,
        },
        [],
    )
