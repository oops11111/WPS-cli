# P3-011 Writer Table Write Report

## Summary

P3-011 implemented a Writer table cell update capability for the local CLI and MCP adapter.

New entry points:

- CLI: `writer-table-write`
- MCP: `wps_agent_writer_table_write`
- Fixture: `fixtures\phase3\writer_table_fixture.docx`

The command validates the target table/cell from DOCX XML before mutation, supports dry-run preview, creates a backup before a real write, writes through WPS COM, reads the target cell back after save, and records successful operations for idempotency replay.

## Implementation Notes

- `document_text.docx_body_tables` and `docx_table_cell_text` read body table content from `word/document.xml`.
- `writer_table_write` rejects unsupported documents, missing tables, and missing cells before backup or mutation.
- Real writes create backup request ids with `<request_id>:backup`.
- Validation passes when the target cell read-back equals the requested text.
- `table_count` and `final_table_count` are reported for evidence. WPS may normalize table XML on save, so table count preservation is reported as `table_count_preserved` instead of being the hard validation gate.

## Evidence

Fixture registration:

```powershell
python -m wps_ai_agent_cli register-document --component writer --path fixtures\phase3\writer_table_fixture.docx --request-id p3-011-register-writer-table-fixture
```

Registered document id:

```text
doc_151a6b8a2c87c79f
```

Dry-run:

```powershell
python -m wps_ai_agent_cli writer-table-write --document-id doc_151a6b8a2c87c79f --table-index 1 --row 2 --column 3 --text FINAL_STATUS --dry-run --request-id p3-011-writer-table-dry-run-002
```

Result:

- `ok = true`
- `current_text = APPROVED_STATUS`
- `replacement_text = FINAL_STATUS`
- no backup was created

Real WPS write:

```powershell
python -m wps_ai_agent_cli writer-table-write --document-id doc_151a6b8a2c87c79f --table-index 1 --row 2 --column 3 --text FINAL_STATUS --request-id p3-011-writer-table-write-002
```

Result:

- `ok = true`
- `backup.created = true`
- backup path: `.wps-agent\backups\doc_151a6b8a2c87c79f\writer_table_fixture.20261003T102907235910Z.docx`
- `write_backend = powershell-com`
- `backend_read_back_text = FINAL_STATUS`
- `read_back_text = FINAL_STATUS`
- `validation_passed = true`

Idempotency replay:

```powershell
python -m wps_ai_agent_cli writer-table-write --document-id doc_151a6b8a2c87c79f --table-index 1 --row 2 --column 3 --text FINAL_STATUS --request-id p3-011-writer-table-write-002
```

Result:

- `ok = true`
- summary: `Writer table write request replayed from idempotency record.`

MCP adapter dry-run:

```powershell
python -m wps_ai_agent_cli mcp-call --name wps_agent_writer_table_write --arguments-json "{\"document_id\":\"doc_151a6b8a2c87c79f\",\"table_index\":1,\"row\":2,\"column\":3,\"text\":\"MCP_STATUS\",\"dry_run\":true,\"request_id\":\"p3-011-mcp-writer-table-dry-run\"}"
```

Result:

- `ok = true`
- mapped CLI command: `writer-table-write`
- nested response `ok = true`
- nested current text: `FINAL_STATUS`

## Verification

```powershell
$env:PYTHONPATH='src'
python -m unittest discover -s tests
python -m wps_ai_agent_cli security-audit --request-id p3-011-security-audit-precheck
```

Observed:

- 87 unit tests passed.
- `security-audit` passed with 39 MCP tools and 7 mutating tools during P3-011. P3-012 later expanded the tool surface to 40 MCP tools and 8 mutating tools.

## Follow-Up

P3-012 should integrate this advanced Writer capability into repeatable regression and restore evidence without adding desktop WPS launch requirements to the safe CI profile.
