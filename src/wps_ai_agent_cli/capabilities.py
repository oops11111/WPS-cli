from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from collections.abc import Callable
from typing import Any


WPS_COMPONENTS: dict[str, tuple[str, ...]] = {
    "writer": ("kwps.Application", "wps.Application", "Kingsoft Writer.Application"),
    "spreadsheets": ("ket.Application", "et.Application", "Kingsoft Spreadsheets.Application"),
    "presentation": ("kwpp.Application", "wpp.Application", "Kingsoft Presentation.Application"),
}


def powershell_executable() -> str:
    return shutil.which("pwsh") or shutil.which("powershell") or "powershell"


def _load_pythoncom() -> Any | None:
    try:
        import pythoncom  # type: ignore[import-not-found]
    except ImportError:
        return None
    return pythoncom


def _resolve_with_powershell(prog_id: str) -> bool:
    command = (
        "$t = [type]::GetTypeFromProgID("
        + repr(prog_id)
        + "); if ($null -ne $t) { 'true' } else { 'false' }"
    )
    completed = subprocess.run(
        [
            powershell_executable(),
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            command,
        ],
        check=False,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        text=True,
        timeout=10,
    )
    return completed.returncode == 0 and completed.stdout.strip().lower() == "true"


def probe_wps_capabilities(
    clsid_resolver: Callable[[str], object] | None = None,
) -> dict[str, Any]:
    system = platform.system()
    pythoncom = None if clsid_resolver else _load_pythoncom()
    pywin32_available = bool(clsid_resolver or pythoncom)
    is_windows = system == "Windows"
    probe_backend = {"powershell_available": False}

    def resolve(prog_id: str) -> tuple[bool, str | None]:
        if not is_windows:
            return False, "not_windows"
        if pywin32_available:
            try:
                if clsid_resolver:
                    clsid_resolver(prog_id)
                else:
                    pythoncom.CLSIDFromProgID(prog_id)
                return True, None
            except Exception as exc:  # pragma: no cover - depends on local COM registry
                pywin32_error = exc.__class__.__name__
        else:
            pywin32_error = "pywin32_missing"

        try:
            registered = _resolve_with_powershell(prog_id)
            probe_backend["powershell_available"] = True
        except Exception as exc:  # pragma: no cover - depends on host powershell
            return False, f"{pywin32_error};powershell_{exc.__class__.__name__}"
        return (True, None) if registered else (False, pywin32_error)

    components: dict[str, Any] = {}
    for component, prog_ids in WPS_COMPONENTS.items():
        attempts = []
        detected = False
        selected_prog_id = None
        for prog_id in prog_ids:
            ok, error = resolve(prog_id)
            attempts.append({"prog_id": prog_id, "registered": ok, "error": error})
            if ok and not detected:
                detected = True
                selected_prog_id = prog_id
        components[component] = {
            "detected": detected,
            "selected_prog_id": selected_prog_id,
            "attempts": attempts,
        }

    return {
        "platform": {
            "system": system,
            "release": platform.release(),
            "python": sys.version.split()[0],
            "is_windows": is_windows,
        },
        "dependencies": {
            "pywin32_available": pywin32_available,
            "powershell_com_probe_available": probe_backend["powershell_available"],
        },
        "components": components,
    }
