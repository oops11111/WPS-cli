# P3-019 Local Cleanup Policy and Approval

## Summary

P3-019 defines the local-only cleanup policy for continued development in:

```text
C:\Users\admin\Documents\wps cli
```

No files were deleted as part of this task.

## Policy

- Cleanup is approval-gated: do not delete files unless the user explicitly approves the exact path or category.
- Keep `src`, `tests`, `config`, `docs`, required fixtures, latest safe regression evidence, latest WPS regression evidence, and the repeatable CLI sync package.
- Keep `.wps-agent\backups` by default. Treat backups as recovery evidence and review them as a group before any deletion.
- Prefer running `cleanup-plan` immediately before asking for removal approval, so candidates reflect the current workspace.
- Do not terminate WPS processes from cleanup automation. Use `wps-process-audit` first and close confirmed stale processes manually.

## Implemented Read-Only Command

P3-019 adds:

```powershell
python -m wps_ai_agent_cli cleanup-plan
```

The command returns a structured cleanup plan with:

- protected paths
- preserved latest evidence
- approval-required cleanup candidates
- total candidate bytes
- dry-run inspection commands

It is intentionally read-only and reports `deletion_performed: false`.

Current local run:

- Request id: `p3-019-cleanup-plan-001`
- Candidate groups: 25
- Candidate bytes: 1,800,218
- Deletions performed: none

## Cleanup Candidate Categories

These categories may be reviewed later, but remain untouched until approved:

- Superseded spreadsheet probe outputs under `fixtures\phase3`.
- Older safe regression JSON artifacts superseded by the latest safe pass.
- Older WPS regression JSON artifacts superseded by the latest WPS pass.
- Older manually generated sync packages superseded by `cloud-sync-package`.
- `.wps-agent\backups` only after a separate recovery-retention decision.

## Verification

Use these commands before and after any future approved cleanup:

```powershell
$env:PYTHONPATH='src'
python -m wps_ai_agent_cli cleanup-plan
python -m unittest discover -s tests
python -m wps_ai_agent_cli regression-run --profile safe --artifact-dir artifacts\regression\safe
python -m wps_ai_agent_cli cloud-sync-package --output artifacts\cloud-sync\wps-ai-agent-cli-phase3-sync-cli.zip
```

## Outcome

The cleanup policy is now defined and machine-readable through CLI/MCP. Actual removal is intentionally deferred until the user approves a specific candidate list.
