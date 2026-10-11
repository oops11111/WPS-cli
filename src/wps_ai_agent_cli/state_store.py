from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any


class StateCorruptError(Exception):
    code = "STATE_CORRUPT"

    def __init__(self, path: Path, quarantined: Path | None, reason: str):
        self.path = path
        self.quarantined = quarantined
        self.reason = reason
        self.details = {"state_path": str(path), "quarantined_path": str(quarantined) if quarantined else None}
        location = f" moved to {quarantined}" if quarantined else ""
        super().__init__(f"State file {path} is not valid JSON ({reason});{location}. Restore it from a copy or re-register documents before retrying.")


def _quarantine(path: Path) -> Path | None:
    stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    target = path.with_name(f"{path.name}.corrupt-{stamp}-{os.getpid()}")
    try:
        os.replace(path, target)
    except OSError:
        return None
    return target


def read_json_state(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    for attempt in range(20):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return default
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise StateCorruptError(path, _quarantine(path), str(exc)) from exc
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.025)
        else:
            if not isinstance(value, dict):
                raise StateCorruptError(path, _quarantine(path), "top-level value is not an object")
            return value
    raise AssertionError("Unreachable state read retry limit")


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(20):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(0.025)
    finally:
        Path(temporary).unlink(missing_ok=True)
