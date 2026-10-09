# P3-010 Advanced WPS Capability Scope

Date: 2026-10-03

## Selected Capability

Next capability: Writer table cell update.

Proposed CLI command: `writer-table-write`

Purpose: update a specific cell in a table inside a registered Writer document while preserving the existing safety contract: stable `document_id`, dry-run preview, mandatory backup before mutation, WPS-backed write, read-back validation, idempotent `request_id`, and optional `task_id` tracking.

## Why This Capability

Writer currently supports body and paragraph-scoped text replacement. Table cell editing is the next useful object-level Writer operation because many business templates store report metadata, approvals, prices, dates, and status fields in tables. It is also bounded enough to validate before moving to harder Writer features such as headers, footers, bookmarks, comments, or text boxes.

## Proposed Interface

```powershell
python -m wps_ai_agent_cli writer-table-write --document-id <doc_id> --table-index 1 --row 2 --column 3 --text "Approved" --dry-run --request-id <request_id>
python -m wps_ai_agent_cli writer-table-write --document-id <doc_id> --table-index 1 --row 2 --column 3 --text "Approved" --task-id <task_id> --request-id <request_id>
```

Arguments:

- `--document-id`: registered Writer document.
- `--table-index`: 1-based table index in document order.
- `--row`: 1-based row index.
- `--column`: 1-based column index.
- `--text`: replacement text for the target cell.
- `--dry-run`: preview table count, target coordinates, and current cell text without modifying.
- `--task-id`: optional long-running task status id.
- `--request-id`: idempotency key.

## Fixture Requirements

Create `fixtures/phase3/writer_table_fixture.docx` with:

- at least two tables
- table 1 with at least 3 rows and 3 columns
- a known marker in table 1 row 2 column 3, for example `PENDING_STATUS`
- body text outside the table to prove non-table content remains readable
- simple formatting in the target cell to observe whether WPS preserves table structure

Expected registered component: `writer`.

## Dry-run Contract

Dry-run must return:

- `table_count`
- target `table_index`, `row`, and `column`
- `current_text`
- `replacement_text`
- `would_modify = true`

Dry-run must not:

- create a backup
- write to the document
- create an operation ledger record for mutation

## Mutation Contract

Mutation must:

- require a stable `request_id`
- replay an existing operation for the same `request_id`
- create a backup using `<request_id>:backup`
- write through WPS COM
- read the target cell back after save
- return `validation_passed = true` only when the target cell matches `--text`
- include `backup`, `backup_replayed`, target coordinates, previous text, written text, and read-back text

## Validation Requirements

Minimum validation:

- target cell read-back equals requested text
- table count is reported before and after the write; a count change is evidence, but the hard validation gate is the target cell read-back
- non-table body text remains present in a snapshot
- invalid table, row, or column returns a structured error without mutation

Suggested error codes:

- `DOCUMENT_NOT_FOUND`
- `UNSUPPORTED_COMPONENT`
- `TABLE_NOT_FOUND`
- `CELL_NOT_FOUND`
- `VALIDATION_FAILED`

## Smoke Evidence

Safe unit tests:

- dry-run does not create `.wps-agent/backups`
- invalid coordinates fail without backup
- idempotency replay returns the same operation result

WPS smoke:

```powershell
python -m wps_ai_agent_cli writer-table-write --document-id <fixture_doc_id> --table-index 1 --row 2 --column 3 --text "APPROVED_STATUS" --request-id p3-011-writer-table-write-001
python -m wps_ai_agent_cli snapshot-document --document-id <fixture_doc_id> --request-id p3-011-writer-table-snapshot-001
python -m wps_ai_agent_cli list-backups --document-id <fixture_doc_id> --request-id p3-011-writer-table-backups-001
```

Acceptance evidence:

- command response `ok = true`
- validation `status = passed`
- backup path exists
- snapshot still returns Writer structure
- target table cell read-back equals `APPROVED_STATUS`

## MCP Contract

Expose as `wps_agent_writer_table_write` with:

- `mutates_document = true`
- `requires_wps = true`
- `dry_run`
- `task_id`
- safety notes covering WPS mutation, backup, read-back validation, and table coordinate risk

## Next Task

`P3-011 Writer table cell update prototype` should implement the CLI core, unit tests, MCP schema, and a first WPS-backed smoke run against the new fixture.
