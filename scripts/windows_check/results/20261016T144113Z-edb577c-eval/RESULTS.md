# Windows agent evaluation

- Date: 2026-10-16 15:25 UTC
- Commit: `edb577c` on `main`
- Machine: Windows-10-10.0.19045-SP0; Python 3.12.15
- WPS: wps.exe 12,8,2,18913, et.exe 12,8,2,18913, wpp.exe 12,8,2,18913
- Written by `scripts/windows_check/run_windows_check.py`; nothing in this file was typed by hand.

## Prerequisites

| Check | Result | Detail |
| --- | --- | --- |
| commit | ok | edb577c on main |
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
python scripts/windows_check/run_windows_check.py eval --prefix wps-open- --repeat 3 --min-passes 2
```

Claude Code CLI 2.1.295 (Claude Code), model CLI default, launch mode `default`. **16/16 tasks passed**, 0 skipped. Each task passes with at least 2 of 3 runs. **0 wrong-tool calls** (file-based write tools called on a document open in WPS, counted for open-document tasks). Task workspaces: `C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261016T144113Z-edb577c-eval`.

| Task | Passes | Turns | `wps-agent` calls | Tool errors | `wrong_tool_calls` | `off_path_calls` | `off_path_tools` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `wps-open-document-export-text` | 3/3 | 4.0 (4, 4, 4) | 6 | 0 | 0 | 0 |  |
| `wps-open-writer-selection-replace` | 3/3 | 6.3 (7, 7, 5) | 16 | 0 | 0 | 3 | `scan_dir`, `snapshot_document`, `validate_document` |
| `wps-open-writer-selection-insert` | 3/3 | 9.0 (11, 8, 8) | 24 | 0 | 0 | 7 | `operation`, `snapshot_document`, `validate_document` |
| `wps-open-presentation-selection-replace` | 3/3 | 7.0 (7, 5, 9) | 18 | 0 | 0 | 4 | `operation`, `snapshot_document` |
| `wps-open-save-document` | 3/3 | 5.0 (7, 3, 5) | 10 | 0 | 0 | 1 | `operation` |
| `wps-open-writer-selection-delete` | 3/3 | 7.7 (7, 7, 9) | 19 | 2 | 0 | 4 | `export_open_document_text`, `snapshot_document`, `validate_document` |
| `wps-open-presentation-selection-insert` | 3/3 | 7.7 (7, 8, 8) | 20 | 0 | 0 | 1 | `snapshot_document` |
| `wps-open-presentation-selection-delete` | 3/3 | 5.0 (5, 5, 5) | 12 | 0 | 0 | 0 |  |
| `wps-open-spreadsheet-selection-replace` | 3/3 | 8.0 (9, 9, 6) | 20 | 0 | 0 | 6 | `spreadsheet_read`, `spreadsheet_sheets`, `validate_document` |
| `wps-open-spreadsheet-selection-delete` | 3/3 | 11.3 (10, 13, 11) | 29 | 1 | 0 | 11 | `mutation_request_inspect`, `spreadsheet_inspect`, `spreadsheet_read`, `spreadsheet_sheets` |
| `wps-open-save-as-untitled` | 3/3 | 6.0 (6, 6, 6) | 12 | 0 | 0 | 0 |  |
| `wps-open-zh-writer-selection-replace` | 3/3 | 7.0 (11, 5, 5) | 16 | 0 | 0 | 4 | `list_backups`, `snapshot_document`, `validate_document` |
| `wps-open-zh-spreadsheet-sheet-cells` | 3/3 | 8.3 (5, 10, 10) | 22 | 0 | 0 | 7 | `spreadsheet_read`, `spreadsheet_sheets` |
| `wps-open-zh-document-export-text` | 3/3 | 4.7 (5, 4, 5) | 6 | 0 | 0 | 0 |  |
| `wps-open-zh-save-as-untitled` | 3/3 | 6.0 (6, 6, 6) | 12 | 0 | 0 | 1 | `snapshot_document` |
| `wps-open-zh-document-export-beyond-gbk` | 3/3 | 6.0 (6, 6, 6) | 8 | 0 | 0 | 1 | `snapshot_document` |

### Runs

- `wps-open-document-export-text` run 1 (pass): cleanup: fixture closed; processes exited 23864 (main window closed)
- `wps-open-document-export-text` run 2 (pass): cleanup: fixture closed; processes exited 46340 (main window closed)
- `wps-open-document-export-text` run 3 (pass): cleanup: fixture closed; processes exited 53184 (main window closed)
- `wps-open-writer-selection-replace` run 1 (pass): cleanup: fixture closed; processes exited 51008 (main window closed)
- `wps-open-writer-selection-replace` run 2 (pass): cleanup: fixture closed; processes exited 55424 (main window closed)
- `wps-open-writer-selection-replace` run 3 (pass): cleanup: fixture closed; processes exited 55560 (main window closed)
- `wps-open-writer-selection-insert` run 1 (pass): cleanup: fixture closed; processes exited 54020 (main window closed)
- `wps-open-writer-selection-insert` run 2 (pass): cleanup: fixture closed; processes exited 51728 (main window closed)
- `wps-open-writer-selection-insert` run 3 (pass): cleanup: fixture closed; processes exited 56188 (main window closed)
- `wps-open-presentation-selection-replace` run 1 (pass): cleanup: fixture closed; processes exited 55584 (main window closed)
- `wps-open-presentation-selection-replace` run 2 (pass): cleanup: fixture closed; processes exited 54880 (main window closed)
- `wps-open-presentation-selection-replace` run 3 (pass): cleanup: fixture closed; processes exited 49716 (main window closed)
- `wps-open-save-document` run 1 (pass): cleanup: fixture closed; processes exited 30940 (main window closed)
- `wps-open-save-document` run 2 (pass): cleanup: fixture closed; processes exited 47356 (main window closed)
- `wps-open-save-document` run 3 (pass): cleanup: fixture closed; processes exited 38672 (main window closed)
- `wps-open-writer-selection-delete` run 1 (pass): cleanup: fixture closed; processes exited 43780 (main window closed)
- `wps-open-writer-selection-delete` run 2 (pass): cleanup: fixture closed; processes exited 9428 (main window closed)
- `wps-open-writer-selection-delete` run 3 (pass): error codes: INVALID_ARGUMENT, VALIDATION_FAILED | cleanup: fixture closed; processes exited 43000 (main window closed)
- `wps-open-presentation-selection-insert` run 1 (pass): cleanup: fixture closed; processes exited 51968 (main window closed)
- `wps-open-presentation-selection-insert` run 2 (pass): cleanup: fixture closed; processes exited 54484 (main window closed)
- `wps-open-presentation-selection-insert` run 3 (pass): cleanup: fixture closed; processes exited 20964 (main window closed)
- `wps-open-presentation-selection-delete` run 1 (pass): cleanup: fixture closed; processes exited 50528 (main window closed)
- `wps-open-presentation-selection-delete` run 2 (pass): cleanup: fixture closed; processes exited 14684 (main window closed)
- `wps-open-presentation-selection-delete` run 3 (pass): cleanup: fixture closed; processes exited 56048 (main window closed)
- `wps-open-spreadsheet-selection-replace` run 1 (pass): cleanup: fixture closed; processes exited 43440 (main window closed)
- `wps-open-spreadsheet-selection-replace` run 2 (pass): cleanup: fixture closed; processes exited 33668 (main window closed)
- `wps-open-spreadsheet-selection-replace` run 3 (pass): cleanup: fixture closed; processes exited 46924 (main window closed)
- `wps-open-spreadsheet-selection-delete` run 1 (pass): cleanup: fixture closed; processes exited 46816 (main window closed)
- `wps-open-spreadsheet-selection-delete` run 2 (pass): error codes: DOCUMENT_HELD_OPEN | cleanup: fixture closed; processes exited 13988 (main window closed)
- `wps-open-spreadsheet-selection-delete` run 3 (pass): cleanup: fixture closed; processes exited 10132 (main window closed)
- `wps-open-save-as-untitled` run 1 (pass): cleanup: untitled 文字文稿1 not_found; notes.docx closed; fixture closed; processes exited 18040 (main window closed)
- `wps-open-save-as-untitled` run 2 (pass): cleanup: untitled 文字文稿1 not_found; notes.docx closed; fixture closed; processes exited 55980 (main window closed)
- `wps-open-save-as-untitled` run 3 (pass): cleanup: untitled 文字文稿1 not_found; notes.docx closed; fixture closed; processes exited 54908 (main window closed)
- `wps-open-zh-writer-selection-replace` run 1 (pass): cleanup: fixture closed; processes exited 55580 (main window closed)
- `wps-open-zh-writer-selection-replace` run 2 (pass): cleanup: fixture closed; processes exited 48704 (main window closed)
- `wps-open-zh-writer-selection-replace` run 3 (pass): cleanup: fixture closed; processes exited 53968 (main window closed)
- `wps-open-zh-spreadsheet-sheet-cells` run 1 (pass): cleanup: fixture closed; processes exited 11196 (main window closed)
- `wps-open-zh-spreadsheet-sheet-cells` run 2 (pass): cleanup: fixture closed; processes exited 43004 (main window closed)
- `wps-open-zh-spreadsheet-sheet-cells` run 3 (pass): cleanup: fixture closed; processes exited 7036 (main window closed)
- `wps-open-zh-document-export-text` run 1 (pass): cleanup: fixture closed; processes exited 17668 (main window closed)
- `wps-open-zh-document-export-text` run 2 (pass): cleanup: fixture closed; processes exited 54484 (main window closed)
- `wps-open-zh-document-export-text` run 3 (pass): cleanup: fixture closed; processes exited 19752 (main window closed)
- `wps-open-zh-save-as-untitled` run 1 (pass): cleanup: untitled 文字文稿1 not_found; 会议纪要.docx closed; fixture closed; processes exited 1336 (main window closed)
- `wps-open-zh-save-as-untitled` run 2 (pass): cleanup: untitled 文字文稿1 not_found; 会议纪要.docx closed; fixture closed; processes exited 12300 (main window closed)
- `wps-open-zh-save-as-untitled` run 3 (pass): cleanup: untitled 文字文稿1 not_found; 会议纪要.docx closed; fixture closed; processes exited 56048 (main window closed)
- `wps-open-zh-document-export-beyond-gbk` run 1 (pass): cleanup: fixture closed; processes exited 10008 (main window closed)
- `wps-open-zh-document-export-beyond-gbk` run 2 (pass): cleanup: fixture closed; processes exited 14876 (main window closed)
- `wps-open-zh-document-export-beyond-gbk` run 3 (pass): cleanup: fixture closed; processes exited 55796 (main window closed)

### Documents WPS had open outside the task workspaces

Listed right after the fixture opened. WPS reopens the documents of its previous session when it starts; they are the machine user's, so they are recorded here and left open.

- None.

### WPS processes after the run

- None.
