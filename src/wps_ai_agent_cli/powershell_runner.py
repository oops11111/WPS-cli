from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Sequence

from .capabilities import powershell_executable
from .errors import COM_OPERATION_FAILED, COM_OPERATION_TIMEOUT


def run_powershell_command(
    script: str,
    timeout_seconds: int = 10,
    *,
    non_interactive: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run an inline PowerShell ``-Command`` script and return the completed process."""
    command = [powershell_executable(), "-NoProfile"]
    if non_interactive:
        command.append("-NonInteractive")
    command.extend(["-Command", script])
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        text=True,
        timeout=timeout_seconds,
    )


def run_powershell_file(
    script_path: str | Path,
    args: Sequence[str] | None = None,
    timeout_seconds: int = 120,
    *,
    cwd: str | Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run an existing ``.ps1`` file with optional arguments."""
    command = [
        powershell_executable(),
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        *(args or ()),
    ]
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd is not None else None,
        check=False,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        text=True,
        timeout=timeout_seconds,
    )


def run_powershell_script(
    script: str,
    timeout_seconds: int = 120,
    timeout_message: str | None = None,
    timeout_data: dict[str, Any] | None = None,
    failure_data: dict[str, Any] | None = None,
    raise_process_errors: bool = False,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Run a script file in PowerShell and parse its JSON stdout.

    Returns ``(payload, None)`` on success or ``(None, failure)`` where
    ``failure`` is a ready-to-return ``{ok, errors, data}`` result. With
    ``raise_process_errors`` a timeout or start failure is re-raised so a caller
    such as ``guarded_com_mutation`` can report it in one place.
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
        if raise_process_errors:
            raise
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
        if raise_process_errors:
            raise
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
