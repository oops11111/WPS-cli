# Windows agent evaluation

- Date: 2026-10-16 11:32 UTC
- Commit: `1c44940` on `main`
- Machine: Windows-10-10.0.19045-SP0; Python 3.12.15
- WPS: wps.exe 12,8,2,18913, et.exe 12,8,2,18913, wpp.exe 12,8,2,18913
- Written by `scripts/windows_check/run_windows_check.py`; nothing in this file was typed by hand.

## Prerequisites

| Check | Result | Detail |
| --- | --- | --- |
| commit | ok | 1c44940 on main |
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
python scripts/windows_check/run_windows_check.py eval --prefix wps-open-zh- --repeat 3 --min-passes 2
```

Claude Code CLI 2.1.295 (Claude Code), model CLI default, launch mode `default`. **4/4 tasks passed**, 0 skipped. Each task passes with at least 2 of 3 runs. Task workspaces: `C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261016T112127Z-1c44940-eval`.

| Task | Passes | Turns | `wps-agent` calls | Tool errors | `off_path_calls` | `off_path_tools` |
| --- | --- | --- | --- | --- | --- | --- |
| `wps-open-zh-writer-selection-replace` | 3/3 | 7.7 (8, 8, 7) | 19 | 0 | 4 | `snapshot_document`, `validate_document` |
| `wps-open-zh-spreadsheet-sheet-cells` | 3/3 | 9.3 (8, 12, 8) | 20 | 2 | 5 | `save_open_document`, `spreadsheet_inspect`, `spreadsheet_read`, `spreadsheet_sheets` |
| `wps-open-zh-document-export-text` | 3/3 | 10.3 (10, 12, 9) | 12 | 0 | 3 | `snapshot_document`, `validate_document` |
| `wps-open-zh-save-as-untitled` | 3/3 | 7.3 (7, 9, 6) | 15 | 0 | 3 | `operations`, `snapshot_document` |

### Runs

- `wps-open-zh-writer-selection-replace` run 1 (pass): cleanup: fixture closed; processes stopped 42328
- `wps-open-zh-writer-selection-replace` run 2 (pass): cleanup: fixture closed; processes stopped 52616
- `wps-open-zh-writer-selection-replace` run 3 (pass): cleanup: fixture closed; processes stopped 55332
- `wps-open-zh-spreadsheet-sheet-cells` run 1 (pass): error codes: DOCUMENT_NOT_FOUND | cleanup: fixture closed; processes stopped 53684
- `wps-open-zh-spreadsheet-sheet-cells` run 2 (pass): error codes: DOCUMENT_HELD_OPEN | cleanup: fixture closed; processes stopped 34824
- `wps-open-zh-spreadsheet-sheet-cells` run 3 (pass): cleanup: fixture closed; processes stopped 56060
- `wps-open-zh-document-export-text` run 1 (pass): cleanup: fixture closed; processes stopped 55340
- `wps-open-zh-document-export-text` run 2 (pass): cleanup: fixture closed; processes stopped 13596
- `wps-open-zh-document-export-text` run 3 (pass): cleanup: fixture closed; processes stopped 28028
- `wps-open-zh-save-as-untitled` run 1 (pass): cleanup: untitled 文字文稿1 not_found; 会议纪要.docx closed; fixture closed; processes stopped 35148
- `wps-open-zh-save-as-untitled` run 2 (pass): cleanup: untitled 文字文稿1 not_found; 会议纪要.docx closed; fixture closed; processes stopped 53832
- `wps-open-zh-save-as-untitled` run 3 (pass): cleanup: untitled 文字文稿1 not_found; 会议纪要.docx closed; fixture closed; processes stopped 6548

### Documents WPS had open outside the task workspaces

Listed right after the fixture opened. WPS reopens the documents of its previous session when it starts; they are the machine user's, so they are recorded here and left open.

- None.

### WPS processes after the run

- None.
