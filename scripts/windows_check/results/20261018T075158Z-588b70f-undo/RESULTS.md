# Windows check of the undo in WPS

- Date: 2026-10-18 07:54 UTC
- Commit: `588b70f` on `main`
- Machine: Windows-10-10.0.19045-SP0; Python 3.12.15
- WPS: wps.exe 12,8,2,18913, et.exe 12,8,2,18913, wpp.exe 12,8,2,18913
- Package: wps-ai-agent-cli 0.9.0 (installed), `C:\Users\admin\wps-agent-venv-clean\Lib\site-packages\wps_ai_agent_cli\__init__.py`
- Written by `scripts/windows_check/run_windows_check.py`; nothing in this file was typed by hand.

## Prerequisites

| Check | Result | Detail |
| --- | --- | --- |
| commit | ok | 588b70f on main |
| python | ok | C:\Users\admin\wps-agent-venv-clean\Scripts\python.exe |
| windows | ok | Windows-10-10.0.19045-SP0 |
| installed package | ok | 0.9.0 from C:\Users\admin\wps-agent-venv-clean\Lib\site-packages\wps_ai_agent_cli\__init__.py |
| no WPS process running | ok | none |
| open command .docx | ok | "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\wps.exe" "%1" |
| open command .xlsx | ok | "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\et.exe" "%1" |
| open command .pptx | ok | "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\wpp.exe" "%1" |
| inspect-env | ok | {"presentation": "kwpp.Application", "spreadsheets": "ket.Application", "writer": "kwps.Application"} |

## Undo in WPS after an injected read-back failure

```
python scripts/windows_check/run_windows_check.py undo
```

**6/6 scenarios passed.** The write runs in WPS as usual; inside this process only its reported read-back is replaced, so the command rejects the write and undoes it in WPS. Hashes are the file's SHA-256. Workspaces: `C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261018T075158Z-588b70f-undo`.

| Scenario | Result | Error codes | Before write | Before undo | After undo | Content matches backup | Cleanup |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `writer-replace` | pass | `VALIDATION_FAILED`, `MUTATION_ROLLED_BACK` | `9101bd83c425` | `AEE61C525787` | `5FCB6CF03210` | True | fixture closed; processes exited 36432 (main window closed) |
| `presentation-replace` | pass | `VALIDATION_FAILED`, `MUTATION_ROLLED_BACK` | `bd6f2a769475` | `ECAD299381BF` | `6B97570439C7` | True | fixture closed; processes exited 15252 (Quit()) |
| `spreadsheet-shape-text-replace` | pass | `VALIDATION_FAILED`, `MUTATION_ROLLED_BACK` | `5e686055bd37` | `ED17191DD8F9` | `DE613401C94C` | True | fixture closed; processes exited 53180 (main window closed) |
| `spreadsheet-chart-title-replace` | pass | `VALIDATION_FAILED`, `MUTATION_ROLLED_BACK` | `d69754c14fa2` | `A2598A347F16` | `5727263D97C5` | True | fixture closed; processes exited 27380 (main window closed) |
| `spreadsheet-axis-title-replace` | pass | `VALIDATION_FAILED`, `MUTATION_ROLLED_BACK` | `6bcaa436e6a0` | `ED080AA5246C` | `87922A000D4D` | True | fixture closed; processes exited 68428 (main window closed) |
| `spreadsheet-series-values-replace` | pass | `VALIDATION_FAILED`, `MUTATION_ROLLED_BACK` | `9a2ae4103839` | `F5600FCE53B6` | `3ED616CC4915` | True | fixture closed; processes exited 70040 (main window closed) |

### `writer-replace`

- ok: the read-back failure was injected after WPS reported the write done
- ok: WPS saved the write (the file changed before the undo)
- ok: the command reported VALIDATION_FAILED, then MUTATION_ROLLED_BACK
- ok: no MUTATION_ROLLBACK_BLOCKED
- ok: rollback.rolled_back_in_wps is true
- ok: rollback.content_matches_backup is true
- ok: the text on disk is the text before the write
- ok: WPS reports the document saved after the undo

- rollback status `reverted`, read back "DRAFT"
- WPS read back after the write (replaced by the injection): "FINAL"

- `VALIDATION_FAILED`: Selection replacement read-back did not match the replacement text.
- `MUTATION_ROLLED_BACK`: The write was undone in WPS: the command put the original back, read it back and saved it, and the saved file's content matches the pre-write backup. The document stays open in WPS and nothing else needs to be done.

### `presentation-replace`

- ok: the read-back failure was injected after WPS reported the write done
- ok: WPS saved the write (the file changed before the undo)
- ok: the command reported VALIDATION_FAILED, then MUTATION_ROLLED_BACK
- ok: no MUTATION_ROLLBACK_BLOCKED
- ok: rollback.rolled_back_in_wps is true
- ok: rollback.content_matches_backup is true
- ok: the text on disk is the text before the write
- ok: WPS reports the document saved after the undo

- rollback status `reverted`, read back "Status: DRAFT"
- WPS read back after the write (replaced by the injection): "FINAL"

