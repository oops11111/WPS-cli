from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from .cleanup_plan import build_cleanup_plan
from .project_status import build_project_status


def _group_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"category": "", "count": 0, "size_bytes": 0, "paths": []})
    for candidate in candidates:
        category = str(candidate.get("category", "uncategorized"))
        item = grouped[category]
        item["category"] = category
        item["count"] += 1
        item["size_bytes"] += int(candidate.get("size_bytes", 0))
        item["paths"].append(candidate.get("path"))
    return sorted(grouped.values(), key=lambda item: item["category"])


def build_artifact_retention_summary(workspace: Path | str = ".") -> dict[str, Any]:
    workspace_path = Path(workspace).resolve()
    cleanup = build_cleanup_plan(workspace_path)
    project_status = build_project_status(workspace_path)
    sync_package = project_status["sync_package"]

    preserved_evidence = cleanup["preserved_evidence"]
    candidates = cleanup["candidates"]
    checks = [
        {
            "name": "cleanup_plan_read_only",
            "passed": cleanup["read_only"] is True,
            "details": "cleanup-plan is read-only.",
        },
        {
            "name": "no_deletion_performed",
            "passed": cleanup["deletion_performed"] is False,
            "details": "No cleanup action was executed.",
        },
        {
            "name": "sync_package_retained",
            "passed": bool(sync_package["exists"] and sync_package["sha256"]),
            "details": sync_package,
        },
        {
            "name": "latest_regression_evidence_retained",
            "passed": len(preserved_evidence) >= 2,
            "details": [item["category"] for item in preserved_evidence],
        },
        {
            "name": "cleanup_candidates_require_approval",
            "passed": all(candidate.get("requires_user_approval") for candidate in candidates),
            "details": {
                "candidate_count": cleanup["candidate_count"],
                "total_candidate_bytes": cleanup["total_candidate_bytes"],
            },
        },
    ]

    return {
        "workspace": str(workspace_path),
        "read_only": True,
        "launches_wps": False,
        "deletion_performed": False,
        "retention_status": "passed" if all(check["passed"] for check in checks) else "warning",
        "review_required": cleanup["candidate_count"] > 0,
        "checks": checks,
        "current_sync_package": sync_package,
        "preserved_evidence": preserved_evidence,
        "candidate_summary": {
            "candidate_count": cleanup["candidate_count"],
            "total_candidate_bytes": cleanup["total_candidate_bytes"],
            "categories": _group_candidates(candidates),
        },
        "approval_policy": {
            "approval_required": cleanup["approval_required"],
            "default_action": "keep_until_approved",
            "deletion_allowed_without_user_approval": False,
            "approval_guidance": (
                "Regenerate cleanup-plan and approve exact paths or categories before any separate cleanup execution."
            ),
        },
        "remote_git_required": project_status["remote_git_required"],
    }
