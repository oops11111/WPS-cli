# Writer Bookmark Fill

P3-079 adds `writer-fill-bookmark` and `wps_agent_writer_fill_bookmark` for
filling a unique, non-reserved bookmark whose paired endpoints sit in the same
direct body paragraph. The result preserves surrounding paragraph text and
uses WPS to replace only the bookmarked range. Preflight requires one paired
name and valid character offsets; missing, duplicate, malformed, cross-paragraph,
table, text-box and header/footer targets are rejected before backup.

`--dry-run` reports the bookmark name, paragraph index and text lengths without
opening WPS or creating a backup. A write creates a backup, opens the registered
document in WPS, checks the current range text, writes the requested value,
recreates the bookmark around the inserted text, saves, then verifies the WPS
range. After closing WPS, offline read-back checks the bookmark is still unique,
its value matches, and the complete target paragraph equals the expected text.
Failures after the write retain the backup for recovery. Request IDs replay a
recorded successful write.

P3-173 also compares every direct body paragraph and table-cell text after the write. When the original body ends in a table, WPS may append exactly one empty body paragraph during save; that single normalization is accepted and reported as `body_tail_normalized=true`. Any other extra paragraph or changed table text still fails validation. Real WPS tests passed for both inline-run and direct-paragraph-child bookmark markers on temporary copies, including neighboring table/header/footer text, backup, and replay. This does not expand the supported write scope.

This implementation does not fill bookmarks spanning paragraphs, in cells,
text boxes, headers/footers, notes or comments. It does not promise formatting
preservation across mixed-format runs; WPS controls formatting at the replaced
range. The current verified fixture checks that a single bold bookmark run
remains bold. Page layout and visual fidelity are not checked.

Evidence on 2026-10-07:

- Offline tests cover character offsets, dry-run without file changes, missing
  and reserved names, duplicate names, cross-paragraph and table rejection,
  no backup before rejected writes, commit read-back and idempotent replay.
- Local `kwps.Application` integration passed on a temporary DOCX. It filled
  `Client` from `old` to `Northwind`, retained the bookmark, preserved bold
  formatting, and verified the full paragraph `Dear Northwind!`.
- MCP catalog drift is zero at 61 tools (9 mutating, 11 WPS-required, 52
  read-only). `mcp-smoke --expected-min-tools 61 --tool-name wps_agent_tasks`
  passes; mutating bookmark tools are not called by the generic smoke harness.

P3-080 formula/cache/display inspection is complete; see
`P3_SPREADSHEET_INSPECT.md` for its WPS evidence. P3-081 now examines how the
existing spreadsheet reader represents dates, percentages, currency and empty
cells without changing its raw-value contract.
