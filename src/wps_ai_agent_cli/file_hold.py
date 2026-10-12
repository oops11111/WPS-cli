"""Preflight file-share probes that mirror Assert-WpsFileNotHeld before Zip/identity opens."""

from __future__ import annotations

import errno
import os
from pathlib import Path
from typing import Any

from .errors import COM_OPERATION_FAILED

# Keep these aligned with wps_script_snippets.Assert-WpsFileNotHeld throw text.
_HELD_OPEN = (
    "The {what} is held open by another handle ({held}), most likely because it is open in WPS. "
    "Open() was not called: on a document that is already open it reloads the file from disk without asking "
    "(alerts are turned off here) and discards unsaved edits made in WPS. The command was refused and nothing "
    "was written, saved or closed. Save or close the document in WPS (or the program that holds the file) and retry."
)
_PROBE_UNKNOWN = (
    "The {what} could not be checked for being open in WPS ({unknown}). Open() was not called, because on a "
    "document that is already open it reloads the file from disk without asking (alerts are turned off here) and "
    "discards unsaved edits. The command was refused as a precaution and nothing was written, saved or closed."
)

# Win32 CreateFileW constants (kernel32).
_GENERIC_READ = 0x80000000
_FILE_SHARE_READ = 0x00000001
_FILE_SHARE_NONE = 0x00000000
_OPEN_EXISTING = 3
_FILE_ATTRIBUTE_NORMAL = 0x80
_INVALID_HANDLE_VALUE = 0xFFFFFFFF
_ERROR_FILE_NOT_FOUND = 2
_ERROR_PATH_NOT_FOUND = 3
_ERROR_SHARING_VIOLATION = 32
_ERROR_LOCK_VIOLATION = 33


def held_open_error(what: str, held: str) -> dict[str, str]:
    return {"code": COM_OPERATION_FAILED, "message": _HELD_OPEN.format(what=what, held=held)}


def probe_unknown_error(what: str, unknown: str) -> dict[str, str]:
    return {"code": COM_OPERATION_FAILED, "message": _PROBE_UNKNOWN.format(what=what, unknown=unknown)}


def is_share_conflict(exc: BaseException) -> bool:
    """True when an open/read failed because another handle holds an incompatible share."""
    if isinstance(exc, PermissionError):
        return True
    if not isinstance(exc, OSError):
        return False
    winerror = getattr(exc, "winerror", None)
    if winerror in (_ERROR_SHARING_VIOLATION, _ERROR_LOCK_VIOLATION):
        return True
    if exc.errno in (errno.EACCES, errno.EPERM):
        return True
    text = str(exc).lower()
    return "being used by another process" in text or "sharing violation" in text or "permission denied" in text


def share_conflict_error(exc: BaseException, what: str = "document") -> dict[str, str]:
    return held_open_error(what, str(exc))


def _probe_win32(path: Path, *, read_only: bool) -> tuple[str | None, str | None]:
    """Return (held_detail, unknown_detail). Missing path → (None, None) like the PS probe."""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    share = _FILE_SHARE_READ if read_only else _FILE_SHARE_NONE
    handle = kernel32.CreateFileW(
        str(path),
        _GENERIC_READ,
        share,
        None,
        _OPEN_EXISTING,
        _FILE_ATTRIBUTE_NORMAL,
        None,
    )
    if handle == _INVALID_HANDLE_VALUE or handle == wintypes.HANDLE(-1).value:
        code = ctypes.get_last_error()
        if code in (_ERROR_FILE_NOT_FOUND, _ERROR_PATH_NOT_FOUND):
            return None, None
        message = ctypes.FormatError(code)
        if code in (_ERROR_SHARING_VIOLATION, _ERROR_LOCK_VIOLATION):
            return message, None
        return None, message
    kernel32.CloseHandle(handle)
    return None, None


def _probe_posix(path: Path) -> tuple[str | None, str | None]:
    """Best-effort open on non-Windows (no Win32 share modes). Missing → (None, None)."""
    try:
        with path.open("rb"):
            return None, None
    except FileNotFoundError:
        return None, None
    except IsADirectoryError as exc:
        return None, str(exc)
    except OSError as exc:
        if is_share_conflict(exc):
            return str(exc), None
        return None, str(exc)


def probe_file_not_held(
    path: str | Path,
    *,
    read_only: bool = False,
    what: str = "document",
) -> dict[str, str] | None:
    """Return a held-open / probe-unknown COM_OPERATION_FAILED error, or None if the probe passes.

    Matches Assert-WpsFileNotHeld: read-only asks for FileShare.Read; mutating asks for FileShare.None.
    A missing file is left for later Open()/existence checks.
    """
    target = Path(path)
    try:
        if os.name == "nt":
            held, unknown = _probe_win32(target, read_only=read_only)
        else:
            held, unknown = _probe_posix(target)
    except OSError as exc:
        return probe_unknown_error(what, str(exc))
    if held is not None:
        return held_open_error(what, held)
    if unknown is not None:
        return probe_unknown_error(what, unknown)
    return None


def refuse_if_held(
    path: str | Path,
    *,
    read_only: bool = False,
    what: str = "document",
    data: dict[str, Any] | None = None,
) -> tuple[bool, dict[str, Any], list[dict[str, str]]] | None:
    """Convenience for command entry points: None if free, else (False, data, [error])."""
    error = probe_file_not_held(path, read_only=read_only, what=what)
    if error is None:
        return None
    return False, data or {}, [error]
