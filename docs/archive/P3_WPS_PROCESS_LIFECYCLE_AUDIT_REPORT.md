# P3-014 WPS Process Lifecycle Audit Report

## Summary

P3-014 added a read-only process audit for WPS-related desktop processes.

New entry points:

- CLI: `wps-process-audit`
- MCP: `wps_agent_wps_process_audit`

The audit lists likely WPS process names and provides safe cleanup guidance. It does not terminate processes, because they may belong to a visible user session or an unrelated document.

## Evidence

Command:

```powershell
python -m wps_ai_agent_cli wps-process-audit --request-id p3-014-wps-process-audit-001
```

Observed:

- `ok = true`
- `process_count = 5`
- process names included four `et` spreadsheet processes and one `wpscloudsvr`
- validation passed:
  - `process_scan_completed`
  - `no_automatic_process_kill`

## Cleanup Guidance

The command reports:

- Do not automatically kill WPS processes; they may belong to an active user session.
- Before manual cleanup, save visible WPS documents and verify no active automation is running.
- If a process is confirmed stale, close it from the desktop UI or Task Manager.

## Follow-Up

P3-015 should refresh release readiness evidence now that safe regression, WPS regression, advanced Writer table smoke, spreadsheet timeout hardening, and process diagnostics are in place.
