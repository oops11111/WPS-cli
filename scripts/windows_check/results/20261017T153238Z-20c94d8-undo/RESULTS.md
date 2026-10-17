# Windows check of the undo in WPS

- Date: 2026-10-17 15:35 UTC
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
| no WPS process running | ok | none |
| open command .docx | ok | "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\wps.exe" "%1" |
| open command .xlsx | ok | "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\et.exe" "%1" |
| open command .pptx | ok | "C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\wpp.exe" "%1" |
| inspect-env | ok | {"presentation": "kwpp.Application", "spreadsheets": "ket.Application", "writer": "kwps.Application"} |

## Undo in WPS after an injected read-back failure

```
python scripts/windows_check/run_windows_check.py undo
```

**5/6 scenarios passed.** The write runs in WPS as usual; inside this process only its reported read-back is replaced, so the command rejects the write and undoes it in WPS. Hashes are the file's SHA-256. Workspaces: `C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261017T153238Z-20c94d8-undo`.

| Scenario | Result | Error codes | Before write | Before undo | After undo | Content matches backup | Cleanup |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `writer-replace` | pass | `VALIDATION_FAILED`, `MUTATION_ROLLED_BACK` | `63852caf0c43` | `965BBFD9108C` | `6093E3CEC427` | True | fixture closed; processes exited 34484 (main window closed) |
| `presentation-replace` | pass | `VALIDATION_FAILED`, `MUTATION_ROLLED_BACK` | `7bf17eec5a8d` | `69917425A8AF` | `7D2163E14D93` | True | fixture closed; processes exited 56996 (main window closed) |
| `spreadsheet-shape-text-replace` | pass | `VALIDATION_FAILED`, `MUTATION_ROLLED_BACK` | `eab1b141775d` | `659F6A7A8628` | `3B4B7FF1093F` | True | fixture closed; processes exited 58904 (main window closed) |
| `spreadsheet-chart-title-replace` | pass | `VALIDATION_FAILED`, `MUTATION_ROLLED_BACK` | `1a4288771e1c` | `C08C18771A97` | `890FE55F24D7` | True | fixture closed; processes exited 55764 (main window closed) |
| `spreadsheet-axis-title-replace` | pass | `VALIDATION_FAILED`, `MUTATION_ROLLED_BACK` | `492006f10605` | `5BBE61167DB5` | `49EAE3E053FE` | True | fixture closed; processes exited 40172 (main window closed) |
| `spreadsheet-series-values-replace` | FAIL | `SELECTION_MISMATCH` | `ca367afd18ce` | - | - | None | fixture closed; processes exited 36900 (main window closed) |

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

- `VALIDATION_FAILED`: Selection replacement read-back did not match the replacement values. WPS saved the write; the next entry says whether it was undone in WPS (pre-write backup: C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261017T153238Z-20c94d8-undo\spreadsheet-shape-text-replace-rjoybav7\.wps-agent\backups\doc_6f3ef0fc857fa6e0\chart_note.20261017T153341821168Z.xlsx).
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

- `VALIDATION_FAILED`: Selection replacement read-back did not match the replacement values. WPS saved the write; the next entry says whether it was undone in WPS (pre-write backup: C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261017T153238Z-20c94d8-undo\spreadsheet-chart-title-replace-uw75t96k\.wps-agent\backups\doc_73ba39d009008068\chart_note.20261017T153411641216Z.xlsx).
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

- `VALIDATION_FAILED`: Selection replacement read-back did not match the replacement values. WPS saved the write; the next entry says whether it was undone in WPS (pre-write backup: C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261017T153238Z-20c94d8-undo\spreadsheet-axis-title-replace-k00zhpcd\.wps-agent\backups\doc_f573a87dc044d97c\chart_note.20261017T153436855587Z.xlsx).
- `MUTATION_ROLLED_BACK`: The write was undone in WPS: the command put the original back, read it back and saved it, and the saved file's content matches the pre-write backup. The document stays open in WPS and nothing else needs to be done.

### `spreadsheet-series-values-replace`

- FAILED: the read-back failure was injected after WPS reported the write done
- FAILED: WPS saved the write (the file changed before the undo)
- FAILED: the command reported VALIDATION_FAILED, then MUTATION_ROLLED_BACK
- ok: no MUTATION_ROLLBACK_BLOCKED
- FAILED: rollback.rolled_back_in_wps is true
- FAILED: rollback.content_matches_backup is true
- ok: the text on disk is the text before the write
- ok: WPS reports the document saved after the undo

- rollback status `None`, read back null
- WPS read back after the write (replaced by the injection): null

- `SELECTION_MISMATCH`: The selection or its text changed between preview and write; no change was made.

### WPS processes after the run

- None.
