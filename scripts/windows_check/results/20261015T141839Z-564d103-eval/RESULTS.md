# Windows agent evaluation

- Date: 2026-10-15 15:37 UTC
- Commit: `57fda43` on `cursor/phase7-windows-564d103`
- Machine: Windows-10-10.0.19045-SP0; Python 3.12.15
- WPS: wps.exe 12,8,2,18913, et.exe 12,8,2,18913, wpp.exe 12,8,2,18913
- Written by `scripts/windows_check/run_windows_check.py`; nothing in this file was typed by hand.

## Prerequisites

| Check | Result | Detail |
| --- | --- | --- |
| commit | ok | 57fda43 on cursor/phase7-windows-564d103 |
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

Claude Code CLI 2.1.295 (Claude Code), model CLI default, launch mode `default`. **8/9 tasks passed**, 2 skipped. Each task passes with at least 2 of 3 runs. Task workspaces: `C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261015T141839Z-564d103-eval`.

| Task | Passes | Turns | `wps-agent` calls | Tool errors | `off_path_calls` | `off_path_tools` |
| --- | --- | --- | --- | --- | --- | --- |
| `wps-open-document-export-text` | 3/3 | 4.7 (6, 4, 4) | 7 | 0 | 0 |  |
| `wps-open-writer-selection-replace` | 3/3 | 7.0 (10, 6, 5) | 18 | 1 | 4 | `mutation_request_inspect`, `validate_document` |
| `wps-open-writer-selection-insert` | 3/3 | 8.3 (10, 6, 9) | 22 | 0 | 7 | `snapshot_document`, `validate_document` |
| `wps-open-presentation-selection-replace` | 3/3 | 5.0 (6, 5, 4) | 12 | 0 | 0 |  |
| `wps-open-save-document` | 3/3 | 7.0 (6, 7, 8) | 17 | 0 | 3 | `operation`, `snapshot_document` |
| `wps-open-writer-selection-delete` | 3/3 | 5.7 (7, 5, 5) | 14 | 0 | 1 | `operation` |
| `wps-open-presentation-selection-insert` | 2/3 | 7.3 (5, 8, 9) | 19 | 1 | 3 | `operation`, `presentation_replace`, `snapshot_document` |
| `wps-open-presentation-selection-delete` | 3/3 | 6.0 (5, 5, 8) | 13 | 0 | 0 |  |
| `wps-open-spreadsheet-selection-replace` | skipped | | | | | |
| `wps-open-spreadsheet-selection-delete` | skipped | | | | | |
| `wps-open-save-as-untitled` | 0/3 | 10.7 (16, 0, 16) | 22 | 11 | 14 | `inspect_env`, `mcp_call`, `mcp_tool_schema`, `mcp_tools`, `operation`, `operations`, `scan_dir` |

### Runs

- `wps-open-document-export-text` run 1 (pass): cleanup: fixture closed; processes left running: WPS still lists open documents
- `wps-open-document-export-text` run 2 (pass): cleanup: fixture closed; processes none started
- `wps-open-document-export-text` run 3 (pass): cleanup: fixture closed; processes none started
- `wps-open-writer-selection-replace` run 1 (pass): error codes: VALIDATION_FAILED | cleanup: fixture closed; processes none started
- `wps-open-writer-selection-replace` run 2 (pass): cleanup: fixture closed; processes none started
- `wps-open-writer-selection-replace` run 3 (pass): cleanup: fixture closed; processes none started
- `wps-open-writer-selection-insert` run 1 (pass): cleanup: fixture closed; processes none started
- `wps-open-writer-selection-insert` run 2 (pass): cleanup: fixture closed; processes none started
- `wps-open-writer-selection-insert` run 3 (pass): cleanup: fixture closed; processes none started
- `wps-open-presentation-selection-replace` run 1 (pass): cleanup: fixture closed; processes left running: WPS still lists open documents
- `wps-open-presentation-selection-replace` run 2 (pass): cleanup: fixture closed; processes none started
- `wps-open-presentation-selection-replace` run 3 (pass): cleanup: fixture closed; processes none started
- `wps-open-save-document` run 1 (pass): cleanup: fixture closed; processes left running: WPS still lists open documents
- `wps-open-save-document` run 2 (pass): cleanup: fixture closed; processes none started
- `wps-open-save-document` run 3 (pass): cleanup: fixture closed; processes none started
- `wps-open-writer-selection-delete` run 1 (pass): cleanup: fixture closed; processes none started
- `wps-open-writer-selection-delete` run 2 (pass): cleanup: fixture closed; processes none started
- `wps-open-writer-selection-delete` run 3 (pass): cleanup: fixture closed; processes none started
- `wps-open-presentation-selection-insert` run 1 (pass): cleanup: fixture closed; processes none started
- `wps-open-presentation-selection-insert` run 2 (pass): cleanup: fixture closed; processes none started
- `wps-open-presentation-selection-insert` run 3 (FAIL): failed checks: tool_not_called (1 call(s)) | error codes: DOCUMENT_HELD_OPEN | cleanup: fixture closed; processes none started
- `wps-open-presentation-selection-delete` run 1 (pass): cleanup: fixture closed; processes none started
- `wps-open-presentation-selection-delete` run 2 (pass): cleanup: fixture closed; processes none started
- `wps-open-presentation-selection-delete` run 3 (pass): cleanup: fixture closed; processes none started
- `wps-open-spreadsheet-selection-replace` skipped: select_text: script_failed [{'code': 'COM_OPERATION_FAILED', 'message': 'True\n{\n  "ok": true,\n  "status": "ok",\n  "address": "C2:C3",\n  "sheet": "Status",\n  "saved": true\n}'}]
- `wps-open-spreadsheet-selection-delete` skipped: select_text: script_failed [{'code': 'COM_OPERATION_FAILED', 'message': 'True\n{\n  "ok": true,\n  "status": "ok",\n  "address": "C3",\n  "sheet": "Status",\n  "saved": true\n}'}]
- `wps-open-save-as-untitled` run 1 (FAIL): failed checks: operation_recorded (no record); file_text (file missing) | error codes: DIRECTORY_NOT_FOUND, MCP_ADAPTER_CALL_REJECTED, OPERATION_NOT_FOUND, UNTITLED_DOCUMENT_NOT_FOUND | cleanup: untitled �����ĸ�1 not_found; fixture closed; processes none started
- `wps-open-save-as-untitled` run 2 (FAIL): failed checks: operation_recorded (no record); tool_called (0 matching call(s)); file_text (file missing) | cleanup: untitled �����ĸ�2 not_found; fixture closed; processes none started
- `wps-open-save-as-untitled` run 3 (FAIL): failed checks: operation_recorded (no record); file_text (file missing) | error codes: INVALID_ARGUMENT, UNTITLED_DOCUMENT_NOT_FOUND | cleanup: untitled �����ĸ�3 not_found; fixture closed; processes none started

### WPS processes after the run

- wpp.exe 17668 `deck.pptx - WPS ��ʾ` "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\wpp.exe" "C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261015T141839Z-564d103-eval\run-1\wps-open-presentation-selection-replace\deck.pptx"
- wps.exe 44888 `�����ĸ�3 * - WPS ����` "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\wps.exe" "C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261015T141839Z-564d103-eval\run-1\wps-open-save-document\report.docx"
