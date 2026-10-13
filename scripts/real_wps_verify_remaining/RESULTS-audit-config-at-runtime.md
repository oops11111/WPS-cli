# Windows re-run of the safe profile after the audit-config fix

**Change tested:** branch `fix/audit-config-at-runtime` (PR #32), which renders the `mcp-config-audit` configuration at run time with the running interpreter.
**Reported by:** the Windows operator, as a table of results. Not re-run here.

`regression-run --profile safe` on Windows: **7 of 7 pass.**

| Scenario | Result |
| --- | --- |
| cli-plan | pass |
| cli-phase3-next | pass |
| mcp-tools-count | pass (85 tools) |
| mcp-catalog-drift | pass |
| mcp-smoke | pass |
| mcp-config-audit | pass |
| security-boundary-audit | pass |

The earlier failure of `mcp-config-audit` on Windows came from the `python` Store alias (exit 9009, no output). This run used the interpreter that runs the regression, so the alias is no longer involved.
