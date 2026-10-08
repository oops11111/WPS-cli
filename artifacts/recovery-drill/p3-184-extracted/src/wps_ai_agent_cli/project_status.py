from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .cleanup_plan import build_cleanup_plan
from .mcp_schema import list_mcp_tool_schemas
from .tasks import list_tasks


def _latest_file(root: Path, pattern: str) -> dict[str, Any] | None:
    if not root.exists():
        return None
    files = sorted((path for path in root.glob(pattern) if path.is_file()), key=lambda item: item.stat().st_mtime)
    if not files:
        return None
    latest = files[-1]
    stat = latest.stat()
    return {
        "path": str(latest),
        "name": latest.name,
        "size_bytes": stat.st_size,
        "last_modified": stat.st_mtime,
    }


def _sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest().upper()


def build_project_status(workspace: Path | str = ".") -> dict[str, Any]:
    workspace_path = Path(workspace).resolve()
    cleanup = build_cleanup_plan(workspace_path)
    sync_package = workspace_path / "artifacts" / "cloud-sync" / "wps-ai-agent-cli-phase3-sync-cli.zip"

    return {
        "workspace": str(workspace_path),
        "phase": "phase3",
        "next_tasks": list_tasks(phase="phase3", status="next"),
        "mcp_tool_count": len(list_mcp_tool_schemas()),
        "cleanup": {
            "read_only": cleanup["read_only"],
            "deletion_performed": cleanup["deletion_performed"],
            "candidate_count": cleanup["candidate_count"],
            "total_candidate_bytes": cleanup["total_candidate_bytes"],
            "approval_required": cleanup["approval_required"],
        },
        "latest_artifacts": {
            "safe_regression": _latest_file(workspace_path / "artifacts" / "regression" / "safe", "regression-run-*.json"),
            "wps_regression": _latest_file(workspace_path / "artifacts" / "regression" / "wps", "regression-run-*.json"),
            "local_repro": _latest_file(workspace_path / "artifacts" / "local-repro", "local-repro-*.json"),
        },
        "sync_package": {
            "path": str(sync_package),
            "exists": sync_package.exists(),
            "sha256": _sha256(sync_package),
            "size_bytes": sync_package.stat().st_size if sync_package.exists() else None,
        },
        "remote_git_required": False,
    }
