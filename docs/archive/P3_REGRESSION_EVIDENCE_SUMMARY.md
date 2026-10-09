# P3-039 Regression Evidence Summary

## Summary

P3-039 adds a read-only regression evidence summary command:

```powershell
python -m wps_ai_agent_cli regression-evidence
```

It reads existing regression artifacts and does not execute regression scenarios or launch WPS.

## Reported Evidence

- Latest safe regression artifact
- Latest WPS regression artifact
- Scenario count, passed count, and failed count per profile
- Result IDs per profile
- Aggregate `evidence_status`
- Read-only and no-WPS-launch flags

## Verification

Focused verification passed:

```powershell
python -m unittest tests.test_regression_evidence tests.test_cli tests.test_mcp_schema tests.test_mcp_catalog
python -m wps_ai_agent_cli regression-evidence --request-id p3-039-regression-evidence-001
python -m wps_ai_agent_cli mcp-catalog-drift --request-id p3-039-drift-after-evidence
```

Results:

- Focused tests: 19 passed.
- Regression evidence status: passed.
- Safe regression artifact summarized: 7/7 passed.
- WPS regression artifact summarized: 4/4 passed.
- MCP catalog drift: 0.
- MCP tool count: 49.
