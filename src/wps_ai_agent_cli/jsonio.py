from __future__ import annotations

import datetime as dt
import json
from typing import Any


def json_default(value: Any) -> Any:
    """Dates and times, as spreadsheet cells hold them, become ISO 8601 text; anything else is still an error."""
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, dt.timedelta):
        return value.total_seconds()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def dumps_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=json_default)
