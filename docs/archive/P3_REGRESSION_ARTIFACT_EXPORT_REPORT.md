# P3-004 Regression Artifact Export Report

Date: 2026-10-03

## Result

`P3-004 Regression result artifact export` is complete. `regression-run` now accepts `--artifact-dir` and writes a timestamped JSON artifact while preserving the normal JSON stdout response.

## Command

```powershell
$env:PYTHONPATH='src'; & 'C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m wps_ai_agent_cli regression-run --profile safe --artifact-dir artifacts\regression --request-id regression-artifact-p3-004-001
```

## Evidence

- Safe regression profile passed: 5 passed, 0 failed.
- Artifact created: `artifacts\regression\regression-run-20261003T063513662051Z-regression-artifact-p3-004-001.json`.
- CLI response includes `data.artifact` with `created`, `filename`, `path`, and `timestamp`.
- MCP schema for `wps_agent_regression_run` now accepts `artifact_dir`.

## Verification

```powershell
$env:PYTHONPATH='src'; & 'C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests
```

Result: 78 tests passed.

## Next Task

`P3-005 Regression artifact CI handoff` should document the CI invocation, artifact retention path, and pass/fail gates for safe and WPS regression profiles.
