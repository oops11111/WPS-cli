# Windows check of the undo in WPS

- Date: 2026-10-15 16:16 UTC
- Commit: `1c460da` on `main`
- Machine: Windows-10-10.0.19045-SP0; Python 3.12.15
- WPS: wps.exe 12,8,2,18913, et.exe 12,8,2,18913, wpp.exe 12,8,2,18913
- Written by `scripts/windows_check/run_windows_check.py`; nothing in this file was typed by hand.

## Prerequisites

| Check | Result | Detail |
| --- | --- | --- |
| commit | ok | 1c460da on main |
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

**2/2 scenarios passed.** The write runs in WPS as usual; inside this process only its reported read-back is replaced, so the command rejects the write and undoes it in WPS. Hashes are the file's SHA-256. Workspaces: `C:\Users\admin\AppData\Local\Temp\wps-windows-check\20261015T161619Z-1c460da-undo`.

| Scenario | Result | Error codes | Before write | Before undo | After undo | Content matches backup | Cleanup |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `writer-replace` | pass | `VALIDATION_FAILED`, `MUTATION_ROLLED_BACK` | `878f73ed6e23` | `29AC373480EE` | `03BD549636BE` | True | fixture closed; processes left running: WPS still lists 文字文稿3 |
| `presentation-replace` | pass | `VALIDATION_FAILED`, `MUTATION_ROLLED_BACK` | `858a45ab5b54` | `955DCE138405` | `36DB8B8DF2E1` | True | fixture closed; processes left running: WPS still lists deck.pptx |

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

### WPS processes after the run

- wps.exe 19088 `文字文稿3 * - WPS 文字`
- wpp.exe 24236 `deck.pptx - WPS 演示`
