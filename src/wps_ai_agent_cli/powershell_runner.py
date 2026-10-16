from __future__ import annotations

import json
import re
import subprocess
import tempfile
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from .capabilities import powershell_executable
from .errors import (
    COM_OPERATION_FAILED,
    COM_OPERATION_TIMEOUT,
    DOCUMENT_HELD_OPEN,
    HELD_OPEN_MARKER,
)

# Windows PowerShell 5.1 writes redirected stdout in the console code page (GBK on a Chinese Windows), but every
# caller decodes it as UTF-8. Any non-ASCII text WPS returned came back garbled: the name of an untitled document
# such as 文字文稿1, a Chinese document name or selection (P7-007). Every script and command starts with this.
UTF8_OUTPUT_PREAMBLE = (
    "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false; "
    "$OutputEncoding = [Console]::OutputEncoding\n"
)


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
    command.extend(["-Command", UTF8_OUTPUT_PREAMBLE + script])
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        text=True,
        timeout=timeout_seconds,
    )


_PARAMETER_NAME = re.compile(r"^-[A-Za-z][A-Za-z0-9]*$")


def _powershell_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _powershell_argument(value: str) -> str:
    return value if _PARAMETER_NAME.match(value) else _powershell_quote(value)


def run_powershell_file(
    script_path: str | Path,
    args: Sequence[str] | None = None,
    timeout_seconds: int = 120,
    *,
    cwd: str | Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run an existing ``.ps1`` file with optional arguments.

    It runs through -Command rather than -File so that the UTF-8 output preamble applies to it too (P8-003): the
    Writer structure parity script prints headings, which may be Chinese. Arguments are quoted for PowerShell;
    one that looks like a parameter name (``-Path``) stays bare so that it still names the parameter.
    """
    invocation = " ".join(["&", _powershell_quote(str(script_path)), *(_powershell_argument(a) for a in args or ())])
    command = [
        powershell_executable(),
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        UTF8_OUTPUT_PREAMBLE + invocation + "; exit $LASTEXITCODE",
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


SCRIPT_WARNING_PREFIX = "WPS_AGENT_WARNING:"


def _script_warnings(stderr: str | None) -> list[str]:
    """Collect non-fatal notices a script wrote to stderr; stdout stays a single JSON document."""
    found: list[str] = []
    for line in (stderr or "").splitlines():
        line = line.strip()
        if line.startswith(SCRIPT_WARNING_PREFIX):
            message = line[len(SCRIPT_WARNING_PREFIX) :].strip()
            if message and message not in found:
                found.append(message)
    return found


_WARNING_SINK: ContextVar[list[str] | None] = ContextVar("wps_script_warning_sink", default=None)


@contextmanager
def collect_script_warnings() -> Iterator[list[str]]:
    """Gather the warnings of every script run inside the block into one list.

    Public commands rebuild their result from selected fields, so a script's own ``warnings`` would be
    lost; ``coordinated_mutation`` uses this to put them into the returned envelope in one place.
    Nested blocks pass what they collected on to the enclosing one.
    """
    sink: list[str] = []
    token = _WARNING_SINK.set(sink)
    try:
        yield sink
    finally:
        _WARNING_SINK.reset(token)
        outer = _WARNING_SINK.get()
        if outer is not None:
            outer.extend(item for item in sink if item not in outer)


def merge_warnings(data: Any, warnings: Sequence[str]) -> Any:
    """Return ``data`` with ``warnings`` added to its ``warnings`` list (deduplicated)."""
    if not warnings or not isinstance(data, dict):
        return data
    existing = data.get("warnings")
    merged = [existing] if isinstance(existing, str) else list(existing or [])
    merged.extend(item for item in warnings if item not in merged)
    return {**data, "warnings": merged}


def _remember_warnings(warnings: list[str]) -> None:
    sink = _WARNING_SINK.get()
    if sink is not None:
        sink.extend(item for item in warnings if item not in sink)


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
            script_file.write(UTF8_OUTPUT_PREAMBLE + script)
            script_path = script_file.name
        completed = subprocess.run(
            [powershell_executable(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path],
            check=False,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            text=True,
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
            "errors": [
                {
                    "code": COM_OPERATION_TIMEOUT,
                    "message": timeout_message
                    or f"WPS operation timed out after {timeout_seconds} seconds; WPS may still be running. Run wps-process-audit before retrying.",
                }
            ],
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
    warnings = _script_warnings(completed.stderr)
    _remember_warnings(warnings)
    if completed.returncode != 0 or not isinstance(payload, dict):
        message = (completed.stderr or completed.stdout).strip()
        if isinstance(payload, dict):
            message = payload.get("error_message") or message
        return None, {
            "ok": False,
            "errors": [
                {
                    "code": DOCUMENT_HELD_OPEN if HELD_OPEN_MARKER in message else COM_OPERATION_FAILED,
                    "message": message,
                }
            ],
            "data": {"backend": "powershell-com", **(failure_data or {}), "diagnostic": payload},
        }
    if warnings:
        payload["warnings"] = [*(payload.get("warnings") or []), *warnings]
    return payload, None
