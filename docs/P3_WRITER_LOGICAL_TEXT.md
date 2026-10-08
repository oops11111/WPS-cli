# Writer Logical Text Validation

P3-076 replaces raw XML substring counting with parsed paragraph text. Existing
validate-document and writer-replace preflight/read-back reuse the fixed helper.
Paragraph-scoped reads use the same text extraction rules. Part filtering and
direct-body paragraph indices are preserved.

Text runs and hyperlinks within a paragraph are joined; XML entities are
decoded by the XML parser. Tabs become tab characters; explicit breaks and
carriage returns become newlines. Soft and nonbreaking hyphens retain their
Unicode characters. Matching does not cross paragraph, cell or story boundaries.
Body counting includes table paragraphs. Independent text boxes, deleted and
move-from content are excluded. Attributes and field instructions are not text;
stored field results and inserted/move-to text are counted when represented by
text nodes. Field evaluation and current WPS revision-display behavior are not
inferred. Header/footer/note/comment parts are eligible only when selected by
the existing part filter (or all parts); non-story XML is ignored.

Tests cover split runs with formatting, XML escapes, paragraph-scoped parity,
validation success/failure, dry-run counts, pre-backup no-match rejection,
unchanged source bytes, metadata false positives, table content, part filters,
paragraph/cell boundaries, tabs/breaks and text-box exclusion. The focused
document-text, Writer, validator and snapshot suite passed 19 tests.

This is offline logical text validation, not a complete model of WPS Find,
rendering, field calculation or text inside drawings. Table read/write helpers
retain their existing contract in this change. Real WPS execution equivalence
for special search characters and revision views remains unverified.

## Next Task

P3-077 hardens Writer replacement scope. Inspection found that the COM loop
captures range.End once, then changes text length without adjusting that bound.
It also uses document.Paragraphs.Item(index) while offline paragraph indices
count only direct body paragraphs. Test shorter/longer replacements, repeated
matches, matches after a table, and a following paragraph containing the same
needle. Make Find options deterministic and prevent wraparound/out-of-scope
edits. Establish an explicit mapping or reject unsupported paragraph structures
before editing, preserving documented indices. Use disposable fixture copies
for any required WPS integration tests and record their evidence separately.
