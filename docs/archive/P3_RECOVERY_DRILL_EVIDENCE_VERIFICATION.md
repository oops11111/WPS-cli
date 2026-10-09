# P3-182 Recovery Drill Evidence Verification

`local-handoff-summary` now includes `recovery_drill_evidence`, a bounded read-only check of the generated `artifacts/recovery-drill/p3-181-final` files. If the directory is absent, status is `absent` and the optional check does not block unrelated handoff. Once present, both Writer and Spreadsheet must have an object manifest, expected ambiguous/no-main-record state, fixed in-workspace current/backup paths, files no larger than 64 MiB, matching SHA-256 values, and distinct current/backup bytes. Missing, redirected, malformed, or modified evidence fails the check.

The real workspace handoff returned `passed` with both components passing and no verifier errors. Focused verifier/handoff tests passed 5/5; the full default suite ran 351 tests (29 skipped, no failures). The verifier does not launch WPS or alter evidence. P3-183 will cover package inclusion and byte-for-byte handoff.
