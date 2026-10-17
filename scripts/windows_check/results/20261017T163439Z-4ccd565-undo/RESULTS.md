# Windows check of the undo in WPS

- Date: 2026-10-17 16:37 UTC
- Commit: `4ccd565` on `main`
- Machine: Windows-10-10.0.19045-SP0; Python 3.12.15
- WPS: wps.exe 12,8,2,18913, et.exe 12,8,2,18913, wpp.exe 12,8,2,18913
- Written by `scripts/windows_check/run_windows_check.py`; nothing in this file was typed by hand.

## Prerequisites

| Check | Result | Detail |
| --- | --- | --- |
| commit | ok | 4ccd565 on main |
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

**6/6 scenarios passed.** The write runs in WPS as usual; inside this process only its reported read-back is replaced, so the command rejects the write and undoes it in WPS. Hashes are the file's SHA-256. Workspaces: `C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261017T163439Z-4ccd565-undo`.

| Scenario | Result | Error codes | Before write | Before undo | After undo | Content matches backup | Cleanup |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `writer-replace` | pass | `VALIDATION_FAILED`, `MUTATION_ROLLED_BACK` | `d0707e5a17f8` | `1753CF1AF100` | `B7B945D8A30D` | True | fixture closed; processes exited 58080 (main window closed) |
| `presentation-replace` | pass | `VALIDATION_FAILED`, `MUTATION_ROLLED_BACK` | `8ccf850a6678` | `EC2640A42547` | `F7B15C6E94D8` | True | fixture closed; processes exited 15680 (main window closed) |
| `spreadsheet-shape-text-replace` | pass | `VALIDATION_FAILED`, `MUTATION_ROLLED_BACK` | `2c4db8fd4fed` | `76CBBF1860C8` | `CF3B13255BE7` | True | fixture closed; processes exited 40376 (main window closed) |
| `spreadsheet-chart-title-replace` | pass | `VALIDATION_FAILED`, `MUTATION_ROLLED_BACK` | `1603fcde5905` | `D337CCC6E77B` | `9FC16373E6DE` | True | fixture closed; processes exited 57608 (main window closed) |
| `spreadsheet-axis-title-replace` | pass | `VALIDATION_FAILED`, `MUTATION_ROLLED_BACK` | `3dfc6ac4e063` | `22CEE0C7186C` | `D2028F21D518` | True | fixture closed; processes exited 46264 (main window closed) |
| `spreadsheet-series-values-replace` | pass | `VALIDATION_FAILED`, `MUTATION_ROLLED_BACK` | `2a19733c8a71` | `87C5CE30E00D` | `138BAB2225E1` | True | fixture closed; processes exited 14012 (main window closed) |

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

- `VALIDATION_FAILED`: Selection replacement read-back did not match the replacement values. WPS saved the write; the next entry says whether it was undone in WPS (pre-write backup: C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261017T163439Z-4ccd565-undo\spreadsheet-shape-text-replace-d3wpqumj\.wps-agent\backups\doc_45cbbe545a164c6b\chart_note.20261017T163543302901Z.xlsx).
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

- `VALIDATION_FAILED`: Selection replacement read-back did not match the replacement values. WPS saved the write; the next entry says whether it was undone in WPS (pre-write backup: C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261017T163439Z-4ccd565-undo\spreadsheet-chart-title-replace-jf3x6s2w\.wps-agent\backups\doc_ed8af8f8353945c8\chart_note.20261017T163615422770Z.xlsx).
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

- `VALIDATION_FAILED`: Selection replacement read-back did not match the replacement values. WPS saved the write; the next entry says whether it was undone in WPS (pre-write backup: C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261017T163439Z-4ccd565-undo\spreadsheet-axis-title-replace-g56pm76n\.wps-agent\backups\doc_acb0ee7110a4572c\chart_note.20261017T163642465696Z.xlsx).
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

- `VALIDATION_FAILED`: Selection replacement read-back did not match the replacement values. WPS saved the write; the next entry says whether it was undone in WPS (pre-write backup: C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261017T163439Z-4ccd565-undo\spreadsheet-series-values-replace-8ll879jx\.wps-agent\backups\doc_bd007955a3b2da69\chart_note.20261017T163707808327Z.xlsx).
- `MUTATION_ROLLED_BACK`: The write was undone in WPS: the command put the original back, read it back and saved it, and the saved file's content matches the pre-write backup. The document stays open in WPS and nothing else needs to be done.

### WPS processes after the run

- None.
