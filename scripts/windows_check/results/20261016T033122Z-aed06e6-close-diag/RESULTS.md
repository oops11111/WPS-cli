# Windows diagnostic of the workbook close

- Date: 2026-10-16 03:32 UTC
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
| no WPS process running | ok | none |
| open command .docx | ok | "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\wps.exe" "%1" |
| open command .xlsx | ok | "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\et.exe" "%1" |
| open command .pptx | ok | "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\wpp.exe" "%1" |
| inspect-env | ok | {"presentation": "kwpp.Application", "spreadsheets": "ket.Application", "writer": "kwps.Application"} |

## Closing a workbook opened the usual way

```
python scripts/windows_check/run_windows_check.py close-diag --method write_then_close --method write_then_close_false --method restore_close_in_wps --launch default
```

Each row is a new workbook opened with the registered open command (`default`, as a double-click) or with `/Automation` (`automation`, the control group), then closed with one method. Outcome `closed` means the call returned and WPS no longer lists the workbook. `write_then_*` rows write and save A1 in another process first, as the agent's selection write did in P7-007; `restore_close_in_wps` runs the product's `restore-backup --close-in-wps` after such a write, and `restored` means it succeeded and A1 is the backup's again. A recovery instance is a WPS process with `recover` in its command line. Workspaces: `C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261016T033122Z-aed06e6-close-diag`.

| Launch | Method | Attached via | In ROT | Outcome | HRESULT | Message | Recovery instance | Cleanup |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| default | `write_then_close` | running_object_table | True | returned, still open |  |  | none | fixture WPS_INSTANCE_NOT_AUTOMATABLE (WPS Spreadsheets is running with a window, but it did not register for automation, so its open documents cannot be reached. This happens when WPS was started by opening a file directly, for example by double-clicking it. Save your work in WPS, close every WPS Spreadsheets window, then reopen the document with the /Automation option, for example: wps.exe /Automation "<path to the document>". Nothing was launched, closed or changed.); processes stopped 49840 |
| default | `write_then_close_false` | running_object_table | True | returned, still open |  |  | none | fixture WPS_INSTANCE_NOT_AUTOMATABLE (WPS Spreadsheets is running with a window, but it did not register for automation, so its open documents cannot be reached. This happens when WPS was started by opening a file directly, for example by double-clicking it. Save your work in WPS, close every WPS Spreadsheets window, then reopen the document with the /Automation option, for example: wps.exe /Automation "<path to the document>". Nothing was launched, closed or changed.); processes stopped 28072 |
| default | `restore_close_in_wps` |  | None | restored |  |  | none | fixture WPS_INSTANCE_NOT_AUTOMATABLE (WPS Spreadsheets is running with a window, but it did not register for automation, so its open documents cannot be reached. This happens when WPS was started by opening a file directly, for example by double-clicking it. Save your work in WPS, close every WPS Spreadsheets window, then reopen the document with the /Automation option, for example: wps.exe /Automation "<path to the document>". Nothing was launched, closed or changed.); processes stopped 49292 |

### default `write_then_close`

- A1 written and saved in another process, then $doc.Close()
- outcome: returned, still open; still in Workbooks after 2 s: False; listed by open-documents: None
- error: `null`
- write before the close: `{"ok": true, "status": "written", "saved": true, "a1": "written by close-diag"}`
- WPS processes after the attempt:
  - et.exe 49840 `"C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\et.exe" "C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261016T033122Z-aed06e6-close-diag\default-write_then_close\close-check.xlsx"`

### default `write_then_close_false`

- A1 written and saved in another process, then $doc.Close($false)
- outcome: returned, still open; still in Workbooks after 2 s: False; listed by open-documents: None
- error: `null`
- write before the close: `{"ok": true, "status": "written", "saved": true, "a1": "written by close-diag"}`
- WPS processes after the attempt:
  - et.exe 28072 `"C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\et.exe" "C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261016T033122Z-aed06e6-close-diag\default-write_then_close_false\close-check.xlsx"`

### default `restore_close_in_wps`

- backup, A1 written and saved in another process, then restore-backup --close-in-wps
- outcome: restored; still in Workbooks after 2 s: None; listed by open-documents: None
- error: `null`
- restore: `{"write": {"ok": true, "status": "written", "saved": true, "a1": "written by close-diag"}, "a1_after_write": "written by close-diag", "step": "restore", "ok": true, "error_codes": [], "errors": [], "close_in_wps": "closed", "a1_after_restore": "seed"}`
- WPS processes after the attempt:
  - et.exe 49292 `"C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\et.exe" "C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261016T033122Z-aed06e6-close-diag\default-restore_close_in_wps\close-check.xlsx"`

### WPS processes after the run

- None.
