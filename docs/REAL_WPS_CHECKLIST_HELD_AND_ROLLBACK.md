# Real-WPS checklist: held-handle envelopes and atomic rollback

Offline tests cover these changes, but none has run against real WPS. Run this checklist on Windows with a real WPS install, then record the results in `scripts/real_wps_verify_remaining/RESULTS-<commit>.md`.

Each case gives the command, the expected result, and the code it exercises. Use scratch copies of fixtures only. Never kill a WPS process that belongs to the user, and do not run these against a document the user is editing.

## Setup

```powershell
cd C:\path\to\WPS-cli
pip install -e ".[test]"
python -m wps_ai_agent_cli register-document --component spreadsheets --path %TEMP%\wps-check\held.xlsx
```

Use `python -m wps_ai_agent_cli --help` to confirm the exact flags before running. Record the `document_id` from the register output.

Record the SHA-256 of each fixture before every case:

```powershell
Get-FileHash %TEMP%\wps-check\held.xlsx -Algorithm SHA256
```

## Case A: `spreadsheet-inspect` against an exclusively held workbook (PR #13)

Code: `src/wps_ai_agent_cli/spreadsheet_inspect.py`, both `load_workbook` calls.

1. Hold the file exclusively from a second process, for example a PowerShell `[System.IO.File]::Open(path, 'Open', 'ReadWrite', 'None')` that stays open.
2. Run `python -m wps_ai_agent_cli spreadsheet-inspect --document-id <id> --range A1 --request-id checklist-a`.

Expected:
- stdout is one JSON envelope, with `"ok": false` and `DOCUMENT_IDENTITY_UNAVAILABLE` in `errors`.
- No Python traceback.
- The file's SHA-256 is unchanged.

Fail if: a traceback appears, stdout is empty, or the call returns `ok: true`.

## Case B: changing command against an exclusively held workbook (PR #12)

Code: `src/wps_ai_agent_cli/sessions.py`, `file_identity`.

1. Keep the exclusive hold from Case A.
2. Run `spreadsheet-write` with a one-cell value to `held.xlsx`, using a new `--request-id checklist-b`.

Expected:
- `"ok": false`, and the message says the file is held open by another handle, "such as WPS", and that nothing was written, saved or closed.
- The file's SHA-256 is unchanged.
- No backup was created for `checklist-b`. Check with `python -m wps_ai_agent_cli list-backups --document-id <id>`.

Fail if: the message is the bare `Permission denied`, or the file changed.

## Case C: changing command against a document WPS has open, no hold

This is the normal path. It checks that the envelope change did not break it.

1. Close the exclusive hold. Open `held.xlsx` in WPS.
2. Run `spreadsheet-write` with a one-cell value and `--request-id checklist-c`, after saving the open document in WPS. Use `save-open-document` or save in WPS first, so the backup matches what is on disk.

Expected: `"ok": true`, a backup exists for `checklist-c`, and the cell value reads back correctly.

## Case D: atomic rollback after a read-back failure (PR #15)

Code: `src/wps_ai_agent_cli/atomic_mutation.py`, applied to 21 commands in `open_documents.py`, `spreadsheet_ops.py`, `writer_ops.py`, and `presentation_ops.py`.

Find an input that WPS writes but reads back differently. A known one is a value WPS normalises on write, such as a number with a leading `+` or a date-like string, depending on the cell format. If you cannot find one in a short search, mark this case "not reproduced" and move on. Do not force the result.

1. Note the SHA-256 of `held.xlsx` (the pre-write state).
2. Run the write with that input and `--request-id checklist-d`.

Expected if the read-back fails:
- `"ok": false`, with `MUTATION_ROLLED_BACK` in `errors`, and `result.rollback.performed` is `true`.
- The file's SHA-256 matches the pre-write value, and `checklist-d`'s backup SHA-256 matches too.
- The `errors` list also keeps the original `VALIDATION_FAILED` error.

Then check what WPS shows:
- Close `held.xlsx` in WPS without saving, or reload it.
- Record whether WPS still shows the rejected value before the reload. This is the documented limit: rollback does not change an open WPS document.

Fail if: the file still holds the rejected value, `rollback.performed` is missing, or the response has no JSON envelope.

## Case E: restore failure is reported with the backup path

Code: `_undo_write` in `atomic_mutation.py`.

This case cannot be forced reliably on real WPS. Skip it and rely on the offline test `test_restore_failure_is_reported_with_the_backup_to_use`. Note the skip in the results file.

## Recording results

For each case record:
- Commit SHA of the tree you tested.
- WPS version and the ProgID you used (`python -m wps_ai_agent_cli inspect-env`).
- Outcome: pass, fail, or not reproduced, with the JSON envelope or the error text.
- The SHA-256 before and after.

Save the results in `scripts/real_wps_verify_remaining/RESULTS-<commit>.md`. Do not edit earlier result files.
