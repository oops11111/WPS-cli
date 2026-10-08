from __future__ import annotations

from pathlib import Path
from typing import Any

from .cleanup_plan import build_cleanup_plan


def build_cleanup_approval_manifest(workspace: Path | str = ".") -> dict[str, Any]:
    plan = build_cleanup_plan(workspace)
    categories: dict[str, dict[str, Any]] = {}
    for candidate in plan["candidates"]:
        category = candidate["category"]
        entry = categories.setdefault(
            category,
            {
                "category": category,
                "candidate_count": 0,
                "total_bytes": 0,
                "paths": [],
                "approval_phrase": f"批准清理 {category}",
            },
        )
        entry["candidate_count"] += 1
        entry["total_bytes"] += int(candidate.get("size_bytes", 0))
        entry["paths"].append(candidate["path"])

    category_list = sorted(categories.values(), key=lambda item: item["category"])
    return {
        "workspace": plan["workspace"],
        "read_only": True,
        "deletion_performed": False,
        "approval_required": True,
        "candidate_count": plan["candidate_count"],
        "total_candidate_bytes": plan["total_candidate_bytes"],
        "categories": category_list,
        "exact_path_approval_template": "批准删除 <exact path from cleanup-plan>",
        "notes": [
            "This manifest is for approval review only.",
            "No cleanup is executed by this command.",
            "Paths and categories should be regenerated with cleanup-plan before any future removal.",
        ],
    }
