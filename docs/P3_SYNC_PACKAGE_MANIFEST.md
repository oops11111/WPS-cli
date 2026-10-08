# P3-063 Sync Package Manifest

## Outcome

P3-063 adds a read-only manifest command for existing local sync packages:

```powershell
python -m wps_ai_agent_cli sync-package-manifest --prefix docs --limit 20
```

The MCP surface now includes:

```text
wps_agent_sync_package_manifest
```

## What It Reports

- Package exists and can be read as a zip file.
- Package SHA256, byte size, and total entry count.
- Matching entry count and returned entry count.
- Whether the result was truncated by `--limit`.
- Entry names, top-level groups, compressed bytes, uncompressed bytes, and directory flags.
- Expected root presence for `src`, `tests`, `config`, `docs`, `fixtures`, and `scripts`.

## Response Shape

The command returns the standard `CommandResponse` envelope with:

- `data.sync_package_manifest.manifest_status`
- `data.sync_package_manifest.entry_count`
- `data.sync_package_manifest.match_count`
- `data.sync_package_manifest.returned_count`
- `data.sync_package_manifest.entries`
- `data.sync_package_manifest.truncated`
- `data.sync_package_manifest.deletion_performed = false`

## Safety Notes

- The command is read-only.
- It does not create packages.
- It does not launch WPS.
- It does not delete files.
- It does not use remote Git.

## Verification

The focused verification set is:

```powershell
python -m unittest tests.test_sync_package_manifest tests.test_cli tests.test_mcp_schema
python -m wps_ai_agent_cli sync-package-manifest --prefix docs --limit 20 --request-id p3-063-smoke
python -m wps_ai_agent_cli mcp-catalog-drift --request-id p3-063-drift-check
python -m wps_ai_agent_cli documentation-freshness --request-id p3-063-doc-freshness-check
```

P3-064 will refresh the local sync package after this command and record the final package evidence.
