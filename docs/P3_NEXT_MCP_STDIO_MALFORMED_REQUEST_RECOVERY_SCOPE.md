# P3-274 MCP stdio malformed request recovery

Status: done. Live subprocess regression and full suite passed; see `TASK_BOARD.md` and `PHASE3_RELEASE_READINESS_REFRESH.md`.

## Goal

Prove the command-line MCP server survives malformed input and remains usable for a later valid request on the same stdio connection.

## Acceptance

- Send a syntactically malformed JSON line and expect JSON-RPC parse error `-32700` with a null ID.
- Send array and scalar JSON values and expect invalid-request error `-32600` with a null ID.
- Send a valid `initialize` request on the same process and verify its response.
- Close stdin and verify clean process exit, no extra stdout responses, and no hung reader thread.

## Boundaries

This is a black-box subprocess regression test. The server implementation and wire contract remain unchanged unless the test exposes a defect.
