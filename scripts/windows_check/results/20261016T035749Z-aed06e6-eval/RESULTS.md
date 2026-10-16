# Windows agent evaluation

- Date: 2026-10-16 05:16 UTC
- Commit: `aed06e6` on `main`
- Machine: Windows-10-10.0.19045-SP0; Python 3.12.15
- WPS: wps.exe 12,8,2,18913, et.exe 12,8,2,18913, wpp.exe 12,8,2,18913
- Written by `scripts/windows_check/run_windows_check.py`; nothing in this file was typed by hand.

## Prerequisites

| Check | Result | Detail |
| --- | --- | --- |
| commit | ok | aed06e6 on main |
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

Claude Code CLI 2.1.295 (Claude Code), model CLI default, launch mode `default`. **14/15 tasks passed**, 0 skipped. Each task passes with at least 2 of 3 runs. Task workspaces: `C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261016T035749Z-aed06e6-eval`.

| Task | Passes | Turns | `wps-agent` calls | Tool errors | `off_path_calls` | `off_path_tools` |
| --- | --- | --- | --- | --- | --- | --- |
| `wps-open-document-export-text` | 3/3 | 4.0 (4, 4, 4) | 6 | 0 | 0 |  |
| `wps-open-writer-selection-replace` | 3/3 | 6.3 (6, 6, 7) | 16 | 0 | 1 | `operation` |
| `wps-open-writer-selection-insert` | 3/3 | 9.0 (9, 11, 7) | 23 | 0 | 6 | `snapshot_document`, `validate_document` |
| `wps-open-presentation-selection-replace` | 3/3 | 4.7 (5, 4, 5) | 11 | 0 | 0 |  |
| `wps-open-save-document` | 3/3 | 4.7 (4, 5, 5) | 11 | 0 | 0 |  |
| `wps-open-writer-selection-delete` | 3/3 | 6.7 (7, 7, 6) | 17 | 1 | 2 | `validate_document`, `writer_structure` |
| `wps-open-presentation-selection-insert` | 2/3 | 6.7 (7, 7, 6) | 17 | 1 | 2 | `presentation_replace`, `snapshot_document` |
| `wps-open-presentation-selection-delete` | 2/3 | 7.3 (6, 7, 9) | 18 | 2 | 3 | `operation`, `presentation_replace` |
| `wps-open-spreadsheet-selection-replace` | 3/3 | 8.3 (11, 6, 8) | 19 | 0 | 5 | `operation`, `spreadsheet_read`, `spreadsheet_sheets` |
| `wps-open-spreadsheet-selection-delete` | 3/3 | 9.7 (13, 9, 7) | 25 | 0 | 7 | `spreadsheet_read`, `spreadsheet_sheets` |
| `wps-open-save-as-untitled` | 3/3 | 5.7 (6, 5, 6) | 13 | 0 | 0 |  |
| `wps-open-zh-writer-selection-replace` | 3/3 | 8.7 (15, 5, 6) | 17 | 0 | 2 | `snapshot_document` |
| `wps-open-zh-spreadsheet-sheet-cells` | 3/3 | 9.7 (7, 16, 6) | 20 | 0 | 9 | `spreadsheet_read`, `spreadsheet_sheets`, `validate_document` |
| `wps-open-zh-document-export-text` | 0/3 | 16.0 (16, 16, 16) | 23 | 6 | 13 | `export_open_document`, `mcp_tool_schema`, `mcp_tools`, `operations`, `snapshot_document`, `task_recovery_playbooks`, `writer_selection_read` |
| `wps-open-zh-save-as-untitled` | 3/3 | 6.3 (6, 5, 8) | 13 | 0 | 2 | `operations`, `snapshot_document` |

### Runs

