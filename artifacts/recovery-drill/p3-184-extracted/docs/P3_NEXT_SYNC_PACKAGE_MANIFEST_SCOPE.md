# P3-062 Next Sync Package Manifest Scope

## Decision

The next non-destructive Phase 3 target is `sync-package-manifest`.

## Rationale

`sync-package-summary` shows package distribution, but handoff review sometimes needs exact entry paths. A read-only manifest command lists package entries with optional prefix filtering so a reviewer can inspect a targeted slice such as `docs/` or `src/wps_ai_agent_cli/`.

## Scope

- List entries from `artifacts\cloud-sync\wps-ai-agent-cli-phase3-sync-cli.zip` by default.
- Report package existence, readability, byte size, SHA256, and total entry count.
- Support `--prefix` to filter zip paths.
- Support `--limit` to cap returned entries.
- Expose the same capability through MCP as `wps_agent_sync_package_manifest`.

## Safety

- Read-only.
- Does not create or overwrite packages.
- Does not launch WPS.
- Does not delete files.
- Does not use remote Git or cloud upload.

## Validation

```powershell
python -m unittest tests.test_sync_package_manifest tests.test_cli tests.test_mcp_schema
python -m wps_ai_agent_cli sync-package-manifest --prefix docs --limit 20
python -m wps_ai_agent_cli mcp-catalog-drift
python -m wps_ai_agent_cli documentation-freshness
```
