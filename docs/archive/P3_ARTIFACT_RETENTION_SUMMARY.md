# P3-045 Artifact Retention Summary

## Outcome

P3-045 adds a read-only `artifact-retention-summary` command and MCP tool `wps_agent_artifact_retention_summary`.

The summary is intended for local-only continuation. It reports what evidence is retained, what artifact cleanup candidates exist, how much space they represent, and what approval is required before any deletion.

## Command

```powershell
python -m wps_ai_agent_cli artifact-retention-summary
```

## Reported Evidence

- Current repeatable sync package path, existence, size, and SHA256.
- Latest safe and WPS regression artifacts retained by `cleanup-plan`.
- Approval-required cleanup candidate groups by category, count, bytes, and paths.
- Explicit policy that deletion is not allowed without user approval for exact paths or categories.
- Local-only posture with `remote_git_required: false`.

## Safety

- Read-only: yes.
- Launches WPS: no.
- Deletes files: no.
- Creates packages: no.
- Uses remote Git or cloud services: no.

## Validation

- Added focused unit coverage in `tests\test_artifact_retention.py`.
- Added CLI parser coverage for `artifact-retention-summary`.
- Added MCP schema coverage for `wps_agent_artifact_retention_summary`.
- Reviewed MCP catalog baseline at 51 tools:
  - read-only: 43
  - mutating: 8
  - WPS-required: 9
  - maintenance category: 3
- Added `artifact-retention-summary` to the safe regression profile.
