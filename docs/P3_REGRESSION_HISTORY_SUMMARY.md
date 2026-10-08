# P3-054 Regression History Summary

## Outcome

P3-054 adds a read-only `regression-history` command and MCP tool `wps_agent_regression_history`.

The command summarizes recent safe and WPS regression artifacts without running regression or launching WPS.

## Command

```powershell
python -m wps_ai_agent_cli regression-history
python -m wps_ai_agent_cli regression-history --limit 3
```

## Reported Evidence

- Latest artifact per profile.
- Recent artifact count per profile.
- Recent pass/fail count per profile.
- Scenario counts, passed counts, failed counts, WPS inclusion flag, and result ids.

## Safety

- Read-only: yes.
- Runs regression: no.
- Launches WPS: no.
- Creates packages: no.
- Deletes files: no.
- Uses remote Git or cloud services: no.

## Validation

- Added focused unit coverage in `tests\test_regression_history.py`.
- Added CLI parser coverage for `regression-history`.
- Added MCP schema coverage for `wps_agent_regression_history`.
- Safe regression now covers regression history as a non-WPS scenario.
