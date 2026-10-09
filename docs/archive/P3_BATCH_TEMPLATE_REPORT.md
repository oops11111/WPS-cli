# P3-121 Batch Template Reports

`batch-template-report` renders a local Markdown/text or DOCX template from a validated
`wps-agent-batch-conversion/v1` manifest. Supported placeholders are
`{{mode}}`, `{{source_directory}}`, `{{output_directory}}`, `{{total}}`,
`{{passed}}`, `{{failed}}`, and `{{files_table}}`. The table includes per-file
status, source/output paths, SHA-256 digests, and errors. No template code or
expressions are evaluated.

The DOCX template uses global summary placeholders in paragraphs/cells and one
repeatable table row with `{{file_status}}`, `{{file_source}}`,
`{{file_output}}`, `{{file_source_sha256}}`, `{{file_output_sha256}}`, and
`{{file_errors}}`. Row cloning preserves the template's table and cell styles.
Placeholders must remain within a single Word run; split or unknown fields are
rejected instead of damaging formatting.

The command checks summary counts and verifies source/output digests against
the current on-disk files, enforces manifest, template, file-count, and
report-size limits, and refuses to overwrite an existing report. Unknown or
malformed placeholders and inconsistent manifests are rejected.

```powershell
python -m wps_ai_agent_cli batch-template-report --manifest .\converted\batch-conversion-manifest.json --template .\report-template.md --output .\converted\batch-report.md
python -m wps_ai_agent_cli batch-template-report --manifest .\converted\batch-conversion-manifest.json --template .\report-template.docx --output .\converted\batch-report.docx
```

MCP tool `wps_agent_batch_template_report` exposes the same manifest, template,
and output contract with optional task tracking; its adapter call is covered by
an integration-style test.
