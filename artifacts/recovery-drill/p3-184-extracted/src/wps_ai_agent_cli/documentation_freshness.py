from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .mcp_schema import list_mcp_tool_schemas
from .tasks import list_tasks


CURRENT_DOC_PATHS = [
    "README.md",
    "docs/MCP_SERVER_CLIENT_CONFIG.md",
    "docs/MCP_TOOL_SCHEMA_DRAFT.md",
    "docs/REGRESSION_MANIFEST.md",
    "docs/PHASE3_RELEASE_READINESS_REFRESH.md",
    "docs/TASK_BOARD.md",
    "config/regression_manifest.json",
    "config/mcp_catalog_guard.json",
]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _line_matches(text: str, pattern: str) -> list[dict[str, Any]]:
    regex = re.compile(pattern)
    matches = []
    for index, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("- 2026-"):
            continue
        if regex.search(line):
            matches.append({"line": index, "text": line})
    return matches


def _json_payload(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def build_documentation_freshness_report(workspace: Path | str = ".") -> dict[str, Any]:
    workspace_path = Path(workspace).resolve()
    tool_count = len(list_mcp_tool_schemas())
    next_tasks = list_tasks(phase="phase3", status="next")
    next_task_ids = [task["id"] for task in next_tasks]
    current_next = next_task_ids[0] if next_task_ids else None
    stale_tool_counts = [str(count) for count in range(max(1, tool_count - 5), tool_count)]
    stale_next_ids = [f"P3-{index:03d}" for index in range(1, 100) if f"P3-{index:03d}" != current_next]

    files: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    for relative in CURRENT_DOC_PATHS:
        path = workspace_path / relative
        text = _read_text(path)
        exists = path.exists()
        file_findings: list[dict[str, Any]] = []
        if exists and text:
            current_context_patterns = [
                r"当前.*(?:工具面|tools/list|MCP).*?(?:" + "|".join(stale_tool_counts) + r")\b",
                r"expected-min-tools\s+(?:" + "|".join(stale_tool_counts) + r")\b",
                r"At least\s+(?:" + "|".join(stale_tool_counts) + r")\s+tools",
                r"当前\s+next\s+为\s+(?:" + "|".join(stale_next_ids) + r")\b",
            ]
            for pattern in current_context_patterns:
                for match in _line_matches(text, pattern):
                    finding = {
                        "path": relative,
                        "line": match["line"],
                        "text": match["text"],
                        "reason": "Line appears to describe current state with an outdated tool count or next task.",
                    }
                    file_findings.append(finding)
                    findings.append(finding)

        files.append(
            {
                "path": relative,
                "exists": exists,
                "scanned": exists,
                "finding_count": len(file_findings),
            }
        )

    manifest = _json_payload(workspace_path / "config" / "regression_manifest.json")
    guard = _json_payload(workspace_path / "config" / "mcp_catalog_guard.json")
    config_checks = [
        {
            "name": "regression_manifest_next_task_current",
            "passed": bool(manifest and current_next and json.dumps(manifest).find(current_next) >= 0),
            "details": current_next,
        },
        {
            "name": "mcp_guard_tool_count_current",
            "passed": bool(guard and guard.get("expected_tool_count") == tool_count),
            "details": {
                "expected_tool_count": guard.get("expected_tool_count") if guard else None,
                "current_tool_count": tool_count,
            },
        },
    ]
    checks = [
        {
            "name": "documents_scanned",
            "passed": all(item["exists"] for item in files),
            "details": [item["path"] for item in files if item["exists"]],
        },
        {
            "name": "no_current_stale_references",
            "passed": not findings,
            "details": findings,
        },
        *config_checks,
    ]

    return {
        "workspace": str(workspace_path),
        "read_only": True,
        "launches_wps": False,
        "deletion_performed": False,
        "freshness_status": "passed" if all(check["passed"] for check in checks) else "warning",
        "current": {
            "mcp_tool_count": tool_count,
            "next_task_ids": next_task_ids,
        },
        "files": files,
        "findings": findings,
        "checks": checks,
    }
