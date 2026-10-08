from __future__ import annotations

from pathlib import Path
from typing import Any

from .mcp_catalog_drift import build_mcp_catalog_drift_report
from .project_status import build_project_status
from .recovery_drill_evidence import verify_recovery_drill_artifacts
from .regression_evidence import build_regression_evidence
from .workspace_health import build_workspace_health


def build_local_handoff_summary(workspace: str | Path = ".") -> tuple[bool, dict[str, Any], list[dict[str, Any]]]:
    workspace_path = Path(workspace).resolve()
    project_status = build_project_status(workspace_path)
    workspace_health = build_workspace_health(workspace_path)
    regression_ok, regression_evidence, regression_errors = build_regression_evidence(workspace_path)
    drift_ok, catalog_drift, drift_errors = build_mcp_catalog_drift_report()
    recovery_drill = verify_recovery_drill_artifacts(workspace_path)

    sync_package = project_status["sync_package"]
    cleanup = project_status["cleanup"]
    checks = [
        {
            "name": "workspace_health_passed",
            "passed": workspace_health["health_status"] == "passed",
            "details": workspace_health["health_status"],
        },
        {
            "name": "regression_evidence_passed",
            "passed": regression_ok,
            "details": regression_evidence.get("evidence_status"),
        },
        {
            "name": "mcp_catalog_drift_absent",
            "passed": drift_ok,
            "details": catalog_drift.get("drift_count") if catalog_drift else None,
        },
        {
            "name": "sync_package_available",
            "passed": bool(sync_package["exists"] and sync_package["sha256"]),
            "details": sync_package,
        },
        {
            "name": "cleanup_read_only",
            "passed": cleanup["read_only"] and not cleanup["deletion_performed"],
            "details": cleanup,
        },
        {
            "name": "remote_git_not_required",
            "passed": project_status["remote_git_required"] is False,
            "details": "Local-only workflow.",
        },
        {
            "name": "recovery_drill_evidence_valid",
            "passed": recovery_drill["status"] != "failed",
            "details": recovery_drill["status"],
        },
    ]
    handoff_status = "passed" if all(check["passed"] for check in checks) else "warning"
    summary = {
        "workspace": str(workspace_path),
        "read_only": True,
        "launches_wps": False,
        "handoff_status": handoff_status,
        "checks": checks,
        "next_tasks": project_status["next_tasks"],
        "mcp_tool_count": project_status["mcp_tool_count"],
        "sync_package": sync_package,
        "cleanup": cleanup,
        "remote_git_required": project_status["remote_git_required"],
        "workspace_health": {
            "health_status": workspace_health["health_status"],
            "latest_artifacts": workspace_health["latest_artifacts"],
        },
        "regression_evidence": {
            "evidence_status": regression_evidence.get("evidence_status"),
            "profiles": regression_evidence.get("profiles", {}),
        },
        "mcp_catalog_drift": {
            "drift_count": catalog_drift.get("drift_count") if catalog_drift else None,
            "review_required": catalog_drift.get("review_required") if catalog_drift else None,
            "guard_path": catalog_drift.get("guard_path") if catalog_drift else None,
        },
        "recovery_drill_evidence": recovery_drill,
    }
    return handoff_status == "passed", summary, [*regression_errors, *drift_errors]
