from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _artifact_files(profile_dir: Path, limit: int) -> list[Path]:
    if not profile_dir.exists():
        return []
    files = sorted(
        (path for path in profile_dir.glob("regression-run-*.json") if path.is_file()),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    return files[:limit]


def _artifact_entry(path: Path) -> dict[str, Any]:
    stat = path.stat()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "path": str(path),
            "name": path.name,
            "size_bytes": stat.st_size,
            "last_modified": stat.st_mtime,
            "available": False,
            "passed": False,
            "error": str(exc),
        }

    regression = payload.get("data", {}).get("regression", {}) if isinstance(payload, dict) else {}
    results = regression.get("results", [])
    failed_count = regression.get("failed_count")
    return {
        "path": str(path),
        "name": path.name,
        "size_bytes": stat.st_size,
        "last_modified": stat.st_mtime,
        "available": True,
        "passed": failed_count == 0 if isinstance(failed_count, int) else False,
        "profile": regression.get("profile"),
        "include_wps": regression.get("include_wps"),
        "scenario_count": regression.get("scenario_count"),
        "passed_count": regression.get("passed_count"),
        "failed_count": failed_count,
        "result_ids": [result.get("id") for result in results if isinstance(result, dict)],
    }


def _profile_history(workspace: Path, profile: str, limit: int) -> dict[str, Any]:
    entries = [_artifact_entry(path) for path in _artifact_files(workspace / "artifacts" / "regression" / profile, limit)]
    failed_entries = [entry for entry in entries if not entry["passed"]]
    return {
        "profile": profile,
        "artifact_count": len(entries),
        "latest": entries[0] if entries else None,
        "entries": entries,
        "recent_passed_count": sum(1 for entry in entries if entry["passed"]),
        "recent_failed_count": len(failed_entries),
        "recent_all_passed": bool(entries) and not failed_entries,
    }


def build_regression_history(workspace: Path | str = ".", limit: int = 5) -> dict[str, Any]:
    workspace_path = Path(workspace).resolve()
    safe_limit = max(1, limit)
    profiles = {
        "safe": _profile_history(workspace_path, "safe", safe_limit),
        "wps": _profile_history(workspace_path, "wps", safe_limit),
    }
    checks = [
        {
            "name": "safe_history_available",
            "passed": profiles["safe"]["artifact_count"] >= 1,
            "details": profiles["safe"]["artifact_count"],
        },
        {
            "name": "wps_history_available",
            "passed": profiles["wps"]["artifact_count"] >= 1,
            "details": profiles["wps"]["artifact_count"],
        },
        {
            "name": "latest_safe_passed",
            "passed": bool(profiles["safe"]["latest"] and profiles["safe"]["latest"]["passed"]),
            "details": profiles["safe"]["latest"]["name"] if profiles["safe"]["latest"] else None,
        },
        {
            "name": "latest_wps_passed",
            "passed": bool(profiles["wps"]["latest"] and profiles["wps"]["latest"]["passed"]),
            "details": profiles["wps"]["latest"]["name"] if profiles["wps"]["latest"] else None,
        },
    ]
    return {
        "workspace": str(workspace_path),
        "read_only": True,
        "launches_wps": False,
        "deletion_performed": False,
        "limit": safe_limit,
        "history_status": "passed" if all(check["passed"] for check in checks) else "warning",
        "profiles": profiles,
        "checks": checks,
    }
