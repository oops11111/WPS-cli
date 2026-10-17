# Windows agent evaluation

- Date: 2026-10-17 15:32 UTC
- Commit: `20c94d8` on `main`
- Machine: Windows-10-10.0.19045-SP0; Python 3.12.15
- WPS: wps.exe 12,8,2,18913, et.exe 12,8,2,18913, wpp.exe 12,8,2,18913
- Written by `scripts/windows_check/run_windows_check.py`; nothing in this file was typed by hand.

## Prerequisites

| Check | Result | Detail |
| --- | --- | --- |
| commit | ok | 20c94d8 on main |
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

Claude Code CLI 2.1.295 (Claude Code), model CLI default, launch mode `default`. **16/16 tasks passed**, 0 skipped. Each task passes with at least 2 of 3 runs. **0 wrong-tool calls** (file-based write tools called on a document open in WPS, counted for open-document tasks). **4 off-path calls**, 3 of them after the task's first write (calls to tools the task does not need). **0 writes whose verified_state.passed is not true** (listed under Runs). Task workspaces: `C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261017T062425Z-20c94d8-eval`.

| Task | Passes | Turns | `wps-agent` calls | Tool errors | `wrong_tool_calls` | `off_path_calls` | after the write | `off_path_tools` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `wps-open-document-export-text` | 3/3 | 3.7 (3, 4, 4) | 6 | 0 | 0 | 0 | 0 |  |
| `wps-open-writer-selection-replace` | 3/3 | 5.0 (5, 5, 5) | 12 | 0 | 0 | 1 | 1 | `validate_document` |
| `wps-open-writer-selection-insert` | 3/3 | 5.7 (5, 5, 7) | 14 | 0 | 0 | 1 | 0 | `snapshot_document` |
| `wps-open-presentation-selection-replace` | 3/3 | 5.3 (5, 6, 5) | 13 | 0 | 0 | 0 | 0 |  |
| `wps-open-save-document` | 3/3 | 4.0 (4, 4, 4) | 9 | 0 | 0 | 0 | 0 |  |
| `wps-open-writer-selection-delete` | 3/3 | 5.3 (6, 5, 5) | 13 | 0 | 0 | 0 | 0 |  |
| `wps-open-presentation-selection-insert` | 3/3 | 5.0 (5, 5, 5) | 12 | 0 | 0 | 0 | 0 |  |
| `wps-open-presentation-selection-delete` | 3/3 | 5.7 (6, 5, 6) | 14 | 0 | 0 | 0 | 0 |  |
| `wps-open-spreadsheet-selection-replace` | 3/3 | 5.7 (7, 6, 4) | 14 | 0 | 0 | 1 | 1 | `spreadsheet_read` |
| `wps-open-spreadsheet-selection-delete` | 3/3 | 4.7 (5, 4, 5) | 11 | 0 | 0 | 0 | 0 |  |
| `wps-open-save-as-untitled` | 3/3 | 8.3 (10, 10, 5) | 15 | 2 | 0 | 1 | 1 | `operation` |
| `wps-open-zh-writer-selection-replace` | 3/3 | 5.3 (6, 4, 6) | 13 | 0 | 0 | 0 | 0 |  |
| `wps-open-zh-spreadsheet-sheet-cells` | 3/3 | 5.0 (5, 4, 6) | 12 | 0 | 0 | 0 | 0 |  |
| `wps-open-zh-document-export-text` | 3/3 | 4.0 (5, 4, 3) | 6 | 0 | 0 | 0 | 0 |  |
| `wps-open-zh-save-as-untitled` | 3/3 | 7.0 (4, 6, 11) | 12 | 1 | 0 | 0 | 0 |  |
| `wps-open-zh-document-export-beyond-gbk` | 3/3 | 6.3 (7, 8, 4) | 7 | 1 | 0 | 0 | 0 |  |

### Runs