- `wps-open-document-export-text` run 1 (pass): cleanup: fixture closed; processes stopped 54220
- `wps-open-document-export-text` run 2 (pass): cleanup: fixture closed; processes stopped 52440
- `wps-open-document-export-text` run 3 (pass): cleanup: fixture closed; processes stopped 42372
- `wps-open-writer-selection-replace` run 1 (pass): cleanup: fixture closed; processes stopped 23608
- `wps-open-writer-selection-replace` run 2 (pass): cleanup: fixture closed; processes stopped 19924
- `wps-open-writer-selection-replace` run 3 (pass): cleanup: fixture closed; processes stopped 19592
- `wps-open-writer-selection-insert` run 1 (pass): cleanup: fixture closed; processes stopped 5248
- `wps-open-writer-selection-insert` run 2 (pass): cleanup: fixture closed; processes stopped 34804
- `wps-open-writer-selection-insert` run 3 (pass): cleanup: fixture closed; processes stopped 46236
- `wps-open-presentation-selection-replace` run 1 (pass): cleanup: fixture closed; processes left running: WPS still lists deck.pptx
- `wps-open-presentation-selection-replace` run 2 (pass): cleanup: fixture closed; processes none started | WPS also had open: `C:\Users\admin\AppData\Local\Temp\wps-p6\eval-open-174f04e\run-20261015T022144989017Z\work\run-1\wps-open-presentation-selection-replace\deck.pptx` (presentation)
- `wps-open-presentation-selection-replace` run 3 (pass): cleanup: fixture closed; processes none started | WPS also had open: `C:\Users\admin\AppData\Local\Temp\wps-p6\eval-open-174f04e\run-20261015T022144989017Z\work\run-1\wps-open-presentation-selection-replace\deck.pptx` (presentation)
- `wps-open-save-document` run 1 (pass): cleanup: fixture closed; processes stopped 39172 | WPS also had open: `C:\Users\admin\AppData\Local\Temp\wps-p6\eval-open-174f04e\run-20261015T022144989017Z\work\run-1\wps-open-presentation-selection-replace\deck.pptx` (presentation)
- `wps-open-save-document` run 2 (pass): cleanup: fixture closed; processes stopped 52064 | WPS also had open: `C:\Users\admin\AppData\Local\Temp\wps-p6\eval-open-174f04e\run-20261015T022144989017Z\work\run-1\wps-open-presentation-selection-replace\deck.pptx` (presentation)
- `wps-open-save-document` run 3 (pass): cleanup: fixture closed; processes stopped 41268 | WPS also had open: `C:\Users\admin\AppData\Local\Temp\wps-p6\eval-open-174f04e\run-20261015T022144989017Z\work\run-1\wps-open-presentation-selection-replace\deck.pptx` (presentation)
- `wps-open-writer-selection-delete` run 1 (pass): cleanup: fixture closed; processes stopped 54568 | WPS also had open: `C:\Users\admin\AppData\Local\Temp\wps-p6\eval-open-174f04e\run-20261015T022144989017Z\work\run-1\wps-open-presentation-selection-replace\deck.pptx` (presentation)
- `wps-open-writer-selection-delete` run 2 (pass): cleanup: fixture closed; processes stopped 54952 | WPS also had open: `C:\Users\admin\AppData\Local\Temp\wps-p6\eval-open-174f04e\run-20261015T022144989017Z\work\run-1\wps-open-presentation-selection-replace\deck.pptx` (presentation)
- `wps-open-writer-selection-delete` run 3 (pass): error codes: VALIDATION_FAILED | cleanup: fixture closed; processes stopped 52424 | WPS also had open: `C:\Users\admin\AppData\Local\Temp\wps-p6\eval-open-174f04e\run-20261015T022144989017Z\work\run-1\wps-open-presentation-selection-replace\deck.pptx` (presentation)
- `wps-open-presentation-selection-insert` run 1 (pass): cleanup: fixture closed; processes none started | WPS also had open: `C:\Users\admin\AppData\Local\Temp\wps-p6\eval-open-174f04e\run-20261015T022144989017Z\work\run-1\wps-open-presentation-selection-replace\deck.pptx` (presentation)
- `wps-open-presentation-selection-insert` run 2 (FAIL): failed checks: tool_not_called (1 call(s)) | error codes: DOCUMENT_HELD_OPEN | cleanup: fixture closed; processes none started | WPS also had open: `C:\Users\admin\AppData\Local\Temp\wps-p6\eval-open-174f04e\run-20261015T022144989017Z\work\run-1\wps-open-presentation-selection-replace\deck.pptx` (presentation)
- `wps-open-presentation-selection-insert` run 3 (pass): cleanup: fixture closed; processes none started | WPS also had open: `C:\Users\admin\AppData\Local\Temp\wps-p6\eval-open-174f04e\run-20261015T022144989017Z\work\run-1\wps-open-presentation-selection-replace\deck.pptx` (presentation)
- `wps-open-presentation-selection-delete` run 1 (pass): cleanup: fixture closed; processes none started | WPS also had open: `C:\Users\admin\AppData\Local\Temp\wps-p6\eval-open-174f04e\run-20261015T022144989017Z\work\run-1\wps-open-presentation-selection-replace\deck.pptx` (presentation)
- `wps-open-presentation-selection-delete` run 2 (FAIL): failed checks: tool_not_called (1 call(s)) | error codes: DOCUMENT_HELD_OPEN | cleanup: fixture closed; processes none started | WPS also had open: `C:\Users\admin\AppData\Local\Temp\wps-p6\eval-open-174f04e\run-20261015T022144989017Z\work\run-1\wps-open-presentation-selection-replace\deck.pptx` (presentation)
- `wps-open-presentation-selection-delete` run 3 (pass): error codes: OPERATION_NOT_FOUND | cleanup: fixture closed; processes none started | WPS also had open: `C:\Users\admin\AppData\Local\Temp\wps-p6\eval-open-174f04e\run-20261015T022144989017Z\work\run-1\wps-open-presentation-selection-replace\deck.pptx` (presentation)
- `wps-open-spreadsheet-selection-replace` run 1 (pass): cleanup: fixture closed; processes stopped 54016 | WPS also had open: `C:\Users\admin\AppData\Local\Temp\wps-p6\eval-open-174f04e\run-20261015T022144989017Z\work\run-1\wps-open-presentation-selection-replace\deck.pptx` (presentation)
- `wps-open-spreadsheet-selection-replace` run 2 (pass): cleanup: fixture closed; processes stopped 54780 | WPS also had open: `C:\Users\admin\AppData\Local\Temp\wps-p6\eval-open-174f04e\run-20261015T022144989017Z\work\run-1\wps-open-presentation-selection-replace\deck.pptx` (presentation)
- `wps-open-spreadsheet-selection-replace` run 3 (pass): cleanup: fixture closed; processes stopped 17328 | WPS also had open: `C:\Users\admin\AppData\Local\Temp\wps-p6\eval-open-174f04e\run-20261015T022144989017Z\work\run-1\wps-open-presentation-selection-replace\deck.pptx` (presentation)
- `wps-open-spreadsheet-selection-delete` run 1 (pass): cleanup: fixture closed; processes stopped 33544 | WPS also had open: `C:\Users\admin\AppData\Local\Temp\wps-p6\eval-open-174f04e\run-20261015T022144989017Z\work\run-1\wps-open-presentation-selection-replace\deck.pptx` (presentation)
- `wps-open-spreadsheet-selection-delete` run 2 (pass): cleanup: fixture closed; processes stopped 55196 | WPS also had open: `C:\Users\admin\AppData\Local\Temp\wps-p6\eval-open-174f04e\run-20261015T022144989017Z\work\run-1\wps-open-presentation-selection-replace\deck.pptx` (presentation)
- `wps-open-spreadsheet-selection-delete` run 3 (pass): cleanup: fixture closed; processes stopped 23200 | WPS also had open: `C:\Users\admin\AppData\Local\Temp\wps-p6\eval-open-174f04e\run-20261015T022144989017Z\work\run-1\wps-open-presentation-selection-replace\deck.pptx` (presentation)
- `wps-open-save-as-untitled` run 1 (pass): cleanup: untitled 文字文稿1 not_found; notes.docx closed; fixture closed; processes stopped 30084
- `wps-open-save-as-untitled` run 2 (pass): cleanup: untitled 文字文稿1 not_found; notes.docx closed; fixture closed; processes stopped 17680
- `wps-open-save-as-untitled` run 3 (pass): cleanup: untitled 文字文稿1 not_found; notes.docx closed; fixture closed; processes stopped 55060
- `wps-open-zh-writer-selection-replace` run 1 (pass): cleanup: fixture closed; processes stopped 55252
- `wps-open-zh-writer-selection-replace` run 2 (pass): cleanup: fixture closed; processes stopped 53016
- `wps-open-zh-writer-selection-replace` run 3 (pass): cleanup: fixture closed; processes stopped 54588
- `wps-open-zh-spreadsheet-sheet-cells` run 1 (pass): cleanup: fixture closed; processes stopped 54428
- `wps-open-zh-spreadsheet-sheet-cells` run 2 (pass): cleanup: fixture closed; processes stopped 55024
- `wps-open-zh-spreadsheet-sheet-cells` run 3 (pass): cleanup: fixture closed; processes stopped 14872
- `wps-open-zh-document-export-text` run 1 (FAIL): failed checks: file_text (file missing) | error codes: EXPORT_OUTPUT_NOT_TEXT | cleanup: fixture closed; processes stopped 33836
- `wps-open-zh-document-export-text` run 2 (FAIL): failed checks: file_text (file missing) | error codes: EXPORT_OUTPUT_NOT_TEXT | cleanup: fixture closed; processes stopped 9460
- `wps-open-zh-document-export-text` run 3 (FAIL): failed checks: file_text (file missing) | error codes: EXPORT_OUTPUT_NOT_TEXT | cleanup: fixture closed; processes stopped 24164
- `wps-open-zh-save-as-untitled` run 1 (pass): cleanup: untitled 文字文稿1 not_found; 会议纪要.docx closed; fixture closed; processes stopped 51972
- `wps-open-zh-save-as-untitled` run 2 (pass): cleanup: untitled 文字文稿1 not_found; 会议纪要.docx closed; fixture closed; processes stopped 46364
- `wps-open-zh-save-as-untitled` run 3 (pass): cleanup: untitled 文字文稿1 not_found; 会议纪要.docx closed; fixture closed; processes stopped 54816

