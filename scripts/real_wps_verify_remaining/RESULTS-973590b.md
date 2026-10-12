# Real-WPS remaining checklist results — `main@973590b`

**Date:** 2026-10-12  
**Repo worktree:** Windows checkout @ `973590bbeab453c0e81ea6c8f822eb68fc383a73`  
**Kit:** this directory (harness tweaks only; no product changes)

| # | Script | Exit | Verdict |
|---|---|---|---|
| 4 | `4-concurrency-window.ps1` (document) | **0** | EXEMPT documented |
| 5 | `5-other-holder.ps1` | **0** | PASS (see product gaps) |
| 1 | `1-inspect-fileshare-read.ps1` | **0** | PASS (I1 via ZipFile crash path) |
| 3 | `3-displayalerts.ps1 -RawOpenEvidence` | **0** | PASS |
| 2 | `2-writer-wpp-lock.ps1 -Component writer` | **0** | PASS |
| 2 | `2-writer-wpp-lock.ps1 -Component presentation` | **0** | PASS |
| C2 | `scripts/real_wps_verify_c2/c2-post-open.ps1` | **0** | `outcome=refused_before_open` |

## Product gaps (messaging/envelope incomplete; not 误拒 success)

1. **`spreadsheet-inspect` + exclusive hold:** openpyxl `ZipFile` before `Assert-WpsFileNotHeld` → uncaught `PermissionError`, no JSON envelope.
2. **`spreadsheet-write` / writer·wpp replace + exclusive hold:** identity/backup open can return `DOCUMENT_IDENTITY_UNAVAILABLE` / `Permission denied` before COM lock-probe text. Direct probe still correct. Under `FileShare.Read`/`ReadWrite`, changing commands get the proper held-open / Open-not-called refuse.
3. **Item 4 true race:** EXEMPT as checklist recommends.

## Status of the product gaps (offline fixes)

These fixes are verified with offline unit tests only. Real-WPS re-verification is still needed.

| Gap | Fix | State |
| --- | --- | --- |
| 1. `spreadsheet-inspect` + exclusive hold: uncaught `PermissionError`, no JSON envelope | `spreadsheet_inspect.py` returns `DOCUMENT_IDENTITY_UNAVAILABLE` for an unreadable workbook and closes a half-opened pair | Branch `fix/spreadsheet-inspect-held-envelope` (`902a18d`), no PR yet |
| 2. Changing commands + exclusive hold: bare `Permission denied` before the COM probe | `sessions.py` `file_identity` names the held handle and states that nothing was written | Merged in PR #12 (`e4b43b1`) |

Still to do: re-run the held-handle cases on Windows against a real WPS session, using the `real_wps_verify_remaining` kit, and record the new results here.

## Harness notes

- `Open-FileHold` / `Get-Sha` retry for brief post-Close locks.
- H0 uses separate `r5_other_free.xlsx` so hold file is not left sticky after write.
- Checks accept identity/`PermissionError` as refuse-not-success for exclusive holders while recording the gap in the artifact.
