# Windows diagnostic of the workbook close

- Date: 2026-10-16 02:16 UTC
- Commit: `4731b04` on `main`
- Machine: Windows-10-10.0.19045-SP0; Python 3.12.15
- WPS: wps.exe 12,8,2,18913, et.exe 12,8,2,18913, wpp.exe 12,8,2,18913
- Written by `scripts/windows_check/run_windows_check.py`; nothing in this file was typed by hand.

## Prerequisites

| Check | Result | Detail |
| --- | --- | --- |
| commit | ok | 4731b04 on main |
| python | ok | C:\Users\admin\.lody\repos\github---oops11111---wps-cli\worktrees\892d82f5-59c6-4cf8-bc52-46c8e7df5f60\.venv\Scripts\python.exe |
| windows | ok | Windows-10-10.0.19045-SP0 |
| no WPS process running | ok | none |
| open command .docx | ok | "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\wps.exe" "%1" |
| open command .xlsx | ok | "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\et.exe" "%1" |
| open command .pptx | ok | "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\wpp.exe" "%1" |
| inspect-env | ok | {"presentation": "kwpp.Application", "spreadsheets": "ket.Application", "writer": "kwps.Application"} |

## Closing a workbook opened the usual way

```
python scripts/windows_check/run_windows_check.py close-diag
```

Each row is a new workbook opened with the registered open command (`default`, as a double-click) or with `/Automation` (`automation`, the control group), then closed with one method. Outcome `closed` means the call returned and WPS no longer lists the workbook. A recovery instance is a WPS process with `recover` in its command line. Workspaces: `C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261016T021338Z-4731b04-close-diag`.

| Launch | Method | Attached via | In ROT | Outcome | HRESULT | Message | Recovery instance | Cleanup |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| default | `close` | running_object_table | True | closed |  |  | none | fixture not_open; processes left running: WPS still lists status.xlsx |
| default | `close_false` | running_object_table | True | closed |  |  | none | fixture not_open; processes none started |
| default | `close_false_missing` | running_object_table | True | closed |  |  | none | fixture not_open; processes none started |
| default | `saved_then_close` | running_object_table | True | closed |  |  | none | fixture not_open; processes none started |
| default | `item_by_name` | running_object_table | True | closed |  |  | none | fixture not_open; processes none started |
| default | `rot_object` | running_object_table | True | closed |  |  | none | fixture not_open; processes none started |
| default | `invoke_member` | running_object_table | True | closed |  |  | none | fixture not_open; processes none started |
| default | `window_close` | running_object_table | True | closed |  |  | none | fixture not_open; processes none started |
| automation | `close` | active_object | True | closed |  |  | none | fixture not_open; processes stopped 40128,47216 |
| automation | `close_false` | active_object | True | closed |  |  | none | fixture not_open; processes left running: WPS still lists status.xlsx |

### default `close`

- $doc.Close() — what close_unchanged_document tries first since P7-007
- outcome: closed; still in Workbooks after 2 s: False; listed by open-documents: False
- error: `null`
- WPS processes after the attempt:
  - et.exe 40128 `"C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\et.exe" "C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261016T021338Z-4731b04-close-diag\default-close\close-check.xlsx"`

### default `close_false`

- $doc.Close($false) — what it tried before P7-007
- outcome: closed; still in Workbooks after 2 s: False; listed by open-documents: False
- error: `null`
- WPS processes after the attempt:
  - et.exe 40128 `"C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\et.exe" "C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261016T021338Z-4731b04-close-diag\default-close\close-check.xlsx"`

### default `close_false_missing`

- $doc.Close($false, [Type]::Missing, $false) — every argument given
- outcome: closed; still in Workbooks after 2 s: False; listed by open-documents: False
- error: `null`
- WPS processes after the attempt:
  - et.exe 40128 `"C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\et.exe" "C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261016T021338Z-4731b04-close-diag\default-close\close-check.xlsx"`

### default `saved_then_close`

- $doc.Saved = $true, then $doc.Close()
- outcome: closed; still in Workbooks after 2 s: False; listed by open-documents: False
- error: `null`
- WPS processes after the attempt:
  - et.exe 40128 `"C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\et.exe" "C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261016T021338Z-4731b04-close-diag\default-close\close-check.xlsx"`

### default `item_by_name`

- $app.Workbooks.Item($doc.Name).Close() — the object WPS returns for the name
- outcome: closed; still in Workbooks after 2 s: False; listed by open-documents: False
- error: `null`
- WPS processes after the attempt:
  - et.exe 40128 `"C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\et.exe" "C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261016T021338Z-4731b04-close-diag\default-close\close-check.xlsx"`

### default `rot_object`

- Close() on the workbook object registered in the Running Object Table itself
- outcome: closed; still in Workbooks after 2 s: False; listed by open-documents: False
- error: `null`
- WPS processes after the attempt:
  - et.exe 40128 `"C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\et.exe" "C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261016T021338Z-4731b04-close-diag\default-close\close-check.xlsx"`

### default `invoke_member`

- IDispatch Close through InvokeMember with no arguments, past the PowerShell COM adapter
- outcome: closed; still in Workbooks after 2 s: False; listed by open-documents: False
- error: `null`
- WPS processes after the attempt:
  - et.exe 40128 `"C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\et.exe" "C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261016T021338Z-4731b04-close-diag\default-close\close-check.xlsx"`

### default `window_close`

- $doc.Windows.Item(1).Close() — the workbook's only window
- outcome: closed; still in Workbooks after 2 s: False; listed by open-documents: False
- error: `null`
- WPS processes after the attempt:
  - et.exe 40128 `"C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\et.exe" "C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261016T021338Z-4731b04-close-diag\default-close\close-check.xlsx"`

### automation `close`

- $doc.Close() — what close_unchanged_document tries first since P7-007
- outcome: closed; still in Workbooks after 2 s: False; listed by open-documents: False
- error: `null`
- WPS processes after the attempt:
  - et.exe 40128 `"C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\et.exe" "C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261016T021338Z-4731b04-close-diag\default-close\close-check.xlsx"`
  - et.exe 47216 `"C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\et.exe" /Automation "C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261016T021338Z-4731b04-close-diag\automation-close\close-check.xlsx"`

### automation `close_false`

- $doc.Close($false) — what it tried before P7-007
- outcome: closed; still in Workbooks after 2 s: False; listed by open-documents: False
- error: `null`
- WPS processes after the attempt:
  - et.exe 47744 `"C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\et.exe" /Automation "C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261016T021338Z-4731b04-close-diag\automation-close_false\close-check.xlsx"`

### WPS processes after the run

- et.exe 47744 `status.xlsx - WPS 表格`
