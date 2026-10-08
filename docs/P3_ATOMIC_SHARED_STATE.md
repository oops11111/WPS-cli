# P3-176 Atomic Shared State Persistence

## Scope

`documents.json` and `operations.json` are shared by commands addressing different document IDs. Their read-modify-write paths now hold workspace-local, cross-process state locks (`state:documents` and `state:operations`) with a 30-second acquisition bound. Writers publish a complete UTF-8 JSON file through a same-directory temporary file, flush/fsync, and `os.replace`. Windows replacement contention is retried for up to 20 attempts at 25 ms intervals. An unsuccessful replacement leaves the previous JSON and removes the temporary file.

Mutation commands also acquire a request-ID lock before their document-ID lock. This keeps replay checks and writes serialized when the same request ID is used with different documents. A standalone backup command uses the request-ID lock as well. All locks coordinate Agent processes using the same workspace; they do not constrain WPS or other external editors.

## Verification

- Four independent processes registered 12 different documents each and recorded 48 operations. Concurrent parent reads saw complete JSON, and both final registries contained all 48 records.
- Concurrent operations on two documents with one request ID produced one success and one `IDEMPOTENCY_CONFLICT`.
- A forced replacement failure retained the prior JSON bytes and removed the temporary file.
- P3-176 acceptance run: 339 tests run, 27 skipped, no failures; opt-in real WPS Writer and Spreadsheet integration: 2/2 passed on temporary files. P3-177 follow-up stress testing exposed and fixed a Windows lock-file initialization race and transient read sharing conflict; 10 repeated concurrency runs and the 342-test full suite then passed.

## Limits

The two registries are atomically updated individually, not as one transaction. P3-177 added safe replay repair for a process stopping after operation commit but before document identity refresh. A stop after WPS save but before operation commit remains ambiguous and is the P3-178 scope. The state locks require all participating Agent processes to use the same workspace path; non-cooperating writers are outside this guarantee.
