from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .sync_package_coverage import build_sync_package_coverage
from .sync_package_inspect import DEFAULT_SYNC_PACKAGE, inspect_sync_package
from .sync_package_summary import summarize_sync_package
from .recovery_drill_evidence import verify_recovery_drill_package
from .writer_structure_parity import FIXTURE, NESTED_FIXTURE, SCRIPT, _sha256, implementation_hashes


def _writer_parity_evidence(workspace: Path, inclusion: dict[str, Any], fixture_relative: Path,
                            expected_scope: str | None = None) -> dict[str, Any]:
    relative = inclusion.get("expected_path")
    if not relative:
        return {"status": "missing", "artifact": None, "reason": "No Writer parity report exists."}
    artifact = workspace / relative
    try:
        payload = json.loads(artifact.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "failed", "artifact": str(artifact), "reason": str(exc)}
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    report = data.get("writer_structure_parity", {}) if isinstance(data, dict) else {}
    validation = payload.get("validation", {}) if isinstance(payload, dict) else {}
    checks = report.get("checks", []) if isinstance(report, dict) else []
    check_names = {check.get("name") for check in checks if isinstance(check, dict)} if isinstance(checks, list) else set()
    passed = (
        isinstance(report, dict) and payload.get("ok") is True
        and isinstance(validation, dict) and validation.get("status") == "passed"
        and report.get("parity_status") == "passed"
        and report.get("failed_count") == 0
        and report.get("wps_launched") is True
        and isinstance(checks, list) and bool(checks)
        and all(isinstance(check, dict) and check.get("passed") is True for check in checks)
        and (expected_scope is None or report.get("scope") == expected_scope)
        and (expected_scope != "nested" or {"read_only_open", "bookmark_names_and_text", "source_unchanged", "implementation_unchanged"} <= check_names)
        and "implementation_unchanged" in check_names
    )
    if not passed:
        return {"status": "failed", "artifact": str(artifact), "reason": "Latest Writer parity report did not pass."}
    fixture, script = workspace / fixture_relative, workspace / SCRIPT
    try:
        fixture_hash, script_hash = _sha256(fixture), _sha256(script)
        code_hashes = implementation_hashes(workspace)
    except OSError as exc:
        return {"status": "stale", "artifact": str(artifact), "reason": str(exc)}
    hashes_match = (
        report.get("source_sha256") == report.get("source_sha256_after") == fixture_hash
        and report.get("audit_script_sha256") == script_hash
        and report.get("implementation_sha256") == report.get("implementation_sha256_after") == code_hashes
    )
    if not hashes_match:
        return {"status": "stale", "artifact": str(artifact), "reason": "Fixture, audit script, or implementation differs from report hashes.",
                "source_sha256": fixture_hash, "audit_script_sha256": script_hash,
                "implementation_sha256": code_hashes}
    if not inclusion.get("included") or not inclusion.get("content_matches"):
        return {"status": "stale_package", "artifact": str(artifact), "reason": "Latest Writer parity report is missing or differs in the package."}
    return {"status": "passed", "artifact": str(artifact), "source_sha256": fixture_hash,
            "audit_script_sha256": script_hash}


