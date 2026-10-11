# P3-007 Security Boundary Audit

Date: 2026-10-03

## Scope

This audit covers mutating CLI and MCP tools exposed through `mcp_schema.py`. The goal is to ensure document-changing or file-state-changing tools have explicit request tracing, dry-run or risk boundaries, backup/protection evidence, recovery linkage, and WPS/file-system boundary notes.

## Implemented Guard

`security-audit` now performs a machine-readable audit of every MCP schema where `mutates_document = true`.

Checked fields:

- `request_id` is available in the input schema.
- idempotency text explicitly mentions `request_id`.
- `task_id` is available for task status and recovery correlation.
- `dry_run` exists or the tool has explicit safety notes.
- backup or pre-restore protection is documented.
- file-system boundary is documented.
- WPS boundary is documented when the tool requires WPS.

## Audited Mutating Tools

| Tool | CLI command | Requires WPS | Result |
| --- | --- | --- | --- |
| `wps_agent_backup_document` | `backup-document` | no | passed |
| `wps_agent_restore_backup` | `restore-backup` | no | passed |
| `wps_agent_writer_replace` | `writer-replace` | yes | passed |
| `wps_agent_spreadsheet_write` | `spreadsheet-write` | yes | passed |
| `wps_agent_spreadsheet_formula_write` | `spreadsheet-formula-write` | yes | passed |
| `wps_agent_presentation_replace` | `presentation-replace` | yes | passed |

## Evidence

Command:

```powershell
$env:PYTHONPATH='src'; & 'C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m wps_ai_agent_cli security-audit --request-id p3-007-security-audit-001
```

Result:

- `schema_count`: 37
- `mutating_tool_count`: 6
- `passed_tool_count`: 6
- `failed_tool_count`: 0
- `validation.status`: `passed`

## Regression Coverage

`security-audit` is now part of the safe regression profile as `security-boundary-audit`. The safe profile also raises the expected MCP tool count to 37.

## Follow-up

The next production-readiness task should capture a performance baseline for core read-only and regression commands, starting with MCP tools/list, batch reporting, and safe regression runtime.
