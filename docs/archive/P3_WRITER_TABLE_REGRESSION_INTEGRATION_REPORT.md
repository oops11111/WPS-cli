# P3-012 Writer Table Regression Integration Report

## Summary

P3-012 integrated the Writer table update capability into repeatable regression evidence without adding WPS launch requirements to the safe CI profile.

New entry points:

- CLI: `writer-table-smoke`
- MCP: `wps_agent_writer_table_smoke`
- WPS regression scenario: `writer-table-smoke`

The smoke command copies a Writer fixture to an output path, registers the output copy, runs the real `writer-table-write` path through WPS COM, checks that a backup exists, and verifies that the backup can be selected by `restore-backup --dry-run`.

## Regression Behavior

Safe profile:

- Still excludes WPS-required scenarios.
- Passed with 6 scenarios.
- Artifact: `artifacts\regression\safe\regression-run-20261003T103958462595Z-regression-writer-table-p3-012-safe-002.json`.

WPS profile:

- Now contains 4 WPS scenarios.
- `writer-table-smoke` passed with:
  - `data.writer_table.validation_passed = true`
  - `data.restore_check.ok = true`
  - backup evidence under `.wps-agent\backups`
- Artifact: `artifacts\regression\wps\regression-run-20261003T104229263780Z-regression-writer-table-p3-012-wps-002.json`.

At P3-012 close, the full WPS profile still had one unrelated failing scenario: the existing `spreadsheet-calc-smoke` timed out. The regression runner now records such exceptions as structured scenario failures instead of crashing the whole run. P3-013 subsequently hardened `calc-smoke` and restored full WPS profile pass status.

## Verification

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests
python -m wps_ai_agent_cli regression-run --profile safe --artifact-dir artifacts\regression\safe --request-id regression-writer-table-p3-012-safe-002
python -m wps_ai_agent_cli writer-table-smoke --input fixtures\phase3\writer_table_fixture.docx --output fixtures\phase3\writer_table_regression_smoke.docx --table-index 1 --row 2 --column 3 --text REGRESSION_STATUS --request-id p3-012-writer-table-smoke-001
python -m wps_ai_agent_cli regression-run --profile wps --include-wps --artifact-dir artifacts\regression\wps --request-id regression-writer-table-p3-012-wps-002
```

Observed:

- 88 unit tests passed.
- Safe regression passed.
- Single Writer table smoke passed.
- Full WPS regression produced a structured artifact; Writer table smoke passed. The spreadsheet timeout was fixed in P3-013.
