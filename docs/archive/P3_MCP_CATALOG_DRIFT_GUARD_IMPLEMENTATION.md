# P3-036 MCP Catalog Drift Guard Implementation

## Summary

P3-036 adds a read-only MCP catalog drift guard:

```powershell
python -m wps_ai_agent_cli mcp-catalog-drift
```

It compares the current MCP catalog snapshot with:

```text
config\mcp_catalog_guard.json
```

## Guard Baseline

The baseline currently expects:

- Tool count: 48
- Mutating tools: 8
- WPS-required tools: 9
- Read-only tools: 40
- Mutating tools missing safety notes: 0
- MCP category count: 8

## Safety

- Read-only only.
- Does not launch WPS.
- Does not update the baseline automatically.
- Reports structured drift details for review.

## Verification

Focused verification passed:

```powershell
python -m unittest tests.test_mcp_catalog tests.test_mcp_schema tests.test_cli
python -m wps_ai_agent_cli mcp-catalog-drift --request-id p3-036-drift-guard-001
python -m wps_ai_agent_cli mcp-catalog-snapshot --request-id p3-036-catalog-snapshot-001
```

Results:

- Focused tests: 17 passed.
- Drift count: 0.
- Current MCP tool count: 48.
- Safety-note drift: none.

## Regression

The safe regression manifest now includes `mcp-catalog-drift` and expects zero drift.
