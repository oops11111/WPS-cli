from __future__ import annotations

from pathlib import Path
from typing import Any

from .sessions import list_documents


EXTENSION_COMPONENTS = {
    ".doc": "writer",
    ".docx": "writer",
    ".wps": "writer",
    ".xls": "spreadsheets",
    ".xlsx": "spreadsheets",
    ".et": "spreadsheets",
    ".ppt": "presentation",
    ".pptx": "presentation",
    ".dps": "presentation",
}


def infer_component(path: str | Path) -> str | None:
    return EXTENSION_COMPONENTS.get(Path(path).suffix.lower())


def scan_directory(
    directory: str | Path,
    recursive: bool = False,
    workspace: str | Path = ".",
) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    root = Path(directory)
    if not root.exists():
        return (
            False,
            {},
            [{"code": "DIRECTORY_NOT_FOUND", "message": f"Directory not found: {directory}"}],
        )
    if not root.is_dir():
        return (
            False,
            {},
            [{"code": "NOT_A_DIRECTORY", "message": f"Not a directory: {directory}"}],
        )

    registered_by_path = {
        str(Path(record["path"]).resolve()).lower(): record
        for record in list_documents(workspace)
    }
    iterator = root.rglob("*") if recursive else root.iterdir()
    files = []
    for item in iterator:
        if not item.is_file():
            continue
        component = infer_component(item)
        if component is None:
            continue
        resolved = str(item.resolve())
        registered = registered_by_path.get(resolved.lower())
        files.append(
            {
                "path": resolved,
                "name": item.name,
                "component": component,
                "extension": item.suffix.lower(),
                "registered": registered is not None,
                "document_id": registered.get("document_id") if registered else None,
                "bytes": item.stat().st_size,
            }
        )

    files.sort(key=lambda entry: entry["path"].lower())
    return (
        True,
        {
            "directory": str(root.resolve()),
            "recursive": recursive,
            "count": len(files),
            "files": files,
        },
        [],
    )
