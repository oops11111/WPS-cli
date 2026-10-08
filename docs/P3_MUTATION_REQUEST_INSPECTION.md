# P3-179 Mutation Request Inspection

`mutation-request-inspect --request <id>` and `wps_agent_mutation_request_inspect` read the main operation record plus derived `:backup` and `:pre-restore` records. They compare each recorded source identity with the current file without opening WPS, changing a file, refreshing registration, or creating a new operation.

Statuses are `no_evidence`, `retryable` (backup exists, source unchanged), `ambiguous` (backup exists, source changed or unavailable), `recorded`, `recorded_repairable` (committed file still present, registration stale), `recorded_changed`, `recorded_unavailable`, and `recorded_unverified`. A recorded status describes ledger evidence, not proof that the current file still contains the operation's result.

Temporary-file tests verified status transitions, command-level CLI/MCP equality, and unchanged JSON bytes after inspection. The stdio MCP smoke exercised initialize, 81-tool listing, and the new tool call with a missing request; all checks passed. P3-180 added state-specific, non-destructive recovery guidance to the response and local validation runbook.
