# MCP stdio release checkpoint

P3-145 reviewed the current implementation and its acceptance evidence.

## Corrected defect

The main thread waited for another stdin line before collecting a completed
batch future. A client waiting for a reply on an open connection could wait
indefinitely. Earlier EOF-only tests did not establish live connection behavior.

Batch workers now write their response before completing. A shared output lock
serializes complete JSON lines and flushes across the worker and main thread.
The single-batch limit includes response delivery. EOF joins the worker.

## Evidence

- An event-controlled test failed against the previous implementation because
  response delivery required another input line or EOF; it passes after the fix.
- A real CLI subprocess converts two HTML batches to DOCX sequentially while
  stdin stays open, returns both request IDs, and exits normally after EOF.
- The server and adapter suite ran 30 tests successfully.
- Previous filtered broad-suite evidence was 253 total, 231 passed, 22 skipped,
  with three additional history-sensitive tests excluded. It was not an
  unqualified full-suite pass.

## Remaining risk and next task

P3-146 addresses task_status.py: create/update currently read and overwrite a
shared JSON file without a transaction lock. Cancellation and progress can read
the same prior record and overwrite each other. A reader can also observe a
partially written file. Required evidence includes concurrent task creation,
terminal cancellation preservation, and complete-file publication. Cross-process
CLI updates need consideration as well as threads within one MCP server.

This checkpoint does not establish desktop-client interoperability, crash
recovery, or full PRD acceptance. Packaging validates content coverage, not
whether the included historical regression artifacts passed.
