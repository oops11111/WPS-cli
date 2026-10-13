# Real-WPS results — main@3a40da6 (includes PR #30)

**Reported by:** the Windows operator. Recorded here as reported; not re-run in this environment.
**ET:** pid 31148, attachable.

## Case D — rollback with the document open: **pass**

Write `[["001"]]` into A1 while the workbook is open in WPS.

- `ok: false`; `VALIDATION_FAILED` (read-back `[[1]]`, requested `"001"`).
- `MUTATION_ROLLBACK_BLOCKED`, with the guidance: close the document in WPS without saving, then `restore-backup --document-id doc_1aa45ff3b78fd829 --backup-path ".wps-agent\backups\doc_1aa45ff3b78fd829\case.20261013T140609162706Z.xlsx" --request-id <new-id>`.
- `rollback.blocked: "file_locked"`, `rollback.performed: false`, `rollback.open_in_wps: true`.
- On disk at this point, A1 held the rejected value `1`.

After closing the document without saving, `restore-backup` returned `ok: true` ("Backup restored."). A1 returned to the pre-write seed value.

Note: the restore itself does not run the open-document probe, so `open_in_wps` was not re-checked after the close. The close was confirmed by `open-documents`, which no longer listed `case.xlsx`.

## `open_in_wps` — probe worked, the earlier `null` not reproduced

With the document open, the probe returned `true`. There was no `open_in_wps: null` and no `open_in_wps_error`. The earlier `null` (run on `main@4898428`) is still unexplained; `open_in_wps_error` remains in place to show the cause if it recurs.

## `mcp-config-audit` — root cause: `python` is the Windows Store alias

- The portable config uses `"command": "python"`. On this machine that resolves to `C:\Users\admin\AppData\Local\Microsoft\WindowsApps\python.exe`, which is the App Execution Alias, not an interpreter.
- Run directly with stdout and stderr redirected, it exits with code `9009` (command not found) and writes nothing to either stream. That is why the audit reports "Configured server closed stdout before replying" with empty stderr.
- The regression configuration assumed `python` would be a real interpreter with this package on its path. That assumption does not hold on machines where `python` is only the alias.

Proposed fix (not yet implemented): the regression runner should write the audit configuration at run time, with `sys.executable` as the command and the repository's `src` directory as `PYTHONPATH`, instead of a committed file that names `python`.

## Still open

1. The proposed fix for the audit configuration above, then a re-run of the safe profile on this machine.
2. The raw `open-documents` output for `open_in_wps: null`, if it recurs.
