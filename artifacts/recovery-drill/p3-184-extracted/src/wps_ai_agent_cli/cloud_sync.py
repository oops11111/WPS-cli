from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from .capabilities import powershell_executable
from .recovery_drill_evidence import verify_recovery_drill_artifacts, verify_recovery_drill_package


DEFAULT_SYNC_ROOTS = ("src", "tests", "config", "docs", "fixtures", "scripts")


def _latest_file(pattern: str, workspace: Path) -> Path | None:
    candidates = sorted(
        workspace.glob(pattern),
        key=lambda item: item.stat().st_mtime if item.exists() else 0,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def build_cloud_sync_package(
    output_path: str | Path,
    workspace: str | Path = ".",
    include_latest_artifacts: bool = True,
) -> tuple[bool, dict[str, Any], list[dict[str, Any]]]:
    workspace_path = Path(workspace).resolve()
    output = Path(output_path)
    if not output.is_absolute():
        output = workspace_path / output

    roots = [str((workspace_path / root).resolve()) for root in DEFAULT_SYNC_ROOTS if (workspace_path / root).exists()]
    artifacts: list[str] = []
    recovery_drill = verify_recovery_drill_artifacts(workspace_path) if include_latest_artifacts else {"status": "absent"}
    if recovery_drill["status"] == "failed":
        return False, {"recovery_drill_evidence": recovery_drill}, [{
            "code": "RECOVERY_DRILL_EVIDENCE_INVALID",
            "message": "Retained recovery-drill evidence is incomplete or changed; the package was not rebuilt.",
        }]
    if include_latest_artifacts:
        for pattern in (
            "artifacts/regression/safe/regression-run-*.json",
            "artifacts/regression/wps/regression-run-*.json",
            "artifacts/writer-structure-parity/writer-structure-parity-*.json",
            "artifacts/writer-nested-parity/writer-nested-parity-*.json",
        ):
            latest = _latest_file(pattern, workspace_path)
            if latest:
                artifacts.append(str(latest.resolve()))
        if recovery_drill["status"] == "passed":
            root = workspace_path / "artifacts" / "recovery-drill" / "p3-181-final"
            for component, suffix in (("writer", ".docx"), ("spreadsheets", ".xlsx")):
                directory = root / component
                artifacts.extend(str(path.resolve()) for path in (
                    directory / "manifest.json",
                    directory / f"current{suffix}",
                    directory / f"backup{suffix}",
                ))

    params = {
        "workspace": str(workspace_path),
        "output_path": str(output),
        "roots": roots,
        "artifacts": artifacts,
    }
    params_json = json.dumps(params)
    script = f"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$params = @'
{params_json}
'@ | ConvertFrom-Json
$rootPath = $params.workspace
$zipPath = $params.output_path
New-Item -ItemType Directory -Force (Split-Path $zipPath) | Out-Null
if (Test-Path -LiteralPath $zipPath) {{ Remove-Item -LiteralPath $zipPath -Force }}
$zip = [System.IO.Compression.ZipFile]::Open($zipPath, [System.IO.Compression.ZipArchiveMode]::Create)
$failed = @()
function AddFileToZip($filePath) {{
  try {{
    $file = Get-Item -LiteralPath $filePath
    $entryName = [System.IO.Path]::GetRelativePath($rootPath, $file.FullName)
    $entry = $zip.CreateEntry($entryName, [System.IO.Compression.CompressionLevel]::Optimal)
    $out = $entry.Open()
    $in = [System.IO.File]::Open($file.FullName, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
    try {{ $in.CopyTo($out) }} finally {{ $in.Dispose(); $out.Dispose() }}
  }} catch {{
    $script:failed += [pscustomobject]@{{ path = $filePath; error = $_.Exception.Message }}
  }}
}}
try {{
  foreach ($root in $params.roots) {{
    Get-ChildItem -LiteralPath $root -Recurse -File |
      Where-Object {{ $_.FullName -notlike '*\\__pycache__\\*' }} |
      ForEach-Object {{ AddFileToZip $_.FullName }}
  }}
  foreach ($artifact in $params.artifacts) {{
    if (Test-Path -LiteralPath $artifact) {{ AddFileToZip $artifact }}
  }}
}} finally {{
  $entryCount = $zip.Entries.Count
  $zip.Dispose()
}}
[pscustomobject]@{{
  output_path = $zipPath
  entry_count = $entryCount
  failed = $failed
}} | ConvertTo-Json -Depth 5
"""

    script_path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8-sig") as script_file:
            script_file.write(script)
            script_path = script_file.name
        completed = subprocess.run(
            [
                powershell_executable(),
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                script_path,
            ],
            check=False,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            text=True,
            timeout=120,
        )
    finally:
        if script_path:
            try:
                Path(script_path).unlink(missing_ok=True)
            except OSError:
                pass

    try:
        payload = json.loads(completed.stdout) if completed.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {}

    failed = payload.get("failed", []) if isinstance(payload, dict) else []
    if isinstance(failed, dict):
        failed = [failed]
    entry_count = 0
    if output.exists():
        with zipfile.ZipFile(output) as archive:
            entry_count = len(archive.infolist())
    ok = completed.returncode == 0 and output.exists() and entry_count > 0 and not failed
    result = {
        "output_path": str(output),
        "include_roots": list(DEFAULT_SYNC_ROOTS),
        "included_artifacts": artifacts,
        "entry_count": entry_count,
        "failed": failed,
        "created": output.exists(),
        "bytes": output.stat().st_size if output.exists() else 0,
        "sha256": _sha256(output) if output.exists() else None,
    }
    if recovery_drill["status"] == "passed" and output.exists():
        package_evidence = verify_recovery_drill_package(workspace_path, output)
        result["recovery_drill_package"] = package_evidence
        if package_evidence["status"] != "passed":
            ok = False
            failed.append({"path": str(output), "error": "Recovery-drill package bytes differ from workspace evidence."})
    errors = []
    if completed.returncode != 0:
        errors.append({"code": "CLOUD_SYNC_PACKAGE_FAILED", "message": completed.stderr.strip() or completed.stdout.strip()})
    if failed:
        errors.append({"code": "CLOUD_SYNC_PACKAGE_FILE_FAILED", "message": "One or more files could not be added.", "details": failed})
    return ok, result, errors
