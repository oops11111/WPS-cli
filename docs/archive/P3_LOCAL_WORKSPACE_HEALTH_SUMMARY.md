# P3-027 Local Workspace Health Summary

## Summary

P3-027 adds a read-only health command:

```powershell
python -m wps_ai_agent_cli workspace-health
```

It combines local project status, cleanup approval posture, regression evidence, and sync package state into one status response.

## MCP Tool

```text
wps_agent_workspace_health
```

## Health Checks

The command reports:

- next task availability
- latest safe regression artifact availability
- sync package availability
- cleanup read-only / no-deletion posture
- local-only mode, with `remote_git_required: false`

## Safety

- Read-only.
- Does not delete cleanup candidates.
- Does not launch WPS.
- Does not call Git or any remote/cloud service.

## Verification

Planned verification commands:

```powershell
$env:PYTHONPATH='src'
python -m wps_ai_agent_cli workspace-health
python -m unittest discover -s tests
python -m wps_ai_agent_cli regression-run --profile safe --artifact-dir artifacts\regression\safe
```
