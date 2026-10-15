# Windows agent evaluation

- Date: 2026-10-15 22:30 UTC
- Commit: `1b6ad48` on `main`
- Machine: Windows-10-10.0.19045-SP0; Python 3.12.15
- WPS: wps.exe 12,8,2,18913, et.exe 12,8,2,18913, wpp.exe 12,8,2,18913
- Written by `scripts/windows_check/run_windows_check.py`; nothing in this file was typed by hand.

## Prerequisites

| Check | Result | Detail |
| --- | --- | --- |
| commit | ok | 1b6ad48 on main |
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

Claude Code CLI 2.1.295 (Claude Code), model CLI default, launch mode `default`. **9/10 tasks passed**, 1 skipped. Each task passes with at least 2 of 3 runs. Task workspaces: `C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261015T221131Z-1b6ad48-eval`.

| Task | Passes | Turns | `wps-agent` calls | Tool errors | `off_path_calls` | `off_path_tools` |
| --- | --- | --- | --- | --- | --- | --- |
| `wps-open-document-export-text` | 3/3 | 4.3 (5, 4, 4) | 7 | 0 | 0 |  |
| `wps-open-writer-selection-replace` | 3/3 | 6.7 (4, 8, 8) | 17 | 0 | 3 | `operation`, `snapshot_document` |
| `wps-open-writer-selection-insert` | 3/3 | 10.3 (16, 9, 6) | 24 | 1 | 8 | `operation`, `snapshot_document`, `validate_document`, `writer_structure` |
| `wps-open-presentation-selection-replace` | 3/3 | 5.7 (6, 5, 6) | 13 | 0 | 0 |  |
| `wps-open-save-document` | 3/3 | 5.7 (5, 6, 6) | 14 | 0 | 2 | `operation`, `snapshot_document` |
| `wps-open-writer-selection-delete` | 3/3 | 5.7 (5, 6, 6) | 14 | 0 | 3 | `operation`, `snapshot_document` |
| `wps-open-presentation-selection-insert` | 3/3 | 7.7 (6, 7, 10) | 19 | 3 | 2 | `export_open_document_text`, `mcp_call` |
| `wps-open-presentation-selection-delete` | 3/3 | 7.0 (6, 8, 7) | 17 | 0 | 0 |  |
| `wps-open-spreadsheet-selection-replace` | 1/3 | 2.0 (6, 0, 0) | 5 | 0 | 1 | `spreadsheet_read` |
| `wps-open-spreadsheet-selection-delete` | skipped | | | | | |
| `wps-open-save-as-untitled` | 3/3 | 6.3 (4, 8, 7) | 11 | 0 | 0 |  |

### Runs

- `wps-open-document-export-text` run 1 (pass): cleanup: fixture closed; processes left running: WPS still lists notes-default.docx
- `wps-open-document-export-text` run 2 (pass): cleanup: fixture closed; processes none started
- `wps-open-document-export-text` run 3 (pass): cleanup: fixture closed; processes none started
- `wps-open-writer-selection-replace` run 1 (pass): cleanup: fixture closed; processes none started
- `wps-open-writer-selection-replace` run 2 (pass): cleanup: fixture closed; processes none started
- `wps-open-writer-selection-replace` run 3 (pass): cleanup: fixture closed; processes none started
- `wps-open-writer-selection-insert` run 1 (pass): cleanup: fixture closed; processes none started
- `wps-open-writer-selection-insert` run 2 (pass): error codes: INVALID_BOOKMARK_TEXT_QUERY | cleanup: fixture closed; processes none started
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
- `wps-open-presentation-selection-insert` run 3 (pass): error codes: IDEMPOTENCY_CONFLICT, INVALID_ARGUMENT, MCP_ADAPTER_CALL_REJECTED | cleanup: fixture closed; processes none started
- `wps-open-presentation-selection-delete` run 1 (pass): cleanup: fixture closed; processes none started
- `wps-open-presentation-selection-delete` run 2 (pass): cleanup: fixture closed; processes none started
- `wps-open-presentation-selection-delete` run 3 (pass): cleanup: fixture closed; processes none started
- `wps-open-spreadsheet-selection-replace` run 1 (pass): cleanup: fixture COM_OPERATION_FAILED (0x800A01A8); processes stopped 49320
- `wps-open-spreadsheet-selection-replace` run 2 (FAIL): setup failed: WPS did not list status.xlsx as open within 45 s (launch mode default): WPS_INSTANCE_NOT_AUTOMATABLE: WPS Spreadsheets is running with a window, but it did not register for automation, so its open documents cannot be reached. This happens when WPS was started by opening a file directly, for example by double-clicking it. Save your work in WPS, close every WPS Spreadsheets window, then reopen the document with the /Automation option, for example: wps.exe /Automation "<path to the document>". Nothing was launched, closed or changed. [WPS processes: 18156,27324,44920; started for this run: none; running before it: 18156,27324,44920]
- `wps-open-spreadsheet-selection-replace` run 3 (FAIL): setup failed: WPS did not list status.xlsx as open within 45 s (launch mode default): WPS_INSTANCE_NOT_AUTOMATABLE: WPS Spreadsheets is running with a window, but it did not register for automation, so its open documents cannot be reached. This happens when WPS was started by opening a file directly, for example by double-clicking it. Save your work in WPS, close every WPS Spreadsheets window, then reopen the document with the /Automation option, for example: wps.exe /Automation "<path to the document>". Nothing was launched, closed or changed. [WPS processes: 18156,27324,44920; started for this run: none; running before it: 18156,27324,44920]
- `wps-open-spreadsheet-selection-delete` skipped: WPS did not list status.xlsx as open within 45 s (launch mode default): WPS_INSTANCE_NOT_AUTOMATABLE: WPS Spreadsheets is running with a window, but it did not register for automation, so its open documents cannot be reached. This happens when WPS was started by opening a file directly, for example by double-clicking it. Save your work in WPS, close every WPS Spreadsheets window, then reopen the document with the /Automation option, for example: wps.exe /Automation "<path to the document>". Nothing was launched, closed or changed. [WPS processes: 18156,27324,44920; started for this run: none; running before it: 18156,27324,44920]
- `wps-open-save-as-untitled` run 1 (pass): cleanup: untitled 文字文稿4 not_found; notes.docx closed; fixture closed; processes none started
- `wps-open-save-as-untitled` run 2 (pass): cleanup: untitled 文字文稿5 not_found; notes.docx closed; fixture closed; processes none started
- `wps-open-save-as-untitled` run 3 (pass): cleanup: untitled 文字文稿6 not_found; notes.docx closed; fixture closed; processes none started

### WPS processes after the run

- wps.exe 18156 `notes-default.docx - WPS 文字` "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\wps.exe" "C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261015T221131Z-1b6ad48-eval\run-1\wps-open-document-export-text\report.docx"
- wpp.exe 44920 `deck.pptx - WPS 演示` "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\wpp.exe" "C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261015T221131Z-1b6ad48-eval\run-1\wps-open-presentation-selection-replace\deck.pptx"
- et.exe 27324 `status.xlsx - [ 工作区261016@062549 ] - WPS 表格` "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\et.exe"  recover1 -cpid=49320 /w
