# Writer Exact Replacement Read-Back

P3-078 calculates the expected logical text before mutation and compares it
with the saved DOCX after WPS closes it. A successful result now requires an
exact paragraph sequence match and a WPS replacement count equal to the
preflight match count. Body scope checks direct main-story paragraphs and table
paragraphs; paragraph scope verifies the selected direct-body paragraph and
all neighboring body paragraphs. The result identifies changed paragraph
indices without returning their text. Deletion, equal find/replacement and a
replacement containing the original match are supported by the same check.

The existing backup is made before invoking WPS. Validation failure is reported
after save and retains that backup for recovery; no automatic restore is
attempted. Exactness uses the project's logical text model: run text is joined,
tabs and breaks are represented, deleted/move-from and text-box content are
excluded. This does not compare visual formatting or prove WPS did not alter
non-text package parts.

Local WPS integration on 2026-10-07 passed five paragraph-scope cases (shorter,
longer, delete, replacement containing the needle, and same-text replacement),
each with two repeated matches, plus whole-document replacement of four matches
across paragraphs and a table cell. The tests confirmed exact read-back, matched
counts, case-sensitive behavior, and preserved unrelated text. A simulated
neighbor corruption test is in normal offline discovery and verifies that
read-back fails while identifying the changed paragraph. Full suite and safe
regression remain the final gates for this task.

P3-079 implemented same-paragraph body bookmark fill. See P3_WRITER_BOOKMARK_FILL.md.
