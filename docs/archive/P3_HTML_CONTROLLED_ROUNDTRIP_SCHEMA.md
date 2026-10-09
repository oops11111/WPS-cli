# P3-116/117 Controlled HTML Identity Schema v1

## Contract

The read-only `html-roundtrip-plan` prototype accepts only owned HTML with
`data-wps-schema="wps-agent-html/v1"` on `<html>` or a
`<meta name="wps-agent-schema" content="wps-agent-html/v1">` declaration.
Each mapped paragraph, heading, list item, table, row, cell, header cell,
hyperlink, or image requires a unique `data-wps-object-id` matching
`[A-Za-z0-9][A-Za-z0-9._:-]{0,127}`.

The deterministic mapping includes source SHA-256, object ID/type, per-type
native index, nearest mapped parent ID, and text SHA-256. It does not fetch
resources or mutate the source. Missing/duplicate/invalid IDs, unsupported
ID-bearing elements, CSS, and executable content are errors, not lossy
warnings.

## Limitations and next step

P3-116 introduced schema/identity planning. P3-117 now persists mappings in an
adjacent `.wpsmap.json` and as native DOCX bookmarks; the verifier checks
missing/duplicate/unmapped IDs and same-type ordering after edits. P3-118 adds
reverse serialization after bookmark verification, retaining IDs and rejecting
unrepresented Word content.

## Verification

- Unit tests verify deterministic mappings, parent IDs, schema rejection,
  duplicate/missing IDs, and CSS/script rejection.
- CLI and MCP adapter/schema contracts expose the read-only plan command.
- Import/verify tests confirm text edits are allowed while removed and
  reordered bookmarks are rejected. The opt-in WPS integration checks bookmark
  retention through a Writer open/save cycle.
- Targeted HTML/MCP/security/catalog/browser set: 27 tests passed, 1 WPS test
  skipped by that run's environment gate; the separate real WPS Writer
  open/save integration passed.
- Broad test run: 213 executed, 199 passed and 14 skipped; the three
  history-sensitive regression/performance tests were excluded because
  earlier troubleshooting generated failed local regression evidence. No
  report artifacts were removed or rewritten.
