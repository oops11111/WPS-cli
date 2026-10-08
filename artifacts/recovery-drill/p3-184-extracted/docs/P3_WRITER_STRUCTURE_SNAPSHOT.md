# Writer Structure Snapshot

P3-075 extends `snapshot-document` and its existing MCP mapping. It adds
paragraph style IDs/names, resolution status, outline levels and heading levels,
plus headings, bookmark endpoints, warnings and explicit scope metadata.
Existing paragraph counts, previews and direct-body paragraph indices remain.

Outline precedence is direct paragraph properties, the paragraph style and its
base styles, then document defaults. The default paragraph style applies when
no explicit style is given. OOXML outline levels 0-8 map to heading levels 1-9;
level 9 means body text. Names such as Heading1 alone are not proof of an
outline level. Missing, cyclic or duplicate styles and invalid levels are
reported; ambiguous definitions are not selected arbitrarily.

Bookmarks are paired by ID within each scanned part. Endpoints identify the
part, scope and direct-body paragraph index where applicable. Table, text-box,
header/footer and other-body endpoints are labelled separately with no body
paragraph index. Missing, reversed or duplicate endpoints are explicit.
`body_paragraph_range_supported` describes endpoint location precision only;
it does not authorize editing or prove that intervening content is simple.

Boundaries: offline Transitional OOXML at standard word/document.xml and
word/styles.xml paths; heading scope is direct-body paragraphs. Header/footer
XML parts are scanned, including unreferenced parts. Footnotes, endnotes and
comments are excluded. No character offsets, computed pagination, visual
heading detection, WPS style inference or live WPS access is claimed.

Validation: 18 focused Writer/snapshot tests passed, including inheritance,
direct body-text override, default styles, malformed styles, cross-paragraph
bookmarks, table/text-box/header scopes, malformed bookmark pairing and an
unchanged-document hash assertion. Three existing DOCX fixtures and the source
PRD were also read without changing their hashes. The original PRD contains
duplicate style IDs and missing Normal references; diagnostics are expected.

Next P3-076: correct Writer text counting used by validation and replacement
preflight. Current document_text.py searches raw XML, so split runs and XML
escaping can cause misses and attribute names can cause false positives.
Parse visible text with explicit paragraph/story boundaries, retain part
filters, cover tables and ensure attributes/field instructions are not counted
as body text. Verify through validate-document and writer-replace dry-run.
