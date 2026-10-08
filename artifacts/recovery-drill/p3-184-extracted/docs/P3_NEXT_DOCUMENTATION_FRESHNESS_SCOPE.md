# P3-050 Next Non-Destructive Capability Scope

## Selected Target

Implement a read-only `documentation-freshness` guard for the local-only Phase 3 workflow.

The command will scan current documentation and configuration references for stale MCP tool counts, stale `expected-min-tools` values, or stale current next-task references.

## Scope

- Inspect the current MCP tool count from the live schema.
- Inspect the current Phase 3 next task from the task ledger.
- Scan current-facing docs and config files for stale current-state references.
- Validate `config\mcp_catalog_guard.json` expected tool count against the live schema.
- Validate `config\regression_manifest.json` still references the current next task.
- Expose the same data through MCP as `wps_agent_documentation_freshness`.

## Safety Constraints

- Read-only only.
- Do not edit documentation automatically.
- Do not run regression.
- Do not create packages.
- Do not launch WPS.
- Do not delete files.
- Do not contact remote Git or cloud services.

## Validation

- Add focused unit tests for fresh and stale documentation scenarios.
- Add CLI parser and MCP schema coverage.
- Add the command to the safe regression profile after implementation.
- Refresh MCP catalog drift baseline after reviewing the new read-only tool.
