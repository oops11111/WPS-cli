from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .jsonio import dumps_json


Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    return token.strip("-") or "unknown"


def write_json_artifact(
    payload: dict[str, Any],
    artifact_dir: str | Path,
    prefix: str,
    request_id: str,
    clock: Clock = _utc_now,
) -> dict[str, Any]:
    timestamp = clock().astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    directory = Path(artifact_dir)
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{_safe_token(prefix)}-{timestamp}-{_safe_token(request_id)}.json"
    path = directory / filename
    path.write_text(dumps_json(payload) + "\n", encoding="utf-8")
    return {
        "created": True,
        "path": str(path),
        "filename": filename,
        "timestamp": timestamp,
    }
