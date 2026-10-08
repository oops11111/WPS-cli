# P3-068 Next Sync Package Readiness Scope

## Decision

The next non-destructive Phase 3 target is `sync-package-readiness`.

This command consolidates the existing package inspection, package summary, and package coverage checks into one local handoff readiness signal.

## Scope

- Read the existing local sync package.
- Reuse existing package inspect, summary, and coverage logic.
- Report package hash, entry count, latest safe/WPS artifact inclusion, root coverage, and package freshness.
- Return warning when workspace sync-root files are newer than the package.

## Safety Constraints

- No package creation.
- No file deletion.
- No WPS launch.
- No remote Git operation.
- Read-only output only.

## Validation

```powershell
python -m unittest tests.test_sync_package_readiness tests.test_cli tests.test_mcp_schema
python -m wps_ai_agent_cli sync-package-readiness
python -m wps_ai_agent_cli regression-run --profile safe --artifact-dir artifacts\regression\safe
```
