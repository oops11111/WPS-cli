from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .capabilities import powershell_executable
from .errors import COM_OPERATION_FAILED, COM_OPERATION_TIMEOUT


def run_powershell_script(
    script: str,
    timeout_seconds: int = 120,
    timeout_message: str | None = None,
    timeout_data: dict[str, Any] | None = None,
    failure_data: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Run a script file in PowerShell and parse its JSON stdout.

    Returns ``(payload, None)`` on success or ``(None, failure)`` where
    ``failure`` is a ready-to-return ``{ok, errors, data}`` result.
    """
    script_path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8-sig") as script_file:
            script_file.write(script)
            script_path = script_file.name
        completed = subprocess.run(
            [powershell_executable(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path],
            check=False, capture_output=True, encoding="utf-8", errors="replace", text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        data = {"backend": "powershell-com", "timed_out": True, **(timeout_data or {})}
        if isinstance(exc.stdout, str):
            data.setdefault("stdout", exc.stdout)
        if isinstance(exc.stderr, str):
            data.setdefault("stderr", exc.stderr)
        return None, {
            "ok": False,
            "errors": [{
                "code": COM_OPERATION_TIMEOUT,
                "message": timeout_message
                or f"WPS operation timed out after {timeout_seconds} seconds; WPS may still be running. Run wps-process-audit before retrying.",
            }],
            "data": data,
        }
    except OSError as exc:
        return None, {
            "ok": False,
            "errors": [{"code": COM_OPERATION_FAILED, "message": f"PowerShell could not be started: {exc}"}],
            "data": {"backend": "powershell-com", **(failure_data or {})},
        }
    finally:
        if script_path:
            try:
                Path(script_path).unlink(missing_ok=True)
            except OSError:
                pass

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = None
    if completed.returncode != 0 or not isinstance(payload, dict):
        message = (completed.stderr or completed.stdout).strip()
        if isinstance(payload, dict):
            message = payload.get("error_message") or message
        return None, {
            "ok": False,
            "errors": [{"code": COM_OPERATION_FAILED, "message": message}],
            "data": {"backend": "powershell-com", **(failure_data or {}), "diagnostic": payload},
        }
    return payload, None
