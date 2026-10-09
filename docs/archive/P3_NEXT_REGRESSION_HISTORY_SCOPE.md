# P3-053 Next Non-Destructive Capability Scope

## Selected Target

Implement a read-only `regression-history` summary for the local-only Phase 3 workflow.

The command will report recent safe and WPS regression artifacts, latest pass state, scenario counts, and recent pass/fail trends without executing regression or launching WPS.

## Scope

- Read recent `artifacts\regression\safe` and `artifacts\regression\wps` JSON artifacts.
- Summarize latest artifact per profile.
- Report recent artifact counts, passed counts, failed counts, scenario counts, and result ids.
- Allow a small `--limit` for artifacts per profile.
- Expose the same data through MCP as `wps_agent_regression_history`.

## Safety Constraints

- Read-only only.
- Do not run regression.
- Do not launch WPS.
- Do not create packages.
- Do not delete files.
- Do not contact remote Git or cloud services.

## Validation

- Add focused unit tests for passed history and missing-profile warning states.
- Add CLI parser and MCP schema coverage.
- Add the command to the safe regression profile after implementation.
- Refresh MCP catalog drift baseline after reviewing the new read-only tool.
