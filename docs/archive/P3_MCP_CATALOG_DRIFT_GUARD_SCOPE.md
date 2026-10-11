# P3-035 MCP Catalog Drift Guard Scope

## Goal

Define a non-destructive guard that makes MCP catalog changes explicit before packaging or handoff.

## Guard Shape

- CLI command: `mcp-catalog-drift`
- Baseline file: `config\mcp_catalog_guard.json`
- Default behavior: compare the current `mcp-catalog-snapshot` result against the baseline.
- Safety posture: read-only, no WPS launch, no cleanup, no file mutation except optional regression artifact export performed by existing regression tooling.

## Compared Fields

- Total MCP tool count
- Category counts
- Mutating tool count
- WPS-required tool count
- Mutating tools missing safety notes

## Pass/Fail Rule

The guard passes only when every expected count matches the current catalog and there are no mutating tools missing safety notes. Any mismatch should return structured drift details so the next developer can intentionally approve, document, or update the baseline.

## Regression Integration

P3-036 should add the guard to the safe regression profile. The safe profile must remain local-only and must not launch desktop WPS.
