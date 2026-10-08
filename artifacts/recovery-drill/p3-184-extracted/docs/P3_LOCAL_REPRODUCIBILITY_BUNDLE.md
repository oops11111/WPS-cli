# P3-020 Local Reproducibility Command Bundle

## Summary

P3-020 adds a local-only reproducibility bundle for continued development in the current workspace. It does not use remote Git, cloud upload, or external services.

Script:

```text
scripts\local_repro_bundle.ps1
```

## What It Runs

The script runs these steps in order:

1. Unit tests:

```powershell
python -m unittest discover -s tests
```

2. Read-only cleanup plan:

```powershell
python -m wps_ai_agent_cli cleanup-plan
```

3. Safe regression with artifact export:

```powershell
python -m wps_ai_agent_cli regression-run --profile safe --artifact-dir artifacts\regression\safe
```

4. Local sync package regeneration:

```powershell
python -m wps_ai_agent_cli cloud-sync-package --output artifacts\cloud-sync\wps-ai-agent-cli-phase3-sync-cli.zip
```

## Run Command

```powershell
.\scripts\local_repro_bundle.ps1
```

Optional Python override:

```powershell
.\scripts\local_repro_bundle.ps1 -Python "C:\path\to\python.exe"
```

## Output

The script writes a local summary artifact:

```text
artifacts\local-repro\local-repro-<run-id>.json
```

It also refreshes:

- latest safe regression JSON under `artifacts\regression\safe`
- repeatable local sync package at `artifacts\cloud-sync\wps-ai-agent-cli-phase3-sync-cli.zip`

## Verified Run

Run id:

```text
p3-020-local-repro-001
```

Summary artifact:

```text
artifacts\local-repro\local-repro-p3-020-local-repro-001.json
```

Safe regression artifact:

```text
artifacts\regression\safe\regression-run-20261003T154602879583Z-local-repro-p3-020-local-repro-001-safe.json
```

Sync package:

```text
artifacts\cloud-sync\wps-ai-agent-cli-phase3-sync-cli.zip
```

Sync package SHA256:

```text
158AA47F91E74E6F967BAE6B8226A95AABA090F42126F2BC7F7CE488FED655AF
```

Results:

- Unit tests: 95 passed.
- Cleanup plan: passed, read-only, no deletion.
- Safe regression: 6/6 passed.
- Sync package: 122 entries.

## Safety

- No remote Git commands are run.
- No cloud upload is attempted.
- Cleanup remains read-only; deletion requires separate explicit user approval.
- WPS desktop is not launched because only the safe regression profile is used.
