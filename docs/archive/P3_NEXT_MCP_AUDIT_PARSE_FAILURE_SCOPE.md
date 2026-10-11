# P3-289 MCP Audit Parse Failure Scope

## Goal

Treat malformed output from configured MCP server processes as normal audit failures rather than uncaught parser or reader-thread exceptions.

## Acceptance

- Invalid JSON and excessive JSON nesting produce bounded `configured_tools_list_smoke` failures.
- Invalid UTF-8 from stdout is reported through the audit result without an uncaught reader-thread traceback.
- Every failure path terminates and reaps the configured subprocess.
- A later independent configured audit still succeeds after malformed-output cases.

## Boundaries

- Preserve the existing line/queue/stderr limits, handshake, request IDs, and pagination.
- Do not execute tools or launch WPS.
- Run focused audit tests, the full suite, safe regression, package readiness, and documentation freshness.
