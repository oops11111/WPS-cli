# P3-178 Unrecorded Mutation Recovery

A WPS operation can save its file before the main request reaches the operation ledger. Its derived pre-mutation backup is already recorded under `request_id:backup` (or `request_id:pre-restore` for restore). On retry, the main request is checked first. If it is absent but a derived backup exists, the source's current file identity is compared with the identity stored in that backup.

- Same identity: the source is still at the backed-up pre-mutation state, so normal retry may continue. This does not prove whether an interrupted WPS invocation ran without changing bytes.
- Different or unreadable identity: return `UNRECORDED_MUTATION_AMBIGUOUS` with the backup evidence. Do not infer success and do not automatically apply the mutation again.
- Main operation present: normal replay and P3-177 identity repair rules apply.

The check runs before command-specific target lookup. A command-level Spreadsheet test changes the worksheet name after backup without writing a main operation record; retry reports ambiguity rather than `SHEET_NOT_FOUND`. Focused backup/replay tests and the full 344-test default suite passed (27 skipped). Opt-in real WPS Writer and Spreadsheet checks passed 2/2 on temporary files. No remote Git was used.

The ledger does not prove whether a changed source was modified by WPS, an external editor, or file replacement. P3-179 will make this evidence inspectable without attempting a retry.