- `wps-open-document-export-text` run 1 (pass): cleanup: fixture closed; processes exited 11516 (main window closed)
- `wps-open-document-export-text` run 2 (pass): cleanup: fixture closed; processes exited 50964 (main window closed)
- `wps-open-document-export-text` run 3 (pass): cleanup: fixture closed; processes exited 9644 (main window closed)
- `wps-open-writer-selection-replace` run 1 (pass): cleanup: fixture closed; processes exited 50964 (main window closed)
- `wps-open-writer-selection-replace` run 2 (pass): cleanup: fixture closed; processes exited 28856 (main window closed)
- `wps-open-writer-selection-replace` run 3 (pass): cleanup: fixture closed; processes exited 54628 (main window closed)
- `wps-open-writer-selection-insert` run 1 (pass): cleanup: fixture closed; processes exited 49868 (main window closed)
- `wps-open-writer-selection-insert` run 2 (pass): cleanup: fixture closed; processes exited 22416 (main window closed)
- `wps-open-writer-selection-insert` run 3 (pass): cleanup: fixture closed; processes exited 47732 (main window closed)
- `wps-open-presentation-selection-replace` run 1 (pass): cleanup: fixture closed; processes exited 10856 (main window closed)
- `wps-open-presentation-selection-replace` run 2 (pass): cleanup: fixture closed; processes exited 28856 (main window closed)
- `wps-open-presentation-selection-replace` run 3 (pass): cleanup: fixture closed; processes exited 16112 (main window closed)
- `wps-open-save-document` run 1 (pass): cleanup: fixture closed; processes exited 44500 (main window closed)
- `wps-open-save-document` run 2 (pass): cleanup: fixture closed; processes exited 53232 (main window closed)
- `wps-open-save-document` run 3 (pass): cleanup: fixture closed; processes exited 20400 (main window closed)
- `wps-open-writer-selection-delete` run 1 (pass): cleanup: fixture closed; processes exited 55892 (main window closed)
- `wps-open-writer-selection-delete` run 2 (pass): cleanup: fixture closed; processes exited 51032 (main window closed)
- `wps-open-writer-selection-delete` run 3 (pass): cleanup: fixture closed; processes exited 54408 (main window closed)
- `wps-open-presentation-selection-insert` run 1 (pass): cleanup: fixture closed; processes exited 33668 (main window closed)
- `wps-open-presentation-selection-insert` run 2 (pass): cleanup: fixture closed; processes exited 46816 (main window closed)
- `wps-open-presentation-selection-insert` run 3 (pass): cleanup: fixture closed; processes exited 44428 (main window closed)
- `wps-open-presentation-selection-delete` run 1 (pass): cleanup: fixture closed; processes exited 21596 (main window closed)
- `wps-open-presentation-selection-delete` run 2 (pass): cleanup: fixture closed; processes exited 52712 (main window closed)
- `wps-open-presentation-selection-delete` run 3 (pass): cleanup: fixture closed; processes exited 9772 (main window closed)
- `wps-open-spreadsheet-selection-replace` run 1 (pass): cleanup: fixture closed; processes exited 47732 (main window closed)
- `wps-open-spreadsheet-selection-replace` run 2 (pass): cleanup: fixture closed; processes exited 33548 (main window closed)
- `wps-open-spreadsheet-selection-replace` run 3 (pass): cleanup: fixture closed; processes exited 54816 (main window closed)
- `wps-open-spreadsheet-selection-delete` run 1 (pass): cleanup: fixture closed; processes exited 13136 (main window closed)
- `wps-open-spreadsheet-selection-delete` run 2 (pass): cleanup: fixture closed; processes exited 26332 (main window closed)
- `wps-open-spreadsheet-selection-delete` run 3 (pass): cleanup: fixture closed; processes exited 24456 (main window closed)
- `wps-open-save-as-untitled` run 1 (pass): error codes: OUTPUT_DIRECTORY_MISSING | cleanup: untitled 文字文稿1 not_found; notes.docx closed; fixture closed; processes exited 50340 (main window closed)
- `wps-open-save-as-untitled` run 2 (pass): error codes: OUTPUT_DIRECTORY_MISSING | cleanup: untitled 文字文稿1 not_found; notes.docx closed; fixture closed; processes exited 58320 (main window closed)
- `wps-open-save-as-untitled` run 3 (pass): cleanup: untitled 文字文稿1 not_found; notes.docx closed; fixture closed; processes exited 58524 (main window closed)
- `wps-open-zh-writer-selection-replace` run 1 (pass): cleanup: fixture closed; processes exited 30672 (main window closed)
- `wps-open-zh-writer-selection-replace` run 2 (pass): cleanup: fixture closed; processes exited 57348 (main window closed)
- `wps-open-zh-writer-selection-replace` run 3 (pass): cleanup: fixture closed; processes exited 25916 (main window closed)
- `wps-open-zh-spreadsheet-sheet-cells` run 1 (pass): cleanup: fixture closed; processes exited 58356 (main window closed)
- `wps-open-zh-spreadsheet-sheet-cells` run 2 (pass): cleanup: fixture closed; processes exited 55332 (main window closed)
- `wps-open-zh-spreadsheet-sheet-cells` run 3 (pass): cleanup: fixture closed; processes exited 38988 (main window closed)
- `wps-open-zh-document-export-text` run 1 (pass): cleanup: fixture closed; processes exited 58136 (main window closed)
- `wps-open-zh-document-export-text` run 2 (pass): cleanup: fixture closed; processes exited 56792 (main window closed)
- `wps-open-zh-document-export-text` run 3 (pass): cleanup: fixture closed; processes exited 58936 (main window closed)
- `wps-open-zh-save-as-untitled` run 1 (pass): cleanup: untitled 文字文稿1 not_found; 会议纪要.docx closed; fixture closed; processes exited 58648 (main window closed)
- `wps-open-zh-save-as-untitled` run 2 (pass): error codes: OUTPUT_DIRECTORY_MISSING | cleanup: untitled 文字文稿1 not_found; 会议纪要.docx closed; fixture closed; processes exited 59364 (main window closed)
- `wps-open-zh-save-as-untitled` run 3 (pass): cleanup: untitled 文字文稿1 not_found; 会议纪要.docx closed; fixture closed; processes exited 10432 (main window closed)
- `wps-open-zh-document-export-beyond-gbk` run 1 (pass): error codes: INVALID_ARGUMENT | cleanup: fixture closed; processes exited 14852 (main window closed)
- `wps-open-zh-document-export-beyond-gbk` run 2 (pass): cleanup: fixture closed; processes exited 36608 (main window closed)
- `wps-open-zh-document-export-beyond-gbk` run 3 (pass): cleanup: fixture closed; processes exited 58364 (main window closed)

### Documents WPS had open outside the task workspaces

Listed right after the fixture opened. WPS reopens the documents of its previous session when it starts; they are the machine user's, so they are recorded here and left open.

- None.

### WPS processes after the run

- None.
