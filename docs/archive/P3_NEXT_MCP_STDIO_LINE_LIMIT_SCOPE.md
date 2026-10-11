# P3-279 Bound MCP stdio input line size

Status: done. MCP tests: 40 passed; full suite: 450 passed/65 skipped.

Status: done. MCP tests: 40 passed; full suite: 450 passed/65 skipped.

Status: implementation and focused verification in progress. Current bound: 1,048,576 text characters including the newline delimiter.

## Goal

Prevent an untrusted MCP peer from forcing unbounded buffering and JSON decoding work with one oversized newline-delimited record.

## Acceptance

- Define a documented maximum line length and enforce it before JSON parsing.
- Drain the remainder of an oversized record in bounded chunks so the next line remains aligned.
- Emit exactly one bounded invalid-request response for the oversized record and continue serving a following valid exchange.
- Cover exact-limit and over-limit cases plus a real subprocess recovery test.

## Boundaries

Only the MCP stdio transport framing is in scope; this does not change CLI JSON argument limits or tool payload limits.
