# Windows agent evaluation

- Date: 2026-10-17 04:22 UTC
- Commit: `ab92a42` on `main`
- Machine: Windows-10-10.0.19045-SP0; Python 3.12.15
- WPS: wps.exe 12,8,2,18913, et.exe 12,8,2,18913, wpp.exe 12,8,2,18913
- Written by `scripts/windows_check/run_windows_check.py`; nothing in this file was typed by hand.

## Prerequisites

| Check | Result | Detail |
| --- | --- | --- |
| commit | ok | ab92a42 on main |
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

Claude Code CLI 2.1.295 (Claude Code), model CLI default, launch mode `default`. **16/16 tasks passed**, 0 skipped. Each task passes with at least 2 of 3 runs. **0 wrong-tool calls** (file-based write tools called on a document open in WPS, counted for open-document tasks). **11 off-path calls**, 8 of them after the task's first write (calls to tools the task does not need). Task workspaces: `C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261016T221731Z-ab92a42-eval`.

| Task | Passes | Turns | `wps-agent` calls | Tool errors | `wrong_tool_calls` | `off_path_calls` | after the write | `off_path_tools` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `wps-open-document-export-text` | 3/3 | 4.0 (4, 4, 4) | 6 | 0 | 0 | 0 | 0 |  |
| `wps-open-writer-selection-replace` | 3/3 | 5.7 (5, 6, 6) | 14 | 0 | 0 | 0 | 0 |  |
| `wps-open-writer-selection-insert` | 3/3 | 7.7 (7, 7, 9) | 20 | 0 | 0 | 4 | 2 | `snapshot_document`, `validate_document` |
| `wps-open-presentation-selection-replace` | 3/3 | 5.0 (5, 5, 5) | 12 | 0 | 0 | 0 | 0 |  |
| `wps-open-save-document` | 3/3 | 4.7 (5, 5, 4) | 11 | 0 | 0 | 0 | 0 |  |
| `wps-open-writer-selection-delete` | 3/3 | 5.3 (5, 5, 6) | 13 | 0 | 0 | 1 | 1 | `snapshot_document` |
| `wps-open-presentation-selection-insert` | 3/3 | 6.3 (6, 7, 6) | 16 | 0 | 0 | 0 | 0 |  |
| `wps-open-presentation-selection-delete` | 3/3 | 5.0 (5, 4, 6) | 12 | 0 | 0 | 0 | 0 |  |
| `wps-open-spreadsheet-selection-replace` | 3/3 | 7.0 (6, 8, 7) | 18 | 0 | 0 | 4 | 3 | `spreadsheet_read` |
| `wps-open-spreadsheet-selection-delete` | 3/3 | 5.3 (4, 6, 6) | 13 | 0 | 0 | 1 | 1 | `spreadsheet_read` |
| `wps-open-save-as-untitled` | 3/3 | 4.3 (5, 4, 4) | 10 | 0 | 0 | 0 | 0 |  |
| `wps-open-zh-writer-selection-replace` | 3/3 | 5.3 (4, 6, 6) | 13 | 0 | 0 | 0 | 0 |  |
| `wps-open-zh-spreadsheet-sheet-cells` | 3/3 | 4.7 (4, 6, 4) | 11 | 0 | 0 | 1 | 1 | `spreadsheet_read` |
| `wps-open-zh-document-export-text` | 3/3 | 4.0 (4, 4, 4) | 6 | 0 | 0 | 0 | 0 |  |
| `wps-open-zh-save-as-untitled` | 3/3 | 4.7 (5, 5, 4) | 11 | 0 | 0 | 0 | 0 |  |
| `wps-open-zh-document-export-beyond-gbk` | 3/3 | 4.0 (4, 4, 4) | 6 | 0 | 0 | 0 | 0 |  |

### Runs

