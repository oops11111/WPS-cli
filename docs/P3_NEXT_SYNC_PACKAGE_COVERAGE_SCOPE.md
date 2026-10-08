# P3-065 Next Sync Package Coverage Scope

## Decision

The next non-destructive Phase 3 target is `sync-package-coverage`.

## Rationale

`sync-package-manifest` lists package contents, but it does not answer whether the package covers the workspace files that should have been included. A read-only coverage command compares package entries with package-time workspace files under the default sync roots.

## Scope

- Compare `artifacts\cloud-sync\wps-ai-agent-cli-phase3-sync-cli.zip` against `src`, `tests`, `config`, `docs`, and `fixtures`.
- Use the package modification time as a cutoff so files added after packaging are reported as newer-than-package hints instead of immediate failures.
- Report expected entry count, packaged entry count, missing entries, extra root entries, and root-level coverage.
- Expose the same capability through MCP as `wps_agent_sync_package_coverage`.

## Safety

- Read-only.
- Does not create or overwrite packages.
- Does not launch WPS.
- Does not delete files.
- Does not use remote Git or cloud upload.

## Validation

```powershell
python -m unittest tests.test_sync_package_coverage tests.test_cli tests.test_mcp_schema
python -m wps_ai_agent_cli sync-package-coverage
python -m wps_ai_agent_cli mcp-catalog-drift
python -m wps_ai_agent_cli documentation-freshness
```
