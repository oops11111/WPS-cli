# P3 WPS Regression Smoke Report

## Summary

P3-003 executed the WPS-required regression profile from `config/regression_manifest.json` in the local desktop WPS environment. All three WPS scenarios passed.

## Command

```powershell
$env:PYTHONPATH = "src"
python -m wps_ai_agent_cli regression-run --profile wps --include-wps --request-id regression-run-wps-p3-003-001
```

## Results

| Scenario | Component | Result | Output |
| --- | --- | --- | --- |
| `writer-com-smoke` | Writer | passed | `fixtures/phase3/writer_smoke_copy.docx` |
| `spreadsheet-calc-smoke` | Spreadsheets | passed | `fixtures/phase3/phase0_calculation_smoke.xlsx` |
| `writer-convert-smoke` | Writer conversion | passed | `fixtures/phase3/writer_smoke.pdf` |

## Output Evidence

| File | Size |
| --- | --- |
| `fixtures/phase3/writer_smoke_copy.docx` | 26237 bytes |
| `fixtures/phase3/phase0_calculation_smoke.xlsx` | 9122 bytes |
| `fixtures/phase3/writer_smoke.pdf` | 243544 bytes |

## Gaps

- This smoke confirms the configured WPS profile works on the current local machine, but it does not yet compare rendered visual output.
- The regression runner currently reports results in the command response; persistent JSON result artifacts are a logical next step.
- Presentation WPS smoke is already covered by earlier phase evidence but is not yet part of the P3 WPS regression profile.

## Next Task

`P3-004 Regression result artifact export` should persist regression-run output to a timestamped JSON artifact for CI and audit trails.