- `wps-open-document-export-text` run 1 (pass): cleanup: fixture closed; processes exited 52368 (main window closed)
- `wps-open-document-export-text` run 2 (pass): cleanup: fixture closed; processes exited 15300 (main window closed)
- `wps-open-document-export-text` run 3 (pass): cleanup: fixture closed; processes exited 53596 (main window closed)
- `wps-open-writer-selection-replace` run 1 (pass): cleanup: fixture closed; processes exited 33296 (main window closed)
- `wps-open-writer-selection-replace` run 2 (pass): cleanup: fixture closed; processes exited 54384 (main window closed)
- `wps-open-writer-selection-replace` run 3 (pass): cleanup: fixture closed; processes exited 40320 (main window closed)
- `wps-open-writer-selection-insert` run 1 (pass): cleanup: fixture closed; processes exited 55748 (main window closed)
- `wps-open-writer-selection-insert` run 2 (pass): cleanup: fixture closed; processes exited 53556 (main window closed)
- `wps-open-writer-selection-insert` run 3 (pass): cleanup: fixture closed; processes exited 19144 (main window closed)
- `wps-open-presentation-selection-replace` run 1 (pass): cleanup: fixture closed; processes exited 50272 (main window closed)
- `wps-open-presentation-selection-replace` run 2 (pass): cleanup: fixture closed; processes exited 17668 (main window closed)
- `wps-open-presentation-selection-replace` run 3 (pass): cleanup: fixture closed; processes exited 53200 (main window closed)
- `wps-open-save-document` run 1 (pass): cleanup: fixture closed; processes exited 55176 (main window closed)
- `wps-open-save-document` run 2 (pass): cleanup: fixture closed; processes exited 54592 (main window closed)
- `wps-open-save-document` run 3 (pass): cleanup: fixture closed; processes exited 51436 (main window closed)
- `wps-open-writer-selection-delete` run 1 (pass): cleanup: fixture closed; processes exited 33316 (main window closed)
- `wps-open-writer-selection-delete` run 2 (pass): cleanup: fixture closed; processes exited 50792 (main window closed)
- `wps-open-writer-selection-delete` run 3 (pass): cleanup: fixture closed; processes exited 11248 (main window closed)
- `wps-open-presentation-selection-insert` run 1 (pass): cleanup: fixture closed; processes exited 45828 (main window closed)
- `wps-open-presentation-selection-insert` run 2 (pass): cleanup: fixture closed; processes exited 45068 (main window closed)
- `wps-open-presentation-selection-insert` run 3 (pass): cleanup: fixture closed; processes exited 45692 (main window closed)
- `wps-open-presentation-selection-delete` run 1 (pass): cleanup: fixture closed; processes exited 38096 (main window closed)
- `wps-open-presentation-selection-delete` run 2 (pass): cleanup: fixture closed; processes exited 15420 (main window closed)
- `wps-open-presentation-selection-delete` run 3 (pass): cleanup: fixture closed; processes exited 42744 (main window closed)
- `wps-open-spreadsheet-selection-replace` run 1 (pass): cleanup: fixture closed; processes exited 26356 (main window closed)
- `wps-open-spreadsheet-selection-replace` run 2 (pass): cleanup: fixture closed; processes exited 51188 (main window closed)
- `wps-open-spreadsheet-selection-replace` run 3 (pass): cleanup: fixture closed; processes exited 54544 (main window closed)
- `wps-open-spreadsheet-selection-delete` run 1 (pass): cleanup: fixture closed; processes exited 45924 (main window closed)
- `wps-open-spreadsheet-selection-delete` run 2 (pass): cleanup: fixture closed; processes exited 3896 (main window closed)
- `wps-open-spreadsheet-selection-delete` run 3 (pass): cleanup: fixture closed; processes exited 43428 (main window closed)
- `wps-open-save-as-untitled` run 1 (pass): cleanup: untitled 文字文稿1 not_found; notes.docx closed; fixture closed; processes exited 39304 (main window closed)
- `wps-open-save-as-untitled` run 2 (pass): cleanup: untitled 文字文稿1 not_found; notes.docx closed; fixture closed; processes exited 34500 (main window closed)
- `wps-open-save-as-untitled` run 3 (pass): cleanup: untitled 文字文稿1 not_found; notes.docx closed; fixture closed; processes exited 20556 (main window closed)
- `wps-open-zh-writer-selection-replace` run 1 (pass): cleanup: fixture closed; processes exited 52348 (main window closed)
- `wps-open-zh-writer-selection-replace` run 2 (pass): cleanup: fixture closed; processes exited 14872 (main window closed)
- `wps-open-zh-writer-selection-replace` run 3 (pass): cleanup: fixture closed; processes exited 42348 (main window closed)
- `wps-open-zh-spreadsheet-sheet-cells` run 1 (pass): cleanup: fixture closed; processes exited 50720 (main window closed)
- `wps-open-zh-spreadsheet-sheet-cells` run 2 (pass): cleanup: fixture closed; processes exited 47052 (main window closed)
- `wps-open-zh-spreadsheet-sheet-cells` run 3 (pass): cleanup: fixture closed; processes exited 17512 (main window closed)
- `wps-open-zh-document-export-text` run 1 (pass): cleanup: fixture closed; processes exited 38976 (main window closed)
- `wps-open-zh-document-export-text` run 2 (pass): cleanup: fixture closed; processes exited 49916 (main window closed)
- `wps-open-zh-document-export-text` run 3 (pass): cleanup: fixture closed; processes exited 50640 (main window closed)
- `wps-open-zh-save-as-untitled` run 1 (pass): cleanup: untitled 文字文稿1 not_found; 会议纪要.docx closed; fixture closed; processes exited 51672 (main window closed)
- `wps-open-zh-save-as-untitled` run 2 (pass): cleanup: untitled 文字文稿1 not_found; 会议纪要.docx closed; fixture closed; processes exited 55772 (main window closed)
- `wps-open-zh-save-as-untitled` run 3 (pass): cleanup: untitled 文字文稿1 not_found; 会议纪要.docx closed; fixture closed; processes exited 7792 (main window closed)
- `wps-open-zh-document-export-beyond-gbk` run 1 (pass): cleanup: fixture closed; processes exited 41300 (main window closed)
- `wps-open-zh-document-export-beyond-gbk` run 2 (pass): cleanup: fixture closed; processes exited 52172 (main window closed)
- `wps-open-zh-document-export-beyond-gbk` run 3 (pass): cleanup: fixture closed; processes exited 41588 (main window closed)

### Documents WPS had open outside the task workspaces

Listed right after the fixture opened. WPS reopens the documents of its previous session when it starts; they are the machine user's, so they are recorded here and left open.

- None.

### WPS processes after the run

- None.
