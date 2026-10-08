from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from typing import Any

from .cloud_sync import DEFAULT_SYNC_ROOTS


DEFAULT_SYNC_PACKAGE = "artifacts/cloud-sync/wps-ai-agent-cli-phase3-sync-cli.zip"


def _latest_file(pattern: str, workspace: Path, not_newer_than: float | None = None) -> Path | None:
    candidates = sorted(
        (
            item
            for item in workspace.glob(pattern)
            if not_newer_than is None or item.stat().st_mtime <= not_newer_than
        ),
        key=lambda item: item.stat().st_mtime if item.exists() else 0,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _relative_zip_name(path: Path, workspace: Path) -> str:
    return path.resolve().relative_to(workspace).as_posix()


def inspect_sync_package(
    workspace: str | Path = ".",
    package_path: str | Path = DEFAULT_SYNC_PACKAGE,
) -> tuple[bool, dict[str, Any], list[dict[str, Any]]]:
    workspace_path = Path(workspace).resolve()
    package = Path(package_path)
    if not package.is_absolute():
        package = workspace_path / package

    package_mtime = package.stat().st_mtime if package.exists() else None
    latest_artifacts = {
        "safe": _latest_file("artifacts/regression/safe/regression-run-*.json", workspace_path, package_mtime),
        "wps": _latest_file("artifacts/regression/wps/regression-run-*.json", workspace_path, package_mtime),
        "writer_parity": _latest_file("artifacts/writer-structure-parity/writer-structure-parity-*.json", workspace_path),
        "writer_nested_parity": _latest_file("artifacts/writer-nested-parity/writer-nested-parity-*.json", workspace_path),
    }
    artifact_expectations = {
        name: _relative_zip_name(path, workspace_path) if path else None
        for name, path in latest_artifacts.items()
    }

    errors: list[dict[str, Any]] = []
    entry_names: list[str] = []
    package_readable = False
    parity_content_matches = {"writer_parity": False, "writer_nested_parity": False}
    if package.exists():
        try:
            with zipfile.ZipFile(package) as archive:
                entry_names = sorted(info.filename.replace("\\", "/") for info in archive.infolist())
                for key in parity_content_matches:
                    parity_path = latest_artifacts[key]
                    parity_entry = artifact_expectations[key]
                    if parity_path is not None and parity_entry in entry_names:
                        info = next(item for item in archive.infolist() if item.filename.replace("\\", "/") == parity_entry)
                        parity_content_matches[key] = hashlib.sha256(archive.read(info)).hexdigest().upper() == _sha256(parity_path)
                package_readable = True
        except zipfile.BadZipFile as exc:
            errors.append({"code": "SYNC_PACKAGE_BAD_ZIP", "message": str(exc)})
        except (OSError, RuntimeError) as exc:
            errors.append({"code": "SYNC_PACKAGE_READ_FAILED", "message": str(exc)})
    else:
        errors.append({"code": "SYNC_PACKAGE_MISSING", "message": f"Package not found: {package}"})

    entry_set = set(entry_names)
    root_coverage = {
        root: any(name == root or name.startswith(f"{root}/") for name in entry_names)
        for root in DEFAULT_SYNC_ROOTS
    }
    artifact_inclusion = {
        name: {
            "expected_path": expected,
            "available": expected is not None,
            "included": bool(expected and expected in entry_set),
        }
        for name, expected in artifact_expectations.items()
    }
    for key, matches in parity_content_matches.items():
        artifact_inclusion[key]["content_matches"] = matches
    checks = [
        {"name": "package_exists", "passed": package.exists(), "details": str(package)},
        {"name": "package_readable", "passed": package_readable, "details": str(package)},
        {"name": "package_has_entries", "passed": bool(entry_names), "details": len(entry_names)},
        {
            "name": "expected_roots_present",
            "passed": all(root_coverage.values()),
            "details": root_coverage,
        },
        {
            "name": "latest_safe_artifact_included",
            "passed": artifact_inclusion["safe"]["included"],
            "details": artifact_inclusion["safe"],
        },
        {
            "name": "latest_wps_artifact_included",
            "passed": artifact_inclusion["wps"]["included"],
            "details": artifact_inclusion["wps"],
        },
        {
            "name": "latest_writer_parity_artifact_matches",
            "passed": artifact_inclusion["writer_parity"]["included"] and parity_content_matches["writer_parity"],
            "details": artifact_inclusion["writer_parity"],
        },
        {
            "name": "latest_writer_nested_parity_artifact_matches",
            "passed": artifact_inclusion["writer_nested_parity"]["included"] and parity_content_matches["writer_nested_parity"],
            "details": artifact_inclusion["writer_nested_parity"],
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
        "inspection_status": "passed" if ok else "warning",
        "exists": package.exists(),
        "readable": package_readable,
        "bytes": package.stat().st_size if package.exists() else 0,
        "artifact_cutoff": package_mtime,
        "sha256": _sha256(package) if package.exists() and package_readable else None,
        "entry_count": len(entry_names),
        "expected_roots": list(DEFAULT_SYNC_ROOTS),
        "root_coverage": root_coverage,
        "latest_artifacts": artifact_inclusion,
        "checks": checks,
    }
    return ok, result, errors
