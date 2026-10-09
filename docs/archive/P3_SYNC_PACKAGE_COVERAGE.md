# P3-066 Sync Package Coverage

## Outcome

P3-066 adds a read-only package coverage command:

```powershell
python -m wps_ai_agent_cli sync-package-coverage
```

The MCP surface now includes:

```text
wps_agent_sync_package_coverage
```

## What It Reports

- Package exists and can be read as a zip file.
- Package SHA256, byte size, and package-time cutoff.
- Expected package-time workspace entries under `src`, `tests`, `config`, `docs`, `fixtures`, and `scripts`.
- Packaged entry count.
- Missing expected entries.
- Extra entries under sync roots.
- Files newer than the package, reported as hints rather than failures.
- Root-level expected and packaged counts.

## Response Shape

The command returns the standard `CommandResponse` envelope with:

- `data.sync_package_coverage.coverage_status`
- `data.sync_package_coverage.expected_entry_count`
- `data.sync_package_coverage.packaged_entry_count`
- `data.sync_package_coverage.missing_entry_count`
- `data.sync_package_coverage.extra_root_entry_count`
- `data.sync_package_coverage.newer_than_package_count`
- `data.sync_package_coverage.root_coverage`
- `data.sync_package_coverage.deletion_performed = false`

## Safety Notes

- The command is read-only.
- It does not create packages.
- It does not launch WPS.
- It does not delete files.
- It does not use remote Git.

## Verification

The focused verification set is:

```powershell
python -m unittest tests.test_sync_package_coverage tests.test_cli tests.test_mcp_schema
python -m wps_ai_agent_cli sync-package-coverage --request-id p3-066-smoke
python -m wps_ai_agent_cli mcp-catalog-drift --request-id p3-066-drift-check
python -m wps_ai_agent_cli documentation-freshness --request-id p3-066-doc-freshness-check
```

P3-067 refreshes the local sync package after this command and records the final package evidence.
