# P3-013 Spreadsheet Calc Timeout Hardening Report

## Summary

P3-013 investigated the `spreadsheet-calc-smoke` timeout that appeared during the full WPS regression profile after P3-012.

Findings:

- Direct `calc-smoke` runs could pass in about 7 seconds.
- The full WPS regression profile repeatedly timed out on the fixed output path `fixtures\phase3\phase0_calculation_smoke.xlsx`.
- The likely cause was WPS `SaveAs` waiting on an existing output file overwrite or file-lock prompt.

Hardening:

- `calc-smoke` now accepts `--timeout-seconds`.
- `run_spreadsheet_calc_smoke` catches `subprocess.TimeoutExpired` and returns `COM_OPERATION_TIMEOUT` inside the normal `CommandResponse` instead of surfacing a traceback.
- The PowerShell COM script sets `DisplayAlerts = false`.
- The script removes a pre-existing output file before `SaveAs`.
- The command rejects identical input and output paths before launching WPS.
- The WPS regression manifest now runs `calc-smoke` with `--timeout-seconds 30`.

## Evidence

Direct probe:

```powershell
python -m wps_ai_agent_cli calc-smoke --input fixtures\phase0\phase0_calculation_fixture.xlsx --output fixtures\phase3\phase0_calculation_smoke_timeout_probe.xlsx --timeout-seconds 5 --request-id p3-013-calc-timeout-probe-001
```

Result:

- `ok = true`
- `raw_value = 18.0`
- `display_text = 18`

Final WPS regression:

```powershell
python -m wps_ai_agent_cli regression-run --profile wps --include-wps --artifact-dir artifacts\regression\wps --request-id regression-writer-table-p3-013-wps-003
```

Result:

- `ok = true`
- `scenario_count = 4`
- `passed_count = 4`
- `failed_count = 0`
- artifact: `artifacts\regression\wps\regression-run-20261003T105030651877Z-regression-writer-table-p3-013-wps-003.json`

## Remaining Follow-Up

Local process inspection still showed stale `et` processes during the investigation. P3-014 should audit WPS COM lifecycle cleanup and produce safe cleanup guidance without automatically killing processes that may belong to the user.
