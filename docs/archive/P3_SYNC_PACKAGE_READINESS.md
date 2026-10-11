# P3-069 Sync Package Readiness

## Outcome

P3-069 adds a read-only package readiness command:

```powershell
python -m wps_ai_agent_cli sync-package-readiness
```

It also exposes the same behavior through MCP as `wps_agent_sync_package_readiness`.

## Behavior

The command combines:

- `sync-package-inspect`
- `sync-package-summary`
- `sync-package-coverage`

It returns a single `readiness_status` plus package hash, entry count, latest safe/WPS artifact inclusion, root coverage, top-level package groups, missing-entry count, and newer-than-package workspace entries. It requires both the latest Writer structure and nested-bookmark parity reports in the package, validates their passed checks, compares each source/script hash with the current controlled fixture and audit script, compares four parser/text-inspection/parity implementation hashes with the current workspace, and checks the packaged bytes. `writer_parity_evidence.status` and `writer_nested_parity_evidence.status` distinguish `missing`, `failed`, `stale`, `stale_package`, and `passed` without launching WPS. A source-code change invalidates prior WPS evidence even when file modification times are unchanged.

## Safety

- Read-only: yes.
- Launches WPS: no.
- Deletes files: no.
- Requires remote Git: no.
- Creates or refreshes packages: no.

## Validation

```powershell
python -m unittest tests.test_sync_package_readiness tests.test_cli tests.test_mcp_schema
python -m wps_ai_agent_cli sync-package-readiness --request-id p3-069-smoke
```

P3-070 will refresh the local sync package after this command and record final package-readiness evidence.
