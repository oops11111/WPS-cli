# P3-057 Sync Package Inspect

## Outcome

P3-057 adds a read-only inspection command for existing local sync packages:

```powershell
python -m wps_ai_agent_cli sync-package-inspect
```

The MCP surface now includes:

```text
wps_agent_sync_package_inspect
```

## What It Checks

- Package exists and can be read as a zip file.
- Package has entries.
- Package SHA256 and byte size are reported.
- Expected roots are represented: `src`, `tests`, `config`, `docs`, `fixtures`, and `scripts`.
- Latest safe and WPS regression artifacts available at package time are included. The latest Writer parity report must also be included with identical bytes; a newer local report invalidates an older package.

## Response Shape

The command returns the standard `CommandResponse` envelope with:

- `data.sync_package_inspect.inspection_status`
- `data.sync_package_inspect.entry_count`
- `data.sync_package_inspect.sha256`
- `data.sync_package_inspect.root_coverage`
- `data.sync_package_inspect.latest_artifacts`
- `data.sync_package_inspect.deletion_performed = false`

## Safety Notes

- The command is read-only.
- It does not create packages.
- It does not launch WPS.
- It does not delete files.
- It does not use remote Git.

## Verification

The focused verification set is:

```powershell
python -m unittest tests.test_sync_package_inspect tests.test_cli tests.test_mcp_schema
python -m wps_ai_agent_cli sync-package-inspect --request-id p3-057-smoke
python -m wps_ai_agent_cli mcp-catalog-drift --request-id p3-057-drift-check
python -m wps_ai_agent_cli documentation-freshness --request-id p3-057-doc-freshness-check
```

P3-058 will refresh the local sync package after this command and record the final package evidence.
