# P3-038 Next Non-Destructive Capability Selection

## Selected Target

Regression evidence summary.

## Why This Target

The project now has stronger local status, workspace health, MCP catalog snapshot, and catalog drift guard commands. The next useful non-destructive capability is a compact way to read the latest regression evidence without opening each artifact manually.

## Scope

Add a read-only command:

```powershell
python -m wps_ai_agent_cli regression-evidence
```

Expected output:

- latest safe regression artifact path and counts
- latest WPS regression artifact path and counts
- pass/fail status per profile
- aggregate evidence status
- local workspace path

## Out of Scope

- No WPS launch.
- No regression execution.
- No artifact mutation.
- No cleanup deletion.
- No remote Git, upload, or cloud synchronization.

## Validation

Minimum validation:

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests
python -m wps_ai_agent_cli regression-evidence
python -m wps_ai_agent_cli regression-run --profile safe --artifact-dir artifacts\regression\safe
```

Acceptance for P3-039:

- The command is read-only.
- Latest safe and WPS artifacts are summarized.
- Safe regression can include the summary command without launching WPS.
