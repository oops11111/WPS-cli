from __future__ import annotations

import json
import subprocess
from typing import Any

from .powershell_runner import run_powershell_command


WPS_PROCESS_NAMES = ("et", "wps", "wpp", "ket", "kwps", "ksolaunch", "wpscloudsvr")


def audit_wps_processes(timeout_seconds: int = 10) -> tuple[bool, dict[str, Any], list[dict[str, Any]]]:
    pattern = "^(" + "|".join(WPS_PROCESS_NAMES) + ")$"
    script = f"""
$ErrorActionPreference = 'Stop'
Get-Process |
  Where-Object {{ $_.ProcessName -match '{pattern}' }} |
  Select-Object ProcessName, Id, CPU,
    @{{Name='StartTime';Expression={{ try {{ $_.StartTime.ToString('o') }} catch {{ $null }} }}}},
    @{{Name='MainWindowTitle';Expression={{ $_.MainWindowTitle }}}} |
  ConvertTo-Json -Depth 4
"""
    try:
        completed = run_powershell_command(script, timeout_seconds=timeout_seconds)
    except subprocess.TimeoutExpired:
        return (
            False,
            {"timeout_seconds": timeout_seconds, "process_names": list(WPS_PROCESS_NAMES)},
            [{"code": "WPS_PROCESS_AUDIT_TIMEOUT", "message": f"Process audit timed out after {timeout_seconds} seconds."}],
        )

    if completed.returncode != 0:
        return (
            False,
            {"stderr": completed.stderr.strip(), "process_names": list(WPS_PROCESS_NAMES)},
            [{"code": "WPS_PROCESS_AUDIT_FAILED", "message": completed.stderr.strip() or "PowerShell process audit failed."}],
        )

    stdout = completed.stdout.strip()
    if not stdout:
        processes: list[dict[str, Any]] = []
    else:
        try:
            payload = json.loads(stdout[stdout.index(next(c for c in stdout if c in "[{")):])
        except (StopIteration, ValueError):
            return (
                False,
                {"stdout": stdout[:1_000], "process_names": list(WPS_PROCESS_NAMES)},
                [{"code": "WPS_PROCESS_AUDIT_FAILED", "message": "PowerShell process audit returned output that is not valid JSON."}],
            )
        processes = payload if isinstance(payload, list) else [payload]

    return (
        True,
        {
            "process_names": list(WPS_PROCESS_NAMES),
            "process_count": len(processes),
            "processes": processes,
            "cleanup_guidance": [
                "Do not automatically kill WPS processes; they may belong to an active user session.",
                "Before manual cleanup, save visible WPS documents and verify no active automation is running.",
                "If a process is confirmed stale, close it from the desktop UI or Task Manager.",
            ],
        },
        [],
    )
