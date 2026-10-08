# P3-060 Sync Package Summary

## Outcome

P3-060 adds a read-only content summary command for existing local sync packages:

```powershell
python -m wps_ai_agent_cli sync-package-summary
```

The MCP surface now includes:

```text
wps_agent_sync_package_summary
```

## What It Reports

- Package exists and can be read as a zip file.
- Package SHA256, byte size, and entry count.
- Top-level groups with entry counts, compressed bytes, uncompressed bytes, and sample entries.
- Artifact entries under `artifacts/`.
- Largest entries, limited by `--limit`.

## Response Shape

The command returns the standard `CommandResponse` envelope with:

- `data.sync_package_summary.summary_status`
- `data.sync_package_summary.entry_count`
- `data.sync_package_summary.sha256`
- `data.sync_package_summary.top_level_groups`
- `data.sync_package_summary.artifact_entries`
- `data.sync_package_summary.largest_entries`
- `data.sync_package_summary.deletion_performed = false`

## Safety Notes

- The command is read-only.
- It does not create packages.
- It does not launch WPS.
- It does not delete files.
- It does not use remote Git.

## Verification

The focused verification set is:

```powershell
python -m unittest tests.test_sync_package_summary tests.test_cli tests.test_mcp_schema
python -m wps_ai_agent_cli sync-package-summary --request-id p3-060-smoke
python -m wps_ai_agent_cli mcp-catalog-drift --request-id p3-060-drift-check
python -m wps_ai_agent_cli documentation-freshness --request-id p3-060-doc-freshness-check
```

P3-061 will refresh the local sync package after this command and record the final package evidence.
