# P3-041 Next Non-Destructive Capability Selection

## Selected Target

Local handoff summary.

## Why This Target

The project now exposes project status, workspace health, regression evidence, and MCP catalog drift as separate read-only commands. A local handoff summary will make continuation easier by combining these signals into one compact status response.

## Scope

Add a read-only command:

```powershell
python -m wps_ai_agent_cli local-handoff-summary
```

Expected output:

- current next task
- workspace health status
- regression evidence status
- MCP catalog drift count
- sync package hash and size
- cleanup posture
- remote Git requirement flag

## Out of Scope

- No WPS launch.
- No regression execution.
- No cleanup deletion.
- No package mutation.
- No remote Git, upload, or cloud synchronization.

## Validation

Minimum validation:

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests
python -m wps_ai_agent_cli local-handoff-summary
python -m wps_ai_agent_cli regression-run --profile safe --artifact-dir artifacts\regression\safe
```

Acceptance for P3-042:

- The command is read-only.
- It summarizes project status, workspace health, regression evidence, catalog drift, and sync package evidence.
- Safe regression can include the summary command without launching WPS.
