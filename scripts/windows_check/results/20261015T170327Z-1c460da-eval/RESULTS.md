# Windows agent evaluation

- Date: 2026-10-15 17:06 UTC
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
python scripts/windows_check/run_windows_check.py eval --only wps-open-spreadsheet-selection-replace --only wps-open-spreadsheet-selection-delete --repeat 3 --min-passes 2
```

Claude Code CLI 2.1.295 (Claude Code), model CLI default, launch mode `default`. **0/1 tasks passed**, 1 skipped. Each task passes with at least 2 of 3 runs. Task workspaces: `C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261015T170327Z-1c460da-eval`.

| Task | Passes | Turns | `wps-agent` calls | Tool errors | `off_path_calls` | `off_path_tools` |
| --- | --- | --- | --- | --- | --- | --- |
| `wps-open-spreadsheet-selection-replace` | 1/3 | 2.0 (6, 0, 0) | 5 | 0 | 1 | `spreadsheet_read` |
| `wps-open-spreadsheet-selection-delete` | skipped | | | | | |

### Runs

- `wps-open-spreadsheet-selection-replace` run 1 (pass): cleanup: fixture COM_OPERATION_FAILED (服务器出现意外情况。 (0x80010105 (RPC_E_SERVERFAULT))); processes stopped 48976
- `wps-open-spreadsheet-selection-replace` run 2 (FAIL): setup failed: WPS did not list status.xlsx as open within 45 s (launch mode default): WPS_INSTANCE_NOT_AUTOMATABLE: WPS Spreadsheets is running with a window, but it did not register for automation, so its open documents cannot be reached. This happens when WPS was started by opening a file directly, for example by double-clicking it. Save your work in WPS, close every WPS Spreadsheets window, then reopen the document with the /Automation option, for example: wps.exe /Automation "<path to the document>". Nothing was launched, closed or changed.
- `wps-open-spreadsheet-selection-replace` run 3 (FAIL): setup failed: WPS did not list status.xlsx as open within 45 s (launch mode default): WPS_INSTANCE_NOT_AUTOMATABLE: WPS Spreadsheets is running with a window, but it did not register for automation, so its open documents cannot be reached. This happens when WPS was started by opening a file directly, for example by double-clicking it. Save your work in WPS, close every WPS Spreadsheets window, then reopen the document with the /Automation option, for example: wps.exe /Automation "<path to the document>". Nothing was launched, closed or changed.
- `wps-open-spreadsheet-selection-delete` skipped: WPS did not list status.xlsx as open within 45 s (launch mode default): WPS_INSTANCE_NOT_AUTOMATABLE: WPS Spreadsheets is running with a window, but it did not register for automation, so its open documents cannot be reached. This happens when WPS was started by opening a file directly, for example by double-clicking it. Save your work in WPS, close every WPS Spreadsheets window, then reopen the document with the /Automation option, for example: wps.exe /Automation "<path to the document>". Nothing was launched, closed or changed.

### WPS processes after the run

- et.exe 27488 `status.xlsx - [ 工作区261016@010412 ] - WPS 表格` "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\et.exe"  recover1 -cpid=48976 /w
