from __future__ import annotations

import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any

from .cloud_sync import DEFAULT_SYNC_ROOTS
from .sync_package_inspect import DEFAULT_SYNC_PACKAGE, _sha256


def summarize_sync_package(
    workspace: str | Path = ".",
    package_path: str | Path = DEFAULT_SYNC_PACKAGE,
    limit: int = 10,
) -> tuple[bool, dict[str, Any], list[dict[str, Any]]]:
    workspace_path = Path(workspace).resolve()
    package = Path(package_path)
    if not package.is_absolute():
        package = workspace_path / package

    errors: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    package_readable = False
    if package.exists():
        try:
            with zipfile.ZipFile(package) as archive:
                for info in archive.infolist():
                    name = info.filename.replace("\\", "/")
                    entries.append(
                        {
                            "name": name,
                            "top_level": name.split("/", 1)[0] if name else "",
                            "uncompressed_bytes": info.file_size,
                            "compressed_bytes": info.compress_size,
                        }
                    )
                package_readable = True
        except zipfile.BadZipFile as exc:
            errors.append({"code": "SYNC_PACKAGE_BAD_ZIP", "message": str(exc)})
        except OSError as exc:
            errors.append({"code": "SYNC_PACKAGE_READ_FAILED", "message": str(exc)})
    else:
        errors.append({"code": "SYNC_PACKAGE_MISSING", "message": f"Package not found: {package}"})

    groups: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"entry_count": 0, "uncompressed_bytes": 0, "compressed_bytes": 0, "sample_entries": []}
    )
    for entry in sorted(entries, key=lambda item: item["name"]):
        group = groups[entry["top_level"]]
        group["entry_count"] += 1
        group["uncompressed_bytes"] += entry["uncompressed_bytes"]
        group["compressed_bytes"] += entry["compressed_bytes"]
        if len(group["sample_entries"]) < max(0, limit):
            group["sample_entries"].append(entry["name"])

    top_level_groups = {
        name: groups[name]
        for name in sorted(groups)
    }
    expected_root_groups = {
        root: root in top_level_groups
        for root in DEFAULT_SYNC_ROOTS
    }
    largest_entries = sorted(
        entries,
        key=lambda item: (item["uncompressed_bytes"], item["name"]),
        reverse=True,
    )[: max(0, limit)]
    artifact_entries = [
        entry["name"]
        for entry in sorted(entries, key=lambda item: item["name"])
        if entry["name"].startswith("artifacts/")
    ]

    checks = [
        {"name": "package_exists", "passed": package.exists(), "details": str(package)},
        {"name": "package_readable", "passed": package_readable, "details": str(package)},
        {"name": "package_has_entries", "passed": bool(entries), "details": len(entries)},
        {
            "name": "expected_root_groups_present",
            "passed": all(expected_root_groups.values()),
            "details": expected_root_groups,
        },
        {
            "name": "artifact_entries_present",
            "passed": bool(artifact_entries),
            "details": len(artifact_entries),
        },
    ]
    ok = all(check["passed"] for check in checks)
    result = {
        "workspace": str(workspace_path),
        "package_path": str(package),
        "read_only": True,
        "launches_wps": False,
        "deletion_performed": False,
        "remote_git_required": False,
        "summary_status": "passed" if ok else "warning",
        "exists": package.exists(),
        "readable": package_readable,
        "bytes": package.stat().st_size if package.exists() else 0,
        "sha256": _sha256(package) if package.exists() and package_readable else None,
        "entry_count": len(entries),
        "top_level_groups": top_level_groups,
        "expected_root_groups": expected_root_groups,
        "artifact_entry_count": len(artifact_entries),
        "artifact_entries": artifact_entries[: max(0, limit)],
        "largest_entries": largest_entries,
        "checks": checks,
    }
    return ok, result, errors
