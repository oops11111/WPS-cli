# Cross-Process Mutation Coordination

P3-175 adds a workspace-local, document-ID-keyed OS file lock under `.wps-agent/locks`. It spans each cooperating Agent's Writer, Spreadsheet, Presentation, and restore mutation call, including backup, WPS COM, readback, operation recording, and identity refresh. Re-registering the same document ID also waits for this lock. Another Agent process trying the same document ID times out with `DOCUMENT_BUSY`; a different ID can proceed. The lock file is retained, while the OS releases the lock on normal exit or process termination.

A two-process test verified contention, different-ID progress, release, and successful re-registration after release. The full default suite passed 336 tests (27 skipped). Real WPS mutation tests passed for Writer, Spreadsheet, and Presentation while the decorator held the lock; a final Writer/Spreadsheet rerun after registration locking passed 2/2. No remote Git was used.

This is cooperative serialization only for processes using the same workspace and document ID. It does not lock the document bytes against WPS or an unrelated editor, and it does not coordinate separate workspaces registering the same path. Source identity checks from P3-174 remain necessary. Different document IDs still share `documents.json` and `operations.json`; P3-176 addresses their atomicity and lost-update risk.