def build_sync_package_readiness(
    workspace: str | Path = ".",
    package_path: str | Path = DEFAULT_SYNC_PACKAGE,
    limit: int = 10,
) -> tuple[bool, dict[str, Any], list[dict[str, Any]]]:
    workspace_path = Path(workspace).resolve()
    inspect_ok, inspection, inspect_errors = inspect_sync_package(workspace=workspace_path, package_path=package_path)
    summary_ok, summary, summary_errors = summarize_sync_package(
        workspace=workspace_path,
        package_path=package_path,
        limit=limit,
    )
    coverage_ok, coverage, coverage_errors = build_sync_package_coverage(
        workspace=workspace_path,
        package_path=package_path,
        limit=limit,
    )

    missing_count = int(coverage.get("missing_entry_count", 0) or 0)
    newer_count = int(coverage.get("newer_than_package_count", 0) or 0)
    artifact_inclusion = inspection.get("latest_artifacts", {})
    parity_evidence = _writer_parity_evidence(workspace_path, artifact_inclusion.get("writer_parity", {}), FIXTURE)
    nested_parity_evidence = _writer_parity_evidence(
        workspace_path, artifact_inclusion.get("writer_nested_parity", {}), NESTED_FIXTURE, "nested",
    )
    recovery_drill_package = verify_recovery_drill_package(workspace_path, package_path)
    package = {
        "exists": inspection.get("exists"),
        "readable": inspection.get("readable"),
        "path": inspection.get("package_path"),
        "bytes": inspection.get("bytes"),
        "sha256": inspection.get("sha256"),
        "entry_count": inspection.get("entry_count"),
    }
    checks = [
        {
            "name": "inspection_passed",
            "passed": inspect_ok,
            "details": inspection.get("inspection_status"),
        },
        {
            "name": "summary_passed",
            "passed": summary_ok,
            "details": summary.get("summary_status"),
        },
        {
            "name": "coverage_passed",
            "passed": coverage_ok,
            "details": coverage.get("coverage_status"),
        },
        {
            "name": "no_missing_expected_entries",
            "passed": missing_count == 0,
            "details": missing_count,
        },
        {
            "name": "no_newer_workspace_entries",
            "passed": newer_count == 0,
            "details": newer_count,
        },
        {
            "name": "latest_safe_artifact_included",
            "passed": bool(artifact_inclusion.get("safe", {}).get("included")),
            "details": artifact_inclusion.get("safe"),
        },
        {
            "name": "latest_wps_artifact_included",
            "passed": bool(artifact_inclusion.get("wps", {}).get("included")),
            "details": artifact_inclusion.get("wps"),
        },
        {
            "name": "latest_writer_parity_evidence_passed",
            "passed": parity_evidence["status"] == "passed",
            "details": parity_evidence,
        },
        {
            "name": "latest_writer_nested_parity_evidence_passed",
            "passed": nested_parity_evidence["status"] == "passed",
            "details": nested_parity_evidence,
        },
        {
            "name": "recovery_drill_package_matches",
            "passed": recovery_drill_package["status"] in {"passed", "absent"},
            "details": recovery_drill_package["status"],
        },
    ]
    ok = all(check["passed"] for check in checks)
    result = {
        "workspace": str(workspace_path),
        "package_path": package["path"],
        "read_only": True,
        "launches_wps": False,
        "deletion_performed": False,
        "remote_git_required": False,
        "readiness_status": "passed" if ok else "warning",
        "package": package,
        "latest_artifacts": artifact_inclusion,
        "writer_parity_evidence": parity_evidence,
        "writer_nested_parity_evidence": nested_parity_evidence,
        "recovery_drill_package": recovery_drill_package,
        "root_coverage": coverage.get("root_coverage", {}),
        "top_level_groups": summary.get("top_level_groups", {}),
        "coverage": {
            "changed_entry_count": coverage.get("changed_entry_count", 0),
            "changed_entries": coverage.get("changed_entries", []),
            "duplicate_entry_count": coverage.get("duplicate_entry_count", 0),
            "duplicate_entries": coverage.get("duplicate_entries", []),
            "extra_root_entries": coverage.get("extra_root_entries", []),
            "expected_entry_count": coverage.get("expected_entry_count"),
            "packaged_entry_count": coverage.get("packaged_entry_count"),
            "missing_entry_count": missing_count,
            "extra_root_entry_count": coverage.get("extra_root_entry_count"),
            "newer_than_package_count": newer_count,
            "missing_entries": coverage.get("missing_entries", []),
            "newer_than_package": coverage.get("newer_than_package", []),
        },
        "checks": checks,
    }
    errors = [*inspect_errors, *summary_errors, *coverage_errors]
    return ok, result, errors
