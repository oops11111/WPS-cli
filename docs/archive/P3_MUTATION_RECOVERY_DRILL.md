# P3-181 Ambiguous Mutation Recovery Drill

## Evidence

Two opt-in WPS integration tests created disposable DOCX and XLSX files, registered each, and recorded a pre-mutation backup. WPS then saved a Writer text replacement or Spreadsheet sheet rename without a main operation record, reproducing the post-save/pre-ledger interruption window. In both cases, CLI and MCP inspection returned `ambiguous`; same-request retry returned `UNRECORDED_MUTATION_AMBIGUOUS`, created no main record, and left the saved file identity unchanged.

Generated current files, backups, and hash manifests are retained at `artifacts/recovery-drill/p3-181-final/writer` and `artifacts/recovery-drill/p3-181-final/spreadsheets`. Both manifests were checked against the retained bytes: current and backup hashes matched their manifest entries, differed from each other, and `main_operation_recorded` was false. These are generated test files, not copies of user documents.

The default suite ran 347 tests (29 skipped, no failures). The two explicit WPS drill tests passed.

## Manual Decision Path

1. Run `mutation-request-inspect --request <id>` and preserve the current file, backup, and inspection output. Do not retry while status is `ambiguous`.
2. Compare the current file with the backup and independently validate the intended content. A changed hash alone does not prove that WPS completed the requested mutation; an external edit or replacement remains possible.
3. Decide explicitly whether to accept the current file or restore the known backup. Re-registration or `restore-backup` is a separate action after that decision, not part of this drill. Use a new request ID for any new mutation.

No original workspace document was modified, no automatic restore occurred, and no remote Git was used.
