# P3-059 Next Sync Package Summary Scope

## Decision

The next non-destructive Phase 3 target is `sync-package-summary`.

## Rationale

`sync-package-inspect` verifies that the current package is usable, but it intentionally keeps the output compact. A read-only content summary makes handoff review easier by showing how the zip is distributed across source, tests, config, docs, fixtures, and packaged evidence.

## Scope

- Summarize `artifacts\cloud-sync\wps-ai-agent-cli-phase3-sync-cli.zip` by default.
- Report package existence, byte size, SHA256, readability, and total entry count.
- Group entries by top-level directory with compressed and uncompressed byte totals.
- Show artifact entries and largest entries with a configurable `--limit`.
- Expose the same capability through MCP as `wps_agent_sync_package_summary`.

## Safety

- Read-only.
- Does not create or overwrite packages.
- Does not launch WPS.
- Does not delete files.
- Does not use remote Git or cloud upload.

## Validation

```powershell
python -m unittest tests.test_sync_package_summary tests.test_cli tests.test_mcp_schema
python -m wps_ai_agent_cli sync-package-summary
python -m wps_ai_agent_cli mcp-catalog-drift
python -m wps_ai_agent_cli documentation-freshness
```
