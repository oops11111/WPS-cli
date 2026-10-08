from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any
import zipfile

from .sessions import file_identity


_COMPONENT_SUFFIXES = {"writer": ".docx", "spreadsheets": ".xlsx"}
_MAX_FILE_BYTES = 64 * 1024 * 1024


def verify_recovery_drill_artifacts(workspace: str | Path = ".") -> dict[str, Any]:
    workspace_path = Path(workspace).resolve()
    root = workspace_path / "artifacts" / "recovery-drill" / "p3-181-final"
    if not root.exists():
        return {"status": "absent", "root": str(root), "components": []}
    if not root.resolve().is_relative_to(workspace_path):
        return {"status": "failed", "root": str(root), "components": [],
                "errors": ["ARTIFACT_ROOT_OUTSIDE_WORKSPACE"]}

    components = []
    for component, suffix in _COMPONENT_SUFFIXES.items():
        directory = root / component
        manifest_path = directory / "manifest.json"
        errors = []
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = {}
            errors.append("MANIFEST_UNAVAILABLE")
        if not isinstance(manifest, dict):
            manifest = {}
            errors.append("MANIFEST_INVALID")
        if manifest.get("component") != component or manifest.get("status") != "ambiguous" or manifest.get("main_operation_recorded") is not False:
            errors.append("MANIFEST_STATE_INVALID")
        hashes = {}
        for role in ("current", "backup"):
            path = directory / f"{role}{suffix}"
            declared = manifest.get(f"{role}_path")
            if not isinstance(declared, str) or (workspace_path / declared).resolve() != path.resolve():
                errors.append(f"{role.upper()}_PATH_INVALID")
            if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
                errors.append(f"{role.upper()}_FILE_UNAVAILABLE")
                continue
            try:
                size = path.stat().st_size
            except OSError:
                errors.append(f"{role.upper()}_FILE_UNAVAILABLE")
                continue
            if size > _MAX_FILE_BYTES:
                errors.append(f"{role.upper()}_FILE_TOO_LARGE")
                continue
            try:
                actual = file_identity(path)["source_sha256"]
            except OSError:
                errors.append(f"{role.upper()}_HASH_UNAVAILABLE")
                continue
            hashes[role] = actual
            if manifest.get(f"{role}_sha256") != actual:
                errors.append(f"{role.upper()}_HASH_MISMATCH")
        if len(hashes) == 2 and hashes["current"] == hashes["backup"]:
            errors.append("CURRENT_EQUALS_BACKUP")
        components.append({
            "component": component,
            "status": "passed" if not errors else "failed",
            "current_sha256": hashes.get("current"),
            "backup_sha256": hashes.get("backup"),
            "errors": errors,
        })
    return {
        "status": "passed" if all(item["status"] == "passed" for item in components) else "failed",
        "root": str(root),
        "components": components,
    }


def verify_recovery_drill_package(workspace: str | Path, package_path: str | Path) -> dict[str, Any]:
    workspace_path = Path(workspace).resolve()
    evidence = verify_recovery_drill_artifacts(workspace_path)
    if evidence["status"] != "passed":
        return {"status": evidence["status"], "entries": [], "evidence_status": evidence["status"]}
    root = workspace_path / "artifacts" / "recovery-drill" / "p3-181-final"
    package = Path(package_path)
    if not package.is_absolute():
        package = workspace_path / package
    entries = []
    try:
        with zipfile.ZipFile(package) as archive:
            infos = archive.infolist()
            for component, suffix in _COMPONENT_SUFFIXES.items():
                directory = root / component
                for filename in ("manifest.json", f"current{suffix}", f"backup{suffix}"):
                    source = directory / filename
                    name = source.relative_to(workspace_path).as_posix()
                    matches = [info for info in infos if info.filename.replace("\\", "/") == name]
                    matched = False
                    if len(matches) == 1 and matches[0].file_size <= _MAX_FILE_BYTES:
                        digest = hashlib.sha256()
                        with archive.open(matches[0]) as stream:
                            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                                digest.update(chunk)
                        matched = digest.hexdigest().upper() == file_identity(source)["source_sha256"]
                    entries.append({"path": name, "content_matches": matched})
    except (OSError, RuntimeError, zipfile.BadZipFile):
        return {"status": "failed", "entries": entries, "evidence_status": evidence["status"]}
    return {
        "status": "passed" if len(entries) == 6 and all(item["content_matches"] for item in entries) else "failed",
        "entries": entries,
        "evidence_status": evidence["status"],
    }
