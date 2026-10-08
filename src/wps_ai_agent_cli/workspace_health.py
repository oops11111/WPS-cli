from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .cleanup_approval import build_cleanup_approval_manifest
from .project_status import build_project_status


def _age_seconds(item: dict[str, Any] | None) -> float | None:
    if not item or item.get("last_modified") is None:
        return None
    return round(time.time() - float(item["last_modified"]), 3)


def build_workspace_health(workspace: Path | str = ".") -> dict[str, Any]:
    status = build_project_status(workspace)
    approval = build_cleanup_approval_manifest(workspace)
    latest = status["latest_artifacts"]
    sync_package = status["sync_package"]
    cleanup = status["cleanup"]

    checks = [
        {
            "name": "next_task_available",
            "passed": len(status["next_tasks"]) >= 1,
            "details": [task["id"] for task in status["next_tasks"]],
        },
        {
            "name": "safe_regression_artifact_available",
            "passed": latest["safe_regression"] is not None,
            "details": latest["safe_regression"]["name"] if latest["safe_regression"] else None,
        },
        {
            "name": "sync_package_available",
            "passed": bool(sync_package["exists"]),
            "details": sync_package["path"],
        },
        {
            "name": "cleanup_read_only",
            "passed": cleanup["read_only"] and not cleanup["deletion_performed"],
            "details": cleanup,
        },
        {
            "name": "remote_git_not_required",
            "passed": status["remote_git_required"] is False,
            "details": "Local-only workflow.",
        },
    ]
    health_status = "passed" if all(check["passed"] for check in checks) else "warning"

    return {
        "workspace": status["workspace"],
        "health_status": health_status,
        "checks": checks,
        "next_tasks": status["next_tasks"],
        "mcp_tool_count": status["mcp_tool_count"],
        "cleanup": {
            **cleanup,
            "approval_category_count": len(approval["categories"]),
            "approval_categories": [category["category"] for category in approval["categories"]],
        },
        "latest_artifacts": {
            **latest,
            "safe_regression_age_seconds": _age_seconds(latest["safe_regression"]),
            "wps_regression_age_seconds": _age_seconds(latest["wps_regression"]),
            "local_repro_age_seconds": _age_seconds(latest["local_repro"]),
        },
        "sync_package": sync_package,
        "remote_git_required": status["remote_git_required"],
    }