- `VALIDATION_FAILED`: Selection replacement read-back did not match the replacement text.
- `MUTATION_ROLLED_BACK`: The write was undone in WPS: the command put the original back, read it back and saved it, and the saved file's content matches the pre-write backup. The document stays open in WPS and nothing else needs to be done.

### `spreadsheet-shape-text-replace`

- ok: the read-back failure was injected after WPS reported the write done
- ok: WPS saved the write (the file changed before the undo)
- ok: the command reported VALIDATION_FAILED, then MUTATION_ROLLED_BACK
- ok: no MUTATION_ROLLBACK_BLOCKED
- ok: rollback.rolled_back_in_wps is true
- ok: rollback.content_matches_backup is true
- ok: the text on disk is the text before the write
- ok: WPS reports the document saved after the undo

- rollback status `reverted`, read back "DRAFT"
- WPS read back after the write (replaced by the injection): "FINAL"

- `VALIDATION_FAILED`: Selection replacement read-back did not match the replacement values. WPS saved the write; the next entry says whether it was undone in WPS (pre-write backup: C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261018T075158Z-588b70f-undo\spreadsheet-shape-text-replace-e9lfguun\.wps-agent\backups\doc_cc1b84159fb9e66b\chart_note.20261018T075306309410Z.xlsx).
- `MUTATION_ROLLED_BACK`: The write was undone in WPS: the command put the original back, read it back and saved it, and the saved file's content matches the pre-write backup. The document stays open in WPS and nothing else needs to be done.

### `spreadsheet-chart-title-replace`

- ok: the read-back failure was injected after WPS reported the write done
- ok: WPS saved the write (the file changed before the undo)
- ok: the command reported VALIDATION_FAILED, then MUTATION_ROLLED_BACK
- ok: no MUTATION_ROLLBACK_BLOCKED
- ok: rollback.rolled_back_in_wps is true
- ok: rollback.content_matches_backup is true
- ok: the text on disk is the text before the write
- ok: WPS reports the document saved after the undo

- rollback status `reverted`, read back "DRAFT"
- WPS read back after the write (replaced by the injection): "FINAL"

- `VALIDATION_FAILED`: Selection replacement read-back did not match the replacement values. WPS saved the write; the next entry says whether it was undone in WPS (pre-write backup: C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261018T075158Z-588b70f-undo\spreadsheet-chart-title-replace-jzhewc0m\.wps-agent\backups\doc_ac4abf67f2a1f0ca\chart_note.20261018T075338754570Z.xlsx).
- `MUTATION_ROLLED_BACK`: The write was undone in WPS: the command put the original back, read it back and saved it, and the saved file's content matches the pre-write backup. The document stays open in WPS and nothing else needs to be done.

### `spreadsheet-axis-title-replace`

- ok: the read-back failure was injected after WPS reported the write done
- ok: WPS saved the write (the file changed before the undo)
- ok: the command reported VALIDATION_FAILED, then MUTATION_ROLLED_BACK
- ok: no MUTATION_ROLLBACK_BLOCKED
- ok: rollback.rolled_back_in_wps is true
- ok: rollback.content_matches_backup is true
- ok: the text on disk is the text before the write
- ok: WPS reports the document saved after the undo

- rollback status `reverted`, read back "DRAFT"
- WPS read back after the write (replaced by the injection): "FINAL"

- `VALIDATION_FAILED`: Selection replacement read-back did not match the replacement values. WPS saved the write; the next entry says whether it was undone in WPS (pre-write backup: C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261018T075158Z-588b70f-undo\spreadsheet-axis-title-replace-gwbebi61\.wps-agent\backups\doc_18a61c6b67524623\chart_note.20261018T075406421767Z.xlsx).
- `MUTATION_ROLLED_BACK`: The write was undone in WPS: the command put the original back, read it back and saved it, and the saved file's content matches the pre-write backup. The document stays open in WPS and nothing else needs to be done.

### `spreadsheet-series-values-replace`

- ok: the read-back failure was injected after WPS reported the write done
- ok: WPS saved the write (the file changed before the undo)
- ok: the command reported VALIDATION_FAILED, then MUTATION_ROLLED_BACK
- ok: no MUTATION_ROLLBACK_BLOCKED
- ok: rollback.rolled_back_in_wps is true
- ok: rollback.content_matches_backup is true
- ok: the text on disk is the text before the write
- ok: WPS reports the document saved after the undo

- rollback status `reverted`, read back "120\t95"
- WPS read back after the write (replaced by the injection): "130\t90"

- `VALIDATION_FAILED`: Selection replacement read-back did not match the replacement values. WPS saved the write; the next entry says whether it was undone in WPS (pre-write backup: C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261018T075158Z-588b70f-undo\spreadsheet-series-values-replace-t0o234ep\.wps-agent\backups\doc_754f2a00745e541a\chart_note.20261018T075433829095Z.xlsx).
- `MUTATION_ROLLED_BACK`: The write was undone in WPS: the command put the original back, read it back and saved it, and the saved file's content matches the pre-write backup. The document stays open in WPS and nothing else needs to be done.

### WPS processes after the run

- None.
