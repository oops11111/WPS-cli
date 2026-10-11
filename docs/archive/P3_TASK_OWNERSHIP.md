# Task ownership and startup cancellation

Task creation now compares command, request_id, and document_id when task_id
already exists. A mismatch returns TASK_ID_CONFLICT without changing the record.
The CLI operation wrapper returns failed preflight without invoking its operation
factory. Callers retrying an operation must supply its original request ID;
an automatically generated new request ID is a different owner.

Matching successful tasks still reach the existing operation handler, allowing
commands with operation-ledger replay to retain their behavior. This is not a
new generic result cache. Failed/cancelled tasks require a new task ID after
the caller reviews their partial results. A failed transition to running, such
as cancellation after creation, also aborts before the operation factory runs.
Cancellation after the running transition remains cooperative, not instantaneous.

Tests cover conflicts in all three identity fields, pending and terminal records,
unchanged persisted bytes, zero operation calls on rejection, the same-owner
handler path, terminal retry rejection, and cancellation during startup.
Two adapter tests now use temporary task-state files rather than fixed task IDs
in the user's workspace. Existing local task history is left intact.

After P3-149, full discovery passed 270 tests (248 passed, 22 skipped). After
P3-150, the related status/CLI/adapter/server suite passed 71 tests.

The subsequent full run exposed a first-use Windows lock-file race: writing
an initialization byte could conflict with another process already holding that
range. Lock acquisition now uses the Windows-supported range beyond EOF without
an initialization write. The four-process creation test passed five consecutive
runs after the correction. Final full discovery: 272 tests, 250 passed,
22 skipped, no failures or exclusions.

Next: P3-151 must add completed HTML batch replay with argument and artifact
verification. Current batch conversion has no operation-ledger replay and its
no-overwrite guard is not equivalent to successful idempotent result replay.
Active duplicate request execution and broader operation-ledger concurrency
also remain separate concerns; these changes do not claim to resolve them.
