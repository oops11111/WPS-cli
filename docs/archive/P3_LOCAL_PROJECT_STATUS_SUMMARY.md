# P3-022 Local Project Status Summary

## Summary

P3-022 adds a local-only status command:

```powershell
python -m wps_ai_agent_cli project-status
```

The command summarizes the current workspace without using remote Git or cloud services.

## Included Status

- Workspace path
- Active Phase 3 next task
- MCP tool count
- Cleanup posture from `cleanup-plan`
- Latest safe regression artifact
- Latest WPS regression artifact
- Latest local reproducibility artifact
- Local sync package path, existence, size, and SHA256
- `remote_git_required: false`

## MCP Tool

The command is exposed as:

```text
wps_agent_project_status
```

## Safety

- Read-only.
- Does not delete cleanup candidates.
- Does not launch WPS.
- Does not run Git or remote sync.

## Verification

Planned verification commands:

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests
python -m wps_ai_agent_cli project-status
python -m wps_ai_agent_cli regression-run --profile safe --artifact-dir artifacts\regression\safe
```
