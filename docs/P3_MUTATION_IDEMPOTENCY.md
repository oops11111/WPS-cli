# Tracked Mutation Idempotency

P3-087 introduces a shared operation replay check. A stored request ID is
replayed only when the command and every bound request field match; a different
command or argument returns `IDEMPOTENCY_CONFLICT` before backup or backend
execution. This applies to presentation replacement, Writer replace/bookmark/
table writes, spreadsheet value/formula writes, and backup/restore operations.

The recorded results retain the arguments needed for comparison. Bookmark
replacement content is represented by a SHA-256 digest rather than copied into
the operation ledger solely for idempotency checks. Spreadsheet writes retain
the originally requested sheet separately from the resolved sheet name.
