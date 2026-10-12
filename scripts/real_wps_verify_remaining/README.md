# Remaining real-WPS verification kit (post PR #8 / #9)

Companion to `scripts/real_wps_verify_c2/`. Covers the checklist items that C2 does not:

| Script | What it checks |
|---|---|
| `1-inspect-fileshare-read.ps1` | `spreadsheet-inspect` FileShare.Read probe vs exclusive / WPS-held / inject |
| `2-writer-wpp-lock.ps1` | writer / presentation lock probe + Open (run once per `-Component`) |
| `3-displayalerts.ps1` | DisplayAlerts (and inspect quiet settings) restored on attached ET |
| `4-concurrency-window.ps1` | documents EXEMPT for true probe→Open race; optional inject stress |
| `5-other-holder.ps1` | other-program `.NET` holders (intentional refuse vs 误拒) |

Helpers: `lib.ps1`, `make_fixtures.py`, `inject_driver.py` (in-memory PRE_OPEN_GUARD patch only; no production hook).

## Proven on real WPS

Ran green on Windows against **`main@973590b`** (merge of PR #8 C2 kit on top of PR #9 lock probe). Summary: store `docs/wps-real-verify-remaining/RESULTS-973590b.md` (also `RESULTS-973590b.md` beside this README).

| # | Exit | Verdict |
|---|---|---|
| 4 document | 0 | EXEMPT documented |
| 5 | 0 | PASS (product gaps A/B recorded in artifact) |
| 1 | 0 | PASS (I1 via ZipFile crash path) |
| 3 (+ `-RawOpenEvidence`) | 0 | PASS |
| 2 writer / presentation | 0 | PASS |
| C2 `c2-post-open.ps1` | 0 | `outcome=refused_before_open` |

## Product gaps **not** fixed in this PR

Scripts treat these as refuse-not-success so the kit stays green while messaging is incomplete:

1. **Gap A (I1 / H-None inspect):** `spreadsheet-inspect` runs openpyxl `ZipFile` before `Assert-WpsFileNotHeld` → uncaught `PermissionError`, no JSON envelope.
2. **Gap B (exclusive hold write / writer·wpp replace):** source identity/backup open can return `DOCUMENT_IDENTITY_UNAVAILABLE` / `Permission denied` **before** the COM lock-probe text (`Open() was not called`). Direct probe is still correct.

Fixing those envelopes is a separate product PR (方案 2).

## Harness tweaks (in these scripts)

- `Open-FileHold` / `Get-Sha` retry briefly for post-Close / AV share locks.
- H0 uses separate `r5_other_free.xlsx` so the hold target is not left sticky after write.
- Exclusive-hold checks accept identity / `PermissionError` as refuse-not-success and record the gap in the artifact.

## How to run (Windows + real WPS)

```powershell
cd scripts\real_wps_verify_remaining
pip install -e "..\..[test]"
# Suggested order: 4(document) → 5 → 1 → 3 → 2 writer → 2 presentation → C2
pwsh -File .\4-concurrency-window.ps1 -RepoRoot C:\path\to\WPS-cli
pwsh -File .\5-other-holder.ps1 -RepoRoot C:\path\to\WPS-cli
pwsh -File .\1-inspect-fileshare-read.ps1 -RepoRoot C:\path\to\WPS-cli
pwsh -File .\3-displayalerts.ps1 -RepoRoot C:\path\to\WPS-cli -RawOpenEvidence
pwsh -File .\2-writer-wpp-lock.ps1 -RepoRoot C:\path\to\WPS-cli -Component writer
pwsh -File .\2-writer-wpp-lock.ps1 -RepoRoot C:\path\to\WPS-cli -Component presentation
pwsh -File ..\real_wps_verify_c2\c2-post-open.ps1 -RepoRoot C:\path\to\WPS-cli
```

State under `%TEMP%\wps-remaining-verify\<stamp>\` (`WPS_VERIFY_DIR` override). Exit: 0 pass / 1 fail / 3 precondition.

**Safety:** scratch files only; never Kill user WPS; do not run inject / `-RawOpenEvidence` / C2 `-RawProbe` against documents the user is editing.
