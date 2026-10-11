# Registered Document Identity Audit

P3-172 found that a registered `document_id` previously bound only component and resolved path. Replacing the file at that path could redirect a later mutation under the old ID. The registration now stores SHA-256, file device, and file inode. A changed file, a same-content atomic replacement, or a legacy registration lacking identity evidence must be explicitly re-registered before a new backup or document mutation. Re-registration retains the stable path-derived ID. A missing or renamed source still returns `INPUT_FILE_NOT_FOUND`.

The shared backup preflight compares the current source with registration and checks source stability plus backup bytes after copying. It leaves a failed partial backup in place for diagnosis and does not start WPS mutation. `restore-backup` may protect and restore a stale current file, but checks that the pre-restore source did not change during copying. Successful local operations refresh the registered identity; idempotent replay returns its prior result without a new mutation. A failed operation after WPS has already changed the file does not refresh identity, so the next mutation requires investigation and explicit re-registration or restore.

Default tests cover path replacement, in-place external edits, legacy records, renamed files, copy-time changes, Writer mutation refusal before COM, and CLI/MCP error parity. The full suite passed 326 tests (25 skipped). Eight opt-in WPS tests passed on temporary Writer and Spreadsheet files, including a Writer fill followed by another backup and consecutive Spreadsheet edits.

This is a preflight guard, not a file lock. An external process could still replace or edit the file after the final backup check and before WPS opens it; eliminating that race requires a separately designed cross-process transaction or locking strategy. No remote Git was used.

During the WPS identity test, a copy of `writer_nested_scope_wps_fixture.docx` with a direct-body `BodyMark` failed the existing bookmark-fill readback validation after COM. The identity check and backup had passed. A second, previously validated bookmark-marker layout filled successfully. P3-173 tracks the compatibility issue; this audit does not claim that all direct-body bookmarks are writable in WPS.

P3-173 resolved that observed failure: WPS correctly changed the bookmarked text but appended an empty direct body paragraph after the fixture's terminal table. The updated readback accepts only that structural normalization while still checking every existing body paragraph and table-cell text. Real WPS tests for both marker placements passed; this does not alter the residual post-backup race described above.

P3-174 subsequently added a source/backup recheck immediately before every COM mutation and a post-COM source recheck after readback. See `P3_MUTATION_SOURCE_STABILITY.md`. It narrows the residual window but does not add an OS lock.