### Documents WPS had open outside the task workspaces

Listed right after the fixture opened. WPS reopens the documents of its previous session when it starts; they are the machine user's, so they are recorded here and left open.

- `C:\Users\admin\AppData\Local\Temp\wps-p6\eval-open-174f04e\run-20261015T022144989017Z\work\run-1\wps-open-presentation-selection-replace\deck.pptx` (presentation): 20 runs (wps-open-presentation-selection-replace run 2, wps-open-presentation-selection-replace run 3, wps-open-save-document run 1, wps-open-save-document run 2, wps-open-save-document run 3, wps-open-writer-selection-delete run 1, wps-open-writer-selection-delete run 2, wps-open-writer-selection-delete run 3, wps-open-presentation-selection-insert run 1, wps-open-presentation-selection-insert run 2, wps-open-presentation-selection-insert run 3, wps-open-presentation-selection-delete run 1, wps-open-presentation-selection-delete run 2, wps-open-presentation-selection-delete run 3, wps-open-spreadsheet-selection-replace run 1, wps-open-spreadsheet-selection-replace run 2, wps-open-spreadsheet-selection-replace run 3, wps-open-spreadsheet-selection-delete run 1, wps-open-spreadsheet-selection-delete run 2, wps-open-spreadsheet-selection-delete run 3)

### WPS processes after the run

- None.
