from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _latest_artifact(profile_dir: Path) -> Path | None:
    if not profile_dir.exists():
        return None
    files = sorted((path for path in profile_dir.glob("regression-run-*.json") if path.is_file()), key=lambda item: item.stat().st_mtime)
    return files[-1] if files else None


def _load_artifact(path: Path) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, [{"code": "REGRESSION_ARTIFACT_INVALID_JSON", "message": str(exc), "path": str(path)}]
    except OSError as exc:
        return None, [{"code": "REGRESSION_ARTIFACT_UNREADABLE", "message": str(exc), "path": str(path)}]
    if not isinstance(payload, dict):
        return None, [{"code": "REGRESSION_ARTIFACT_INVALID", "message": "Artifact payload must be a JSON object.", "path": str(path)}]
    return payload, []


def _profile_summary(workspace: Path, profile: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    profile_dir = workspace / "artifacts" / "regression" / profile
    artifact = _latest_artifact(profile_dir)
    if artifact is None:
        return {
            "profile": profile,
            "artifact": None,
            "available": False,
            "passed": False,
            "scenario_count": None,
            "passed_count": None,
            "failed_count": None,
            "result_ids": [],
        }, [{"code": "REGRESSION_ARTIFACT_NOT_FOUND", "message": f"No {profile} regression artifact found."}]

    stat = artifact.stat()
    payload, errors = _load_artifact(artifact)
    regression = payload.get("data", {}).get("regression", {}) if payload else {}
    results = regression.get("results", [])
    failed_count = regression.get("failed_count")
    passed = failed_count == 0 if isinstance(failed_count, int) else False
    return {
        "profile": profile,
        "artifact": {
            "path": str(artifact),
            "name": artifact.name,
            "size_bytes": stat.st_size,
            "last_modified": stat.st_mtime,
        },
        "available": payload is not None,
        "passed": passed,
        "scenario_count": regression.get("scenario_count"),
        "passed_count": regression.get("passed_count"),
        "failed_count": failed_count,
        "include_wps": regression.get("include_wps"),
        "result_ids": [result.get("id") for result in results if isinstance(result, dict)],
    }, errors


def build_regression_evidence(workspace: str | Path = ".") -> tuple[bool, dict[str, Any], list[dict[str, Any]]]:
    workspace_path = Path(workspace).resolve()
    profiles: dict[str, Any] = {}
    errors: list[dict[str, Any]] = []
    for profile in ("safe", "wps"):
        summary, profile_errors = _profile_summary(workspace_path, profile)
        profiles[profile] = summary
        errors.extend(profile_errors)

    required_profiles = ["safe", "wps"]
    missing_profiles = [profile for profile in required_profiles if not profiles[profile]["available"]]
    failed_profiles = [profile for profile in required_profiles if profiles[profile]["available"] and not profiles[profile]["passed"]]
    evidence_status = "passed" if not missing_profiles and not failed_profiles else "failed"
    evidence = {
        "workspace": str(workspace_path),
        "read_only": True,
        "launches_wps": False,
        "profiles": profiles,
        "missing_profiles": missing_profiles,
        "failed_profiles": failed_profiles,
        "evidence_status": evidence_status,
    }
    return evidence_status == "passed", evidence, errors
