# P3-269 MCP Config-Audit Pagination Failure Tests

## Objective

Prove that the configured-server pagination audit fails safely when a server violates page traversal invariants.

## Cases

- Duplicate tool names across otherwise valid pages: report a failed configured `tools/list` audit with the complete tool/page counts and duplicate count.
- Repeated `nextCursor`: report a failed audit with page count and an explanatory error; do not invoke the same cursor indefinitely.

## Method and Boundaries

Use a tiny temporary fake server command under the test's temporary directory. Do not edit user MCP configuration, use remote services, launch WPS, or modify user documents. Keep tests deterministic and independent of installed desktop clients.

## Acceptance

Both cases fail the audit for the expected reason, expose enough diagnostic details to triage, and terminate within the normal audit timeout.
