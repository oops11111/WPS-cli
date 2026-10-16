# Windows agent evaluation

- Date: 2026-10-16 00:45 UTC
- Commit: `0f5d8ee` on `main`
- Machine: Windows-10-10.0.19045-SP0; Python 3.12.15
- WPS: wps.exe 12,8,2,18913, et.exe 12,8,2,18913, wpp.exe 12,8,2,18913
- Written by `scripts/windows_check/run_windows_check.py`; nothing in this file was typed by hand.

## Prerequisites

| Check | Result | Detail |
| --- | --- | --- |
| commit | ok | 0f5d8ee on main |
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

Claude Code CLI 2.1.295 (Claude Code), model CLI default, launch mode `default`. **11/11 tasks passed**, 0 skipped. Each task passes with at least 2 of 3 runs. Task workspaces: `C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261016T001559Z-0f5d8ee-eval`.

| Task | Passes | Turns | `wps-agent` calls | Tool errors | `off_path_calls` | `off_path_tools` |
| --- | --- | --- | --- | --- | --- | --- |
| `wps-open-document-export-text` | 3/3 | 4.3 (4, 4, 5) | 6 | 0 | 0 |  |
| `wps-open-writer-selection-replace` | 3/3 | 7.0 (10, 7, 4) | 17 | 0 | 3 | `snapshot_document`, `validate_document` |
| `wps-open-writer-selection-insert` | 3/3 | 10.0 (15, 8, 7) | 21 | 0 | 5 | `save_open_document`, `snapshot_document`, `validate_document` |
| `wps-open-presentation-selection-replace` | 3/3 | 6.3 (7, 6, 6) | 15 | 0 | 0 |  |
| `wps-open-save-document` | 3/3 | 11.0 (16, 12, 5) | 17 | 1 | 6 | `operation`, `snapshot_document`, `validate_document`, `writer_structure` |
| `wps-open-writer-selection-delete` | 3/3 | 7.7 (11, 6, 6) | 16 | 0 | 4 | `export_open_document_text`, `mutation_request_inspect`, `operation`, `snapshot_document` |
| `wps-open-presentation-selection-insert` | 3/3 | 6.3 (6, 8, 5) | 15 | 0 | 2 | `operation`, `snapshot_document` |
| `wps-open-presentation-selection-delete` | 3/3 | 8.7 (8, 10, 8) | 18 | 0 | 1 | `operation` |
| `wps-open-spreadsheet-selection-replace` | 3/3 | 8.7 (10, 9, 7) | 22 | 0 | 6 | `spreadsheet_read`, `spreadsheet_sheets` |
| `wps-open-spreadsheet-selection-delete` | 3/3 | 7.3 (6, 8, 8) | 19 | 0 | 5 | `spreadsheet_read`, `spreadsheet_sheets` |
| `wps-open-save-as-untitled` | 3/3 | 6.0 (6, 6, 6) | 13 | 0 | 1 | `operation` |

### Runs

- `wps-open-document-export-text` run 1 (pass): cleanup: fixture closed; processes left running: WPS still lists report.docx
- `wps-open-document-export-text` run 2 (pass): cleanup: fixture closed; processes none started
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
- `wps-open-save-document` run 1 (pass): error codes: VALIDATION_FAILED | cleanup: fixture closed; processes none started
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
- `wps-open-spreadsheet-selection-replace` run 1 (pass): cleanup: fixture COM_OPERATION_FAILED (0x800A01A8); processes stopped 29388
- `wps-open-spreadsheet-selection-replace` run 2 (pass): cleanup: fixture COM_OPERATION_FAILED (0x800A01A8); processes stopped 26352
- `wps-open-spreadsheet-selection-replace` run 3 (pass): cleanup: fixture COM_OPERATION_FAILED (0x800A01A8); processes stopped 20412
- `wps-open-spreadsheet-selection-delete` run 1 (pass): cleanup: fixture COM_OPERATION_FAILED (0x800A01A8); processes stopped 19088
- `wps-open-spreadsheet-selection-delete` run 2 (pass): cleanup: fixture COM_OPERATION_FAILED (0x800A01A8); processes stopped 48796
- `wps-open-spreadsheet-selection-delete` run 3 (pass): cleanup: fixture COM_OPERATION_FAILED (0x800A01A8); processes stopped 19088
- `wps-open-save-as-untitled` run 1 (pass): cleanup: untitled 文字文稿1 not_found; notes.docx closed; fixture closed; processes left running: WPS still lists report.docx
- `wps-open-save-as-untitled` run 2 (pass): cleanup: untitled 文字文稿2 not_found; notes.docx closed; fixture closed; processes none started
- `wps-open-save-as-untitled` run 3 (pass): cleanup: untitled 文字文稿3 not_found; notes.docx closed; fixture closed; processes none started

### WPS processes after the run

- wps.exe 42532 `report.docx - WPS 文字` "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\wps.exe" "C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261016T001559Z-0f5d8ee-eval\run-1\wps-open-save-as-untitled\report.docx"
