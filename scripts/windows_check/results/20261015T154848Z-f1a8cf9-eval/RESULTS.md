# Windows agent evaluation

- Date: 2026-10-15 15:53 UTC
- Commit: `f1a8cf9` on `cursor/phase7-windows-564d103`
- Machine: Windows-10-10.0.19045-SP0; Python 3.12.15
- WPS: wps.exe 12,8,2,18913, et.exe 12,8,2,18913, wpp.exe 12,8,2,18913
- Written by `scripts/windows_check/run_windows_check.py`; nothing in this file was typed by hand.

## Prerequisites

| Check | Result | Detail |
| --- | --- | --- |
| commit | ok | f1a8cf9 on cursor/phase7-windows-564d103 |
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

Claude Code CLI 2.1.295 (Claude Code), model CLI default, launch mode `default`. **2/2 tasks passed**, 0 skipped. Each task passes with at least 2 of 3 runs. Task workspaces: `C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261015T154848Z-f1a8cf9-eval`.

| Task | Passes | Turns | `wps-agent` calls | Tool errors | `off_path_calls` | `off_path_tools` |
| --- | --- | --- | --- | --- | --- | --- |
| `wps-open-spreadsheet-selection-replace` | 2/3 | 4.0 (6, 6, 0) | 10 | 0 | 3 | `save_open_document`, `spreadsheet_read` |
| `wps-open-spreadsheet-selection-delete` | 2/3 | 5.7 (8, 9, 0) | 13 | 0 | 3 | `spreadsheet_read`, `spreadsheet_sheets` |

### Runs

- `wps-open-spreadsheet-selection-replace` run 1 (pass): cleanup: fixture COM_OPERATION_FAILED; processes stopped 26368
- `wps-open-spreadsheet-selection-replace` run 2 (pass): cleanup: fixture COM_OPERATION_FAILED; processes stopped 3768,47552
- `wps-open-spreadsheet-selection-replace` run 3 (FAIL): setup failed: WPS did not list status.xlsx as open within 45 s (launch mode default); is WPS the default app for .xlsx?
- `wps-open-spreadsheet-selection-delete` run 1 (pass): cleanup: fixture COM_OPERATION_FAILED; processes stopped 47964
- `wps-open-spreadsheet-selection-delete` run 2 (pass): cleanup: fixture COM_OPERATION_FAILED; processes stopped 3084,18544
- `wps-open-spreadsheet-selection-delete` run 3 (FAIL): setup failed: WPS did not list status.xlsx as open within 45 s (launch mode default); is WPS the default app for .xlsx?

### WPS processes after the run

- None.
