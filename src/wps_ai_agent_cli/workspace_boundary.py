"""Optional workspace boundary for document paths (S-02).

When ``WPS_AGENT_WORKSPACE_ROOT`` names a directory, documents may only be registered or converted
from inside that directory; ``*`` (or an unset variable) means no boundary. It is a deployment
setting: an MCP server configuration sets it in the server's environment to confine tool calls to a
chosen tree (for example the user's documents folder), and scripts can set it the same way. It is
deliberately not defaulted to the server's working directory — documents legitimately live outside
the folder the server happens to start in.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

BOUNDARY_ENV = "WPS_AGENT_WORKSPACE_ROOT"


def boundary_root() -> Path | None:
    raw = os.environ.get(BOUNDARY_ENV, "").strip()
    if not raw or raw == "*":
        return None
    return Path(raw).expanduser().resolve()


def set_boundary_root(root: str | Path) -> None:
    os.environ[BOUNDARY_ENV] = str(root)


def boundary_error(path: str | Path, what: str = "Path") -> dict[str, Any] | None:
    """An error entry when ``path`` lies outside the configured boundary, else None."""
    root = boundary_root()
    if root is None:
        return None
    resolved = Path(path).expanduser().resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return {
            "code": "PATH_OUTSIDE_WORKSPACE",
            "message": (
                f"{what} is outside the workspace boundary ({root}): {resolved}. "
                "Move the file inside the workspace, or widen WPS_AGENT_WORKSPACE_ROOT "
                "(set it to * to disable the boundary)."
            ),
        }
    return None
