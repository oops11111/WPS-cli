# P3-026 Cleanup Approval Manifest Export

## Summary

P3-026 adds a read-only command for future cleanup approval review:

```powershell
python -m wps_ai_agent_cli cleanup-approval-manifest
```

The command groups current `cleanup-plan` candidates by exact approval category and includes example approval phrases. It does not delete files.

## MCP Tool

```text
wps_agent_cleanup_approval_manifest
```

## Safety

- Read-only.
- Does not execute cleanup.
- Does not change `.wps-agent`, fixtures, regression artifacts, or sync packages.
- Future deletion still requires a separate explicit user approval naming exact categories or paths.

## Output Shape

The manifest includes:

- total candidate count
- total candidate bytes
- grouped categories
- paths under each category
- approval phrase for each category
- exact path approval template

## Related Gate

P3-025 remains closed by default:

```text
No approved category or path, no removal.
```
