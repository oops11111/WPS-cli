from __future__ import annotations

import re
from typing import Any


_MCP_TOOL_NAME_PATTERN = re.compile(r"[A-Za-z0-9_.-]{1,128}\Z")


def audit_mcp_tool_names(tools: list[Any]) -> tuple[int, int]:
    valid_names = []
    invalid_count = 0
    for tool in tools:
        name = tool.get("name") if isinstance(tool, dict) else None
        if not isinstance(name, str) or _MCP_TOOL_NAME_PATTERN.fullmatch(name) is None:
            invalid_count += 1
        else:
            valid_names.append(name)
    duplicate_count = len(valid_names) - len(set(valid_names))
    return invalid_count, duplicate_count
