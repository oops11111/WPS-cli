# P3-048 Local Validation Runbook

## Outcome

P3-048 adds a read-only `validation-runbook` command and MCP tool `wps_agent_validation_runbook`.

The command returns a structured local validation playbook without executing any of the listed steps.

## Command

```powershell
python -m wps_ai_agent_cli validation-runbook
```

## Sections

- Quick local checks: unit tests, project status, workspace health, and local handoff.
- Safe regression: safe profile, MCP smoke, and MCP config audit with the current tool-count expectation.
- Mutation recovery: inspect operation and backup evidence by request ID before considering a retry or restore; the runbook itself makes no changes.
- Package refresh: local sync package generation and status read-back.
- Optional WPS validation: WPS regression and process audit, clearly isolated as WPS-launching.
- Cleanup review: cleanup-plan, cleanup approval manifest, and artifact retention summary.

## Safety

- Read-only: yes.
- Executes commands: no.
- Launches WPS: no.
- Creates packages: no.
- Deletes files: no.
- Uses remote Git or cloud services: no.

## Validation

- Added focused unit coverage in `tests\test_validation_runbook.py`.
- Added CLI parser coverage for `validation-runbook`.
- Added MCP schema coverage for `wps_agent_validation_runbook`.
- Safe regression now covers the runbook as a non-WPS scenario.
