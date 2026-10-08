from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any

from .cloud_sync import DEFAULT_SYNC_ROOTS
from .sync_package_inspect import DEFAULT_SYNC_PACKAGE, _sha256


def build_sync_package_manifest(
    workspace: str | Path = ".",
    package_path: str | Path = DEFAULT_SYNC_PACKAGE,
    prefix: str | None = None,
    limit: int = 50,
) -> tuple[bool, dict[str, Any], list[dict[str, Any]]]:
    workspace_path = Path(workspace).resolve()
    package = Path(package_path)
    if not package.is_absolute():
        package = workspace_path / package

    normalized_prefix = (prefix or "").replace("\\", "/").strip("/")
    if normalized_prefix:
        normalized_prefix = f"{normalized_prefix}/"

    errors: list[dict[str, Any]] = []
    all_entries: list[dict[str, Any]] = []
    package_readable = False
    if package.exists():
        try:
            with zipfile.ZipFile(package) as archive:
                for info in archive.infolist():
                    name = info.filename.replace("\\", "/")
                    all_entries.append(
                        {
                            "name": name,
                            "top_level": name.split("/", 1)[0] if name else "",
                            "uncompressed_bytes": info.file_size,
                            "compressed_bytes": info.compress_size,
                            "is_dir": info.is_dir(),
                        }
                    )
                package_readable = True
        except zipfile.BadZipFile as exc:
            errors.append({"code": "SYNC_PACKAGE_BAD_ZIP", "message": str(exc)})
        except OSError as exc:
            errors.append({"code": "SYNC_PACKAGE_READ_FAILED", "message": str(exc)})
    else:
        errors.append({"code": "SYNC_PACKAGE_MISSING", "message": f"Package not found: {package}"})

    matching_entries = [
        entry
        for entry in sorted(all_entries, key=lambda item: item["name"])
        if not normalized_prefix or entry["name"].startswith(normalized_prefix)
    ]
    limited_entries = matching_entries[: max(0, limit)]
    expected_roots_present = {
        root: any(entry["name"] == root or entry["name"].startswith(f"{root}/") for entry in all_entries)
        for root in DEFAULT_SYNC_ROOTS
    }
    checks = [
        {"name": "package_exists", "passed": package.exists(), "details": str(package)},
        {"name": "package_readable", "passed": package_readable, "details": str(package)},
        {"name": "package_has_entries", "passed": bool(all_entries), "details": len(all_entries)},
        {
            "name": "expected_roots_present",
            "passed": all(expected_roots_present.values()),
            "details": expected_roots_present,
        },
        {
            "name": "prefix_matches_entries",
            "passed": bool(matching_entries) if normalized_prefix else True,
            "details": {"prefix": normalized_prefix, "match_count": len(matching_entries)},
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
        "manifest_status": "passed" if ok else "warning",
        "exists": package.exists(),
        "readable": package_readable,
        "bytes": package.stat().st_size if package.exists() else 0,
        "sha256": _sha256(package) if package.exists() and package_readable else None,
        "entry_count": len(all_entries),
        "prefix": normalized_prefix,
        "match_count": len(matching_entries),
        "returned_count": len(limited_entries),
        "limit": max(0, limit),
        "entries": limited_entries,
        "truncated": len(matching_entries) > len(limited_entries),
        "expected_roots_present": expected_roots_present,
        "checks": checks,
    }
    return ok, result, errors
