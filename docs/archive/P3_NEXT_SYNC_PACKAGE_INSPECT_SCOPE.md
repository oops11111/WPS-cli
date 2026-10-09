# P3-056 Next Sync Package Inspect Scope

## Decision

The next non-destructive Phase 3 target is `sync-package-inspect`.

## Rationale

The project already creates a repeatable local sync package with `cloud-sync-package`. The next useful local-only capability is a read-only inspection command that verifies the existing package before handoff or later refresh work.

## Scope

- Inspect `artifacts\cloud-sync\wps-ai-agent-cli-phase3-sync-cli.zip` by default.
- Report package existence, byte size, SHA256, readability, and entry count.
- Verify the default package roots: `src`, `tests`, `config`, `docs`, and `fixtures`.
- Verify the latest safe and WPS regression artifacts available at package time are present in the zip.
- Expose the same capability through MCP as `wps_agent_sync_package_inspect`.

## Safety

- Read-only.
- Does not create or overwrite packages.
- Does not launch WPS.
- Does not delete files.
- Does not use remote Git or cloud upload.

## Validation

```powershell
python -m unittest tests.test_sync_package_inspect tests.test_cli tests.test_mcp_schema
python -m wps_ai_agent_cli sync-package-inspect
python -m wps_ai_agent_cli mcp-catalog-drift
python -m wps_ai_agent_cli documentation-freshness
```
