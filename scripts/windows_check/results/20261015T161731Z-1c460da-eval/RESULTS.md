# Windows agent evaluation

- Date: 2026-10-15 17:02 UTC
- Commit: `1c460da` on `main`
- Machine: Windows-10-10.0.19045-SP0; Python 3.12.15
- WPS: wps.exe 12,8,2,18913, et.exe 12,8,2,18913, wpp.exe 12,8,2,18913
- Written by `scripts/windows_check/run_windows_check.py`; nothing in this file was typed by hand.

## Prerequisites

| Check | Result | Detail |
| --- | --- | --- |
| commit | ok | 1c460da on main |
| python | ok | C:\Users\admin\.lody\repos\github---oops11111---wps-cli\worktrees\892d82f5-59c6-4cf8-bc52-46c8e7df5f60\.venv\Scripts\python.exe |
| windows | ok | Windows-10-10.0.19045-SP0 |
| claude answers | ok | OK |
| no WPS process running | ok | none |
| open command .docx | ok | "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\wps.exe" "%1" |
| open command .xlsx | ok | "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\et.exe" "%1" |
| open command .pptx | ok | "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\wpp.exe" "%1" |
| inspect-env | ok | {"presentation": "kwpp.Application", "spreadsheets": "ket.Application", "writer": "kwps.Application"} |

## Agent evaluation

```
python scripts/windows_check/run_windows_check.py eval --only wps-open-document-export-text --only wps-open-writer-selection-replace --only wps-open-writer-selection-insert --only wps-open-writer-selection-delete --only wps-open-presentation-selection-replace --only wps-open-presentation-selection-insert --only wps-open-presentation-selection-delete --only wps-open-spreadsheet-selection-replace --only wps-open-spreadsheet-selection-delete --only wps-open-save-document --only wps-open-save-as-untitled --repeat 3 --min-passes 2
```

Claude Code CLI 2.1.295 (Claude Code), model CLI default, launch mode `default`. **8/10 tasks passed**, 1 skipped. Each task passes with at least 2 of 3 runs. Task workspaces: `C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261015T161731Z-1c460da-eval`.

| Task | Passes | Turns | `wps-agent` calls | Tool errors | `off_path_calls` | `off_path_tools` |
| --- | --- | --- | --- | --- | --- | --- |
| `wps-open-document-export-text` | 3/3 | 4.0 (4, 4, 4) | 6 | 0 | 0 |  |
| `wps-open-writer-selection-replace` | 3/3 | 5.7 (6, 6, 5) | 14 | 0 | 1 | `validate_document` |
| `wps-open-writer-selection-insert` | 3/3 | 9.7 (7, 16, 6) | 23 | 0 | 7 | `export_open_document_text`, `snapshot_document`, `validate_document` |
| `wps-open-presentation-selection-replace` | 3/3 | 6.3 (7, 6, 6) | 15 | 0 | 2 | `operation`, `snapshot_document` |
| `wps-open-save-document` | 3/3 | 5.7 (5, 5, 7) | 14 | 0 | 1 | `snapshot_document` |
| `wps-open-writer-selection-delete` | 3/3 | 5.7 (6, 6, 5) | 13 | 0 | 0 |  |
| `wps-open-presentation-selection-insert` | 3/3 | 6.3 (9, 5, 5) | 15 | 0 | 1 | `operations` |
| `wps-open-presentation-selection-delete` | 3/3 | 6.7 (7, 6, 7) | 16 | 0 | 0 |  |
| `wps-open-spreadsheet-selection-replace` | 1/3 | 2.3 (7, 0, 0) | 6 | 0 | 2 | `spreadsheet_read`, `spreadsheet_sheets` |
| `wps-open-spreadsheet-selection-delete` | skipped | | | | | |
| `wps-open-save-as-untitled` | 0/3 | 16.0 (16, 16, 16) | 38 | 24 | 20 | `inspect_env`, `mcp_call`, `mcp_config_audit`, `mcp_server`, `mcp_smoke`, `mcp_tool_schema`, `mcp_tools`, `register_document`, `regression_manifest` |

### Runs

