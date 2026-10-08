# P3-018 Local Workspace Continuity Audit

## Summary

P3-018 audited the current local-only workspace state after the user confirmed that remote Git/cloud sync is not required.

The workspace should continue to be treated as the source of truth:

```text
C:\Users\admin\Documents\wps cli
```

## Inventory

Artifacts:

- File count: 25
- Total size: 2,575,231 bytes
- Includes cloud-sync packages and regression artifacts.

Fixtures:

- File count: 21
- Total size: 1,147,129 bytes
- Includes Phase 0 fixtures, Phase 3 WPS outputs, and probe outputs from timeout investigation.

WPS agent state:

- Backup file count: 20
- Backup total size: 434,930 bytes
- State files:
  - `.wps-agent\documents.json`
  - `.wps-agent\operations.json`
  - `.wps-agent\task_statuses.json`

## Keep

Keep these as release or reproducibility evidence:

- `src\`
- `tests\`
- `config\`
- `docs\`
- `fixtures\phase0\`
- `fixtures\phase3\phase0_calculation_smoke.xlsx`
- `fixtures\phase3\writer_smoke_copy.docx`
- `fixtures\phase3\writer_smoke.pdf`
- `fixtures\phase3\writer_table_fixture.docx`
- `fixtures\phase3\writer_table_regression_smoke.docx`
- latest safe regression artifact
- latest WPS regression artifact
- `artifacts\cloud-sync\wps-ai-agent-cli-phase3-sync-cli.zip`

## Cleanup Candidates

Do not delete automatically. These are candidates for a later user-approved cleanup task:

- `fixtures\phase3\phase0_calculation_smoke_after_profile.xlsx`
- `fixtures\phase3\phase0_calculation_smoke_inprocess_probe.xlsx`
- `fixtures\phase3\phase0_calculation_smoke_timeout_probe.xlsx`
- older `artifacts\regression\safe\regression-run-*.json` superseded by the latest safe artifact
- older `artifacts\regression\wps\regression-run-*.json` superseded by the latest WPS artifact
- old `.wps-agent\backups\...` entries after confirming they are no longer needed for recovery evidence

## Safety Notes

- Do not automatically delete `.wps-agent\backups`; they are part of the recovery evidence chain.
- Do not automatically terminate WPS processes; use `wps-process-audit` first and close confirmed stale processes manually.
- Keep at least one passing safe regression artifact and one passing WPS regression artifact with every local handoff.

## Verification Commands

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests
python -m wps_ai_agent_cli regression-run --profile safe --artifact-dir artifacts\regression\safe
python -m wps_ai_agent_cli cloud-sync-package --output artifacts\cloud-sync\wps-ai-agent-cli-phase3-sync-cli.zip
```

## Follow-Up

P3-019 defined the cleanup policy, P3-021 recorded the no-approval/no-deletion checkpoint, and later cleanup still requires explicit user approval for exact paths or categories.
