from __future__ import annotations

import hashlib
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

from .cloud_sync import DEFAULT_SYNC_ROOTS
from .sync_package_inspect import DEFAULT_SYNC_PACKAGE, _sha256


def _workspace_sync_files(workspace: Path, cutoff: float | None) -> tuple[list[str], list[str]]:
    expected: list[str] = []
    newer_than_package: list[str] = []
    for root in DEFAULT_SYNC_ROOTS:
        root_path = workspace / root
        if not root_path.exists():
            continue
        for path in sorted(root_path.rglob("*")):
            if not path.is_file():
                continue
            if path.name.startswith("~$"):
                continue
            relative_parts = path.relative_to(workspace).parts
            if "__pycache__" in relative_parts:
                continue
            relative = path.relative_to(workspace).as_posix()
            if cutoff is not None and path.stat().st_mtime > cutoff:
                newer_than_package.append(relative)
            else:
                expected.append(relative)
    return expected, newer_than_package


def build_sync_package_coverage(
    workspace: str | Path = ".",
    package_path: str | Path = DEFAULT_SYNC_PACKAGE,
    limit: int = 20,
) -> tuple[bool, dict[str, Any], list[dict[str, Any]]]:
    workspace_path = Path(workspace).resolve()
    package = Path(package_path)
    if not package.is_absolute():
        package = workspace_path / package

    errors: list[dict[str, Any]] = []
    package_readable = False
    entry_names: set[str] = set()
    changed_entries: list[str] = []
    duplicate_entries: list[str] = []
    workspace_entries, _ = _workspace_sync_files(workspace_path, None)
    workspace_set = set(workspace_entries)
    if package.exists():
        try:
            with zipfile.ZipFile(package) as archive:
                entries = [info for info in archive.infolist() if not info.is_dir()]
                names = [info.filename.replace("\\", "/") for info in entries]
                entry_names = set(names)
                duplicate_entries = sorted(name for name, count in Counter(names).items() if count > 1)
                # Only open workspace paths enumerated locally, never archive-supplied paths.
                for info, name in zip(entries, names):
                    if name not in workspace_set:
                        continue
                    digest = hashlib.sha256()
                    with archive.open(info) as stream:
                        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                            digest.update(chunk)
                    if digest.hexdigest().upper() != _sha256(workspace_path / name):
                        changed_entries.append(name)
                package_readable = True
        except zipfile.BadZipFile as exc:
            errors.append({"code": "SYNC_PACKAGE_BAD_ZIP", "message": str(exc)})
        except (OSError, RuntimeError, NotImplementedError) as exc:
            errors.append({"code": "SYNC_PACKAGE_READ_FAILED", "message": str(exc)})
    else:
        errors.append({"code": "SYNC_PACKAGE_MISSING", "message": f"Package not found: {package}"})

    package_mtime = package.stat().st_mtime if package.exists() else None
    expected_entries, newer_than_package = _workspace_sync_files(workspace_path, package_mtime)
    expected_set = set(expected_entries)
    missing_entries = sorted(expected_set - entry_names)
    extra_root_entries = sorted(
        entry
        for entry in entry_names
        if entry.split("/", 1)[0] in DEFAULT_SYNC_ROOTS and entry not in workspace_set
    )
    root_coverage = {
        root: {
            "expected": sum(1 for item in expected_entries if item == root or item.startswith(f"{root}/")),
            "packaged": sum(1 for item in entry_names if item == root or item.startswith(f"{root}/")),
        }
        for root in DEFAULT_SYNC_ROOTS
    }
    checks = [
        {"name": "package_exists", "passed": package.exists(), "details": str(package)},
        {"name": "package_readable", "passed": package_readable, "details": str(package)},
        {"name": "expected_entries_available", "passed": bool(expected_entries), "details": len(expected_entries)},
        {"name": "no_missing_expected_entries", "passed": not missing_entries, "details": len(missing_entries)},
        {"name": "content_matches_workspace", "passed": not changed_entries, "details": len(changed_entries)},
        {"name": "no_obsolete_root_entries", "passed": not extra_root_entries, "details": len(extra_root_entries)},
        {"name": "no_duplicate_entries", "passed": not duplicate_entries, "details": len(duplicate_entries)},
        {
            "name": "expected_roots_covered",
            "passed": all(details["packaged"] >= details["expected"] for details in root_coverage.values()),
            "details": root_coverage,
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
        "coverage_status": "passed" if ok else "warning",
        "exists": package.exists(),
        "readable": package_readable,
        "bytes": package.stat().st_size if package.exists() else 0,
        "sha256": _sha256(package) if package.exists() and package_readable else None,
        "artifact_cutoff": package_mtime,
        "expected_entry_count": len(expected_entries),
        "packaged_entry_count": len(entry_names),
        "missing_entry_count": len(missing_entries),
        "extra_root_entry_count": len(extra_root_entries),
        "newer_than_package_count": len(newer_than_package),
        "changed_entry_count": len(changed_entries),
        "duplicate_entry_count": len(duplicate_entries),
        "changed_entries": sorted(changed_entries)[: max(0, limit)],
        "duplicate_entries": duplicate_entries[: max(0, limit)],
        "missing_entries": missing_entries[: max(0, limit)],
        "extra_root_entries": extra_root_entries[: max(0, limit)],
        "newer_than_package": newer_than_package[: max(0, limit)],
        "truncated": {
            "changed_entries": len(changed_entries) > max(0, limit),
            "duplicate_entries": len(duplicate_entries) > max(0, limit),
            "missing_entries": len(missing_entries) > max(0, limit),
            "extra_root_entries": len(extra_root_entries) > max(0, limit),
            "newer_than_package": len(newer_than_package) > max(0, limit),
        },
        "root_coverage": root_coverage,
        "checks": checks,
    }
    return ok, result, errors