- `wps-open-document-export-text` run 1 (pass): cleanup: fixture closed; processes stopped 47812
- `wps-open-document-export-text` run 2 (pass): cleanup: fixture closed; processes left running: WPS still lists report.docx
- `wps-open-document-export-text` run 3 (pass): cleanup: fixture closed; processes none started
- `wps-open-writer-selection-replace` run 1 (pass): cleanup: fixture closed; processes none started
- `wps-open-writer-selection-replace` run 2 (pass): cleanup: fixture closed; processes none started
- `wps-open-writer-selection-replace` run 3 (pass): cleanup: fixture closed; processes none started
- `wps-open-writer-selection-insert` run 1 (pass): cleanup: fixture closed; processes none started
- `wps-open-writer-selection-insert` run 2 (pass): cleanup: fixture closed; processes none started
- `wps-open-writer-selection-insert` run 3 (pass): cleanup: fixture closed; processes none started
- `wps-open-presentation-selection-replace` run 1 (pass): cleanup: fixture closed; processes left running: WPS still lists deck.pptx
- `wps-open-presentation-selection-replace` run 2 (pass): cleanup: fixture closed; processes none started
- `wps-open-presentation-selection-replace` run 3 (pass): cleanup: fixture closed; processes none started
- `wps-open-save-document` run 1 (pass): cleanup: fixture closed; processes none started
- `wps-open-save-document` run 2 (pass): cleanup: fixture closed; processes none started
- `wps-open-save-document` run 3 (pass): cleanup: fixture closed; processes none started
- `wps-open-writer-selection-delete` run 1 (pass): cleanup: fixture closed; processes none started
- `wps-open-writer-selection-delete` run 2 (pass): cleanup: fixture closed; processes none started
- `wps-open-writer-selection-delete` run 3 (pass): cleanup: fixture closed; processes none started
- `wps-open-presentation-selection-insert` run 1 (pass): cleanup: fixture closed; processes none started
- `wps-open-presentation-selection-insert` run 2 (pass): cleanup: fixture closed; processes none started
- `wps-open-presentation-selection-insert` run 3 (pass): cleanup: fixture closed; processes none started
- `wps-open-presentation-selection-delete` run 1 (pass): cleanup: fixture closed; processes none started
- `wps-open-presentation-selection-delete` run 2 (pass): cleanup: fixture closed; processes none started
- `wps-open-presentation-selection-delete` run 3 (pass): cleanup: fixture closed; processes none started
- `wps-open-spreadsheet-selection-replace` run 1 (pass): cleanup: fixture COM_OPERATION_FAILED (服务器出现意外情况。 (0x80010105 (RPC_E_SERVERFAULT))); processes stopped 8140
- `wps-open-spreadsheet-selection-replace` run 2 (FAIL): setup failed: WPS did not list status.xlsx as open within 45 s (launch mode default): WPS_INSTANCE_NOT_AUTOMATABLE: WPS Spreadsheets is running with a window, but it did not register for automation, so its open documents cannot be reached. This happens when WPS was started by opening a file directly, for example by double-clicking it. Save your work in WPS, close every WPS Spreadsheets window, then reopen the document with the /Automation option, for example: wps.exe /Automation "<path to the document>". Nothing was launched, closed or changed.
- `wps-open-spreadsheet-selection-replace` run 3 (FAIL): setup failed: WPS did not list status.xlsx as open within 45 s (launch mode default): WPS_INSTANCE_NOT_AUTOMATABLE: WPS Spreadsheets is running with a window, but it did not register for automation, so its open documents cannot be reached. This happens when WPS was started by opening a file directly, for example by double-clicking it. Save your work in WPS, close every WPS Spreadsheets window, then reopen the document with the /Automation option, for example: wps.exe /Automation "<path to the document>". Nothing was launched, closed or changed.
- `wps-open-spreadsheet-selection-delete` skipped: WPS did not list status.xlsx as open within 45 s (launch mode default): WPS_INSTANCE_NOT_AUTOMATABLE: WPS Spreadsheets is running with a window, but it did not register for automation, so its open documents cannot be reached. This happens when WPS was started by opening a file directly, for example by double-clicking it. Save your work in WPS, close every WPS Spreadsheets window, then reopen the document with the /Automation option, for example: wps.exe /Automation "<path to the document>". Nothing was launched, closed or changed.
- `wps-open-save-as-untitled` run 1 (FAIL): failed checks: operation_recorded (no record); file_text (file missing) | error codes: INPUT_FILE_NOT_FOUND, MCP_ADAPTER_CALL_REJECTED, MCP_CONFIG_AUDIT_FAILED, MCP_SMOKE_TOOL_NOT_READ_ONLY, MCP_TOOL_EXECUTION_FAILED, UNTITLED_DOCUMENT_NOT_FOUND | cleanup: untitled 文字文稿1 closed; fixture closed; processes stopped 49260
- `wps-open-save-as-untitled` run 2 (FAIL): failed checks: operation_recorded (no record); file_text (file missing) | error codes: MCP_ADAPTER_CALL_REJECTED, MCP_SMOKE_TOOL_NOT_READ_ONLY, UNTITLED_DOCUMENT_NOT_FOUND | cleanup: untitled 文字文稿1 closed; fixture closed; processes stopped 41124
- `wps-open-save-as-untitled` run 3 (FAIL): failed checks: operation_recorded (no record); file_text (file missing) | error codes: INVALID_ARGUMENT, MCP_ADAPTER_CALL_REJECTED, UNTITLED_DOCUMENT_NOT_FOUND | cleanup: untitled 文字文稿1 closed; fixture closed; processes stopped 32876

### WPS processes after the run

- None.
