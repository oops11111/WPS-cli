from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .state_store import StateCorruptError, atomic_write_json, read_json_state


COMPONENT_NAMES = ("writer", "spreadsheets", "presentation")
SCHEMA_VERSION = 1
_MAX_VERSION_CHARS = 64
_MAX_SEGMENTS = 8
_MAX_SEGMENT_DIGITS = 9


def version_state_path(workspace: str | Path) -> Path:
    return Path(workspace) / ".wps-agent" / "wps-versions.json"


def parse_wps_version(value: str) -> tuple[int, ...] | None:
    text = value.strip()
    if not text or len(text) > _MAX_VERSION_CHARS:
        return None
    parts = text.split(".")
    if len(parts) > _MAX_SEGMENTS:
        return None
    numbers: list[int] = []
    for part in parts:
        if not part.isdigit() or len(part) > _MAX_SEGMENT_DIGITS:
            return None
        numbers.append(int(part))
    return tuple(numbers)


def compare_version_text(current: str, baseline: str) -> str | None:
    current_parts = parse_wps_version(current)
    baseline_parts = parse_wps_version(baseline)
    if current_parts is None or baseline_parts is None:
        return None
    return _compare_parts(current_parts, baseline_parts)


def compare_wps_versions(
    workspace: str | Path,
    versions: dict[str, str | None],
    *,
    record: bool,
) -> tuple[bool, dict[str, Any], list[dict[str, Any]]]:
    unknown = sorted(set(versions) - set(COMPONENT_NAMES))
    if unknown:
        return False, {}, [{
            "code": "WPS_VERSION_COMPONENT_UNKNOWN",
            "message": "Version comparison only accepts writer, spreadsheets, and presentation.",
            "details": {"components": unknown},
        }]

    path = version_state_path(workspace)
    try:
        payload = read_json_state(path, {"schema_version": SCHEMA_VERSION, "components": {}})
    except StateCorruptError as exc:
        return False, {"state_path": str(path)}, [{
            "code": exc.code,
            "message": "The WPS version baseline is not valid JSON and was quarantined when possible.",
            "details": exc.details,
        }]
    except OSError:
        return False, {"state_path": str(path)}, [{
            "code": "WPS_VERSION_STATE_UNREADABLE",
            "message": "The WPS version baseline could not be read.",
        }]

    baseline, problem = _baseline_versions(payload)
    if baseline is None:
        return False, {"state_path": str(path)}, [{
            "code": "WPS_VERSION_STATE_INVALID",
            "message": "The WPS version baseline does not use the supported object shape.",
            "details": {"reason": problem},
        }]

    observed = {name: _blank_to_none(versions.get(name)) for name in COMPONENT_NAMES}
    comparisons = [_comparison(name, observed[name], baseline[name]) for name in COMPONENT_NAMES]
    persisted = False
    if record:
        updated = _recordable_updates(observed)
        if updated:
            merged = dict(payload.get("components") or {})
            observed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            for name, version in updated.items():
                merged[name] = {"observed_at": observed_at, "version": version}
            try:
                atomic_write_json(path, {"schema_version": SCHEMA_VERSION, "components": merged})
            except OSError:
                return False, {"state_path": str(path), "comparisons": comparisons}, [{
                    "code": "WPS_VERSION_STATE_UNWRITABLE",
                    "message": "The WPS version baseline could not be written.",
                }]
            persisted = True

    return True, {
        "state_path": str(path),
        "record_requested": record,
        "persisted": persisted,
        "comparisons": comparisons,
    }, []


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _baseline_versions(payload: dict[str, Any]) -> tuple[dict[str, str | None] | None, str | None]:
    if payload.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
        return None, "unsupported_schema"
    components = payload.get("components", {})
    if not isinstance(components, dict) or set(components) - set(COMPONENT_NAMES):
        return None, "invalid_components"
    versions: dict[str, str | None] = {}
    for name in COMPONENT_NAMES:
        entry = components.get(name)
        if entry is None:
            versions[name] = None
            continue
        if not isinstance(entry, dict):
            return None, "invalid_component"
        version = entry.get("version")
        if version is None:
            versions[name] = None
            continue
        if not isinstance(version, str):
            return None, "invalid_version"
        versions[name] = version
    return versions, None


def _comparison(name: str, current: str | None, baseline: str | None) -> dict[str, Any]:
    current_parts = None if current is None else parse_wps_version(current)
    baseline_parts = None if baseline is None else parse_wps_version(baseline)
    if current is not None and current_parts is None:
        relation = "unparsable_current"
    elif baseline is not None and baseline_parts is None:
        relation = "unparsable_baseline"
    elif current is None and baseline is None:
        relation = "both_absent"
    elif baseline is None:
        relation = "absent_baseline"
    elif current is None:
        relation = "absent_current"
    else:
        relation = _compare_parts(current_parts or (), baseline_parts or ())
    return {
        "component": name,
        "current": current,
        "baseline": baseline,
        "relation": relation,
    }


def _compare_parts(current: tuple[int, ...], baseline: tuple[int, ...]) -> str:
    left = _strip_trailing_zeros(current)
    right = _strip_trailing_zeros(baseline)
    if left == right:
        return "equal"
    return "newer" if left > right else "older"


def _strip_trailing_zeros(parts: tuple[int, ...]) -> tuple[int, ...]:
    trimmed = list(parts)
    while len(trimmed) > 1 and trimmed[-1] == 0:
        trimmed.pop()
    return tuple(trimmed)


def _recordable_updates(observed: dict[str, str | None]) -> dict[str, str]:
    updates: dict[str, str] = {}
    for name, version in observed.items():
        if version is not None and parse_wps_version(version) is not None:
            updates[name] = version
    return updates
