from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .mcp_catalog import build_mcp_catalog_snapshot


DEFAULT_MCP_CATALOG_GUARD = "config/mcp_catalog_guard.json"


def _load_guard(path: str | Path) -> tuple[bool, dict[str, Any], list[dict[str, Any]], Path]:
    guard_path = Path(path)
    if not guard_path.exists():
        return False, {}, [{"code": "MCP_CATALOG_GUARD_NOT_FOUND", "message": f"Guard config not found: {guard_path}"}], guard_path
    try:
        guard = json.loads(guard_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, {}, [{"code": "MCP_CATALOG_GUARD_INVALID_JSON", "message": str(exc)}], guard_path
    if not isinstance(guard, dict):
        return False, {}, [{"code": "MCP_CATALOG_GUARD_INVALID", "message": "Guard config must be a JSON object."}], guard_path
    return True, guard, [], guard_path


def _append_scalar_drift(
    drifts: list[dict[str, Any]],
    field: str,
    expected: Any,
    actual: Any,
) -> None:
    if expected != actual:
        drifts.append(
            {
                "field": field,
                "expected": expected,
                "actual": actual,
                "kind": "value_mismatch",
            }
        )


def _append_category_drifts(
    drifts: list[dict[str, Any]],
    expected_counts: dict[str, Any],
    actual_counts: dict[str, int],
) -> None:
    for category in sorted(set(expected_counts) | set(actual_counts)):
        expected = expected_counts.get(category)
        actual = actual_counts.get(category)
        if expected != actual:
            drifts.append(
                {
                    "field": f"category_counts.{category}",
                    "expected": expected,
                    "actual": actual,
                    "kind": "category_count_mismatch",
                }
            )


def build_mcp_catalog_drift_report(
    guard_path: str | Path = DEFAULT_MCP_CATALOG_GUARD,
) -> tuple[bool, dict[str, Any], list[dict[str, Any]]]:
    loaded, guard, errors, resolved_guard_path = _load_guard(guard_path)
    if not loaded:
        return False, {}, errors

    snapshot = build_mcp_catalog_snapshot()
    expected_category_counts = guard.get("expected_category_counts", {})
    if not isinstance(expected_category_counts, dict):
        return False, {}, [
            {
                "code": "MCP_CATALOG_GUARD_INVALID",
                "message": "expected_category_counts must be a JSON object.",
            }
        ]

    drifts: list[dict[str, Any]] = []
    comparisons = {
        "tool_count": (guard.get("expected_tool_count"), snapshot["tool_count"]),
        "mutating_tool_count": (guard.get("expected_mutating_tool_count"), snapshot["mutating_tool_count"]),
        "requires_wps_tool_count": (guard.get("expected_requires_wps_tool_count"), snapshot["requires_wps_tool_count"]),
        "read_only_tool_count": (guard.get("expected_read_only_tool_count"), snapshot["read_only_tool_count"]),
        "safety_notes_missing_count": (
            guard.get("expected_safety_notes_missing_count"),
            snapshot["safety_notes_missing_count"],
        ),
    }
    for field, (expected, actual) in comparisons.items():
        _append_scalar_drift(drifts, field, expected, actual)

    _append_category_drifts(drifts, expected_category_counts, snapshot["category_counts"])

    report = {
        "guard_path": str(resolved_guard_path),
        "guard_schema_version": guard.get("schema_version"),
        "drift_count": len(drifts),
        "review_required": bool(drifts),
        "drifts": drifts,
        "expected": {
            "tool_count": guard.get("expected_tool_count"),
            "mutating_tool_count": guard.get("expected_mutating_tool_count"),
            "requires_wps_tool_count": guard.get("expected_requires_wps_tool_count"),
            "read_only_tool_count": guard.get("expected_read_only_tool_count"),
            "safety_notes_missing_count": guard.get("expected_safety_notes_missing_count"),
            "category_counts": expected_category_counts,
        },
        "current": {
            "tool_count": snapshot["tool_count"],
            "mutating_tool_count": snapshot["mutating_tool_count"],
            "requires_wps_tool_count": snapshot["requires_wps_tool_count"],
            "read_only_tool_count": snapshot["read_only_tool_count"],
            "safety_notes_missing_count": snapshot["safety_notes_missing_count"],
            "category_counts": snapshot["category_counts"],
        },
    }
    return not drifts, report, []
