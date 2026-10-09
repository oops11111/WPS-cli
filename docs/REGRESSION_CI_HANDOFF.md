# Regression Artifact CI Handoff

Date: 2026-10-03

## Scope

This handoff defines how CI or a scheduled Windows runner should invoke the Phase 3 regression suite, where JSON artifacts should be retained, and which fields decide pass/fail for safe, release, and WPS profiles.

## Safe Profile

Use the safe profile as the baseline. It does not launch desktop WPS or require a previously passed safe artifact. Package-readiness checks still require a current local package.

```powershell
$env:PYTHONPATH='src'
& 'C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m wps_ai_agent_cli regression-run --profile safe --artifact-dir artifacts\regression\safe --request-id ci-safe-$env:BUILD_BUILDID
```

Required gate:

- Process exit code is `0`.
- Top-level `ok` is `true`.
- `validation.status` is `passed`.
- `data.regression.failed_count` is `0`.
- `data.regression.scenario_count` is at least `5`.
- `data.artifact.created` is `true`.

Artifact retention:

- Upload `artifacts\regression\safe\regression-run-*.json`.
- Keep successful PR artifacts for at least 30 days.
- Keep failed safe artifacts for at least 90 days or until the related defect is closed.

## Release Profile

The shipped manifest has no `release` scenarios. The profile name is kept so a custom manifest can define its own gates; `regression-run --profile release` on the shipped manifest reports zero scenarios. The former `local-release-gates` command and its package-readiness steps were removed (see `docs/CODE_REVIEW_BATCH_6.md`, G-07).

## WPS Profile

Use the WPS profile only on an interactive Windows runner with WPS installed and COM automation available. It can launch WPS desktop processes and writes output files under `fixtures\phase3`.

```powershell
$env:PYTHONPATH='src'
& 'C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m wps_ai_agent_cli regression-run --profile wps --include-wps --artifact-dir artifacts\regression\wps --request-id ci-wps-$env:BUILD_BUILDID
```

Required gate:

- Process exit code is `0`.
- Top-level `ok` is `true`.
- `validation.status` is `passed`.
- `data.regression.failed_count` is `0`.
- `data.regression.scenario_count` is at least `3`.
- Every result has `requires_wps` set to `true`.
- `fixtures\phase3\writer_smoke_copy.docx` exists.
- `fixtures\phase3\phase0_calculation_smoke.xlsx` exists.
- `fixtures\phase3\writer_smoke.pdf` exists.
- `data.artifact.created` is `true`.

Artifact retention:

- Upload `artifacts\regression\wps\regression-run-*.json`.
- Upload WPS output evidence from `fixtures\phase3`.
- Keep all WPS profile artifacts for at least 90 days because they are environment-specific evidence.

## Failure Triage

1. Open the JSON artifact named in `data.artifact.path`.
2. Inspect `data.regression.results[]` and start with entries where `ok` is `false`.
3. Compare failed `checks[]` entries with the manifest expectation in `config\regression_manifest.json`.
4. For WPS failures, capture `inspect-env` output and rerun only after confirming WPS processes have exited.
5. If the artifact is missing but stdout reports a passed run, treat the CI job as failed because the audit trail is incomplete.

## Current Verified Evidence

- Safe profile artifact export passed with request id `regression-artifact-p3-004-001`.
- MCP adapter artifact export passed with request id `mcp-regression-artifact-p3-004-002`.
- WPS profile passed previously with request id `regression-run-wps-p3-003-001`.

## Next Work

The next production-readiness task should establish a recovery hardening drill for failed or interrupted document-mutating operations.
