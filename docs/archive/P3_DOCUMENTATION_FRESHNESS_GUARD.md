# P3-051 Documentation Freshness Guard

## Outcome

P3-051 adds a read-only `documentation-freshness` command and MCP tool `wps_agent_documentation_freshness`.

The command scans current-facing docs and config for stale tool-count, `expected-min-tools`, and current next-task references.

## Command

```powershell
python -m wps_ai_agent_cli documentation-freshness
```

## Checked Files

- `README.md`
- `docs\MCP_SERVER_CLIENT_CONFIG.md`
- `docs\MCP_TOOL_SCHEMA_DRAFT.md`
- `docs\REGRESSION_MANIFEST.md`
- `docs\PHASE3_RELEASE_READINESS_REFRESH.md`
- `docs\TASK_BOARD.md`
- `config\regression_manifest.json`
- `config\mcp_catalog_guard.json`

## Safety

- Read-only: yes.
- Edits files: no.
- Runs regression: no.
- Creates packages: no.
- Launches WPS: no.
- Uses remote Git or cloud services: no.

## Validation

- Added focused unit coverage in `tests\test_documentation_freshness.py`.
- Added CLI parser coverage for `documentation-freshness`.
- Added MCP schema coverage for `wps_agent_documentation_freshness`.
- Safe regression now covers documentation freshness as a non-WPS scenario.
