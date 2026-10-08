# Cloud Sync Readiness Handoff

## Current Workspace

Local project root:

```text
C:\Users\admin\Documents\wps cli
```

The user confirmed this project should continue in the current local workspace. Remote Git and external cloud upload are optional future paths, not blockers for current development.

## Recommended Sync Scope

Include:

- `src\`
- `tests\`
- `config\`
- `docs\`
- `fixtures\`
- latest safe regression artifact under `artifacts\regression\safe`
- `artifacts\regression\wps\regression-run-20261003T105030651877Z-regression-writer-table-p3-013-wps-003.json`
- `artifacts\cloud-sync\wps-ai-agent-cli-phase3-sync-cli.zip`

Exclude or regenerate:

- `.wps-agent\backups\` unless recovery evidence must be preserved
- transient WPS output probes not referenced by release reports
- Python caches such as `__pycache__`

## Local Verification

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests
python -m wps_ai_agent_cli project-status
python -m wps_ai_agent_cli regression-run --profile safe --artifact-dir artifacts\regression\safe
python -m wps_ai_agent_cli cloud-sync-package --output artifacts\cloud-sync\wps-ai-agent-cli-phase3-sync-cli.zip
```

Optional local desktop WPS validation:

```powershell
python -m wps_ai_agent_cli regression-run --profile wps --include-wps --artifact-dir artifacts\regression\wps
python -m wps_ai_agent_cli wps-process-audit
```

## Optional Future Target Options

No remote target is required now. If that changes later, choose one:

- Initialize Git here and push to a remote repository.
- Package the recommended sync scope into an archive for upload.
- Connect a cloud project workspace and copy the recommended sync scope there.
- Use an installed connector such as Google Drive, Dropbox, SharePoint, or Box if the target is document-storage oriented.

## Current Local Evidence

- Release readiness: `docs\PHASE3_RELEASE_READINESS_REFRESH.md`
- Project status: `python -m wps_ai_agent_cli project-status`
- Safe regression final artifact: latest artifact under `artifacts\regression\safe`
- WPS regression final artifact: `artifacts\regression\wps\regression-run-20261003T105030651877Z-regression-writer-table-p3-013-wps-003.json`
- WPS process audit: `docs\P3_WPS_PROCESS_LIFECYCLE_AUDIT_REPORT.md`

## Current Decision

Continue local-only. Regenerate the sync package locally when a handoff archive is needed.
