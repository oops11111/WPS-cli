from __future__ import annotations

from collections import Counter
from typing import Any

from .mcp_schema import SCHEMA_VERSION, list_mcp_tool_schemas


def build_mcp_catalog_snapshot() -> dict[str, Any]:
    tools = list_mcp_tool_schemas()
    category_counts = Counter(schema["category"] for schema in tools)
    mutating = [schema for schema in tools if schema["mutates_document"]]
    requires_wps = [schema for schema in tools if schema["requires_wps"]]
    safety_notes_missing = [
        schema["name"]
        for schema in mutating
        if not schema.get("safety_notes")
    ]
    maintenance_tools = [
        {
            "name": schema["name"],
            "cli_command": schema["cli_command"],
            "title": schema["title"],
        }
        for schema in tools
        if schema["category"] in {"maintenance", "environment", "project"}
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "tool_count": len(tools),
        "category_counts": dict(sorted(category_counts.items())),
        "mutating_tool_count": len(mutating),
        "requires_wps_tool_count": len(requires_wps),
        "read_only_tool_count": len(tools) - len(mutating),
        "maintenance_tools": maintenance_tools,
        "safety_notes_missing_count": len(safety_notes_missing),
        "safety_notes_missing_tools": safety_notes_missing,
        "mutating_tools": [
            {
                "name": schema["name"],
                "cli_command": schema["cli_command"],
                "category": schema["category"],
                "requires_wps": schema["requires_wps"],
            }
            for schema in mutating
        ],
        "wps_required_tools": [
            {
                "name": schema["name"],
                "cli_command": schema["cli_command"],
                "category": schema["category"],
                "mutates_document": schema["mutates_document"],
            }
            for schema in requires_wps
        ],
    }
