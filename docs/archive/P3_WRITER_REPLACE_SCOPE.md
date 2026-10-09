# Writer Replacement Scope

P3-077 updates the existing PowerShell COM Writer backend. Each replacement
adjusts the search end by the actual COM range length delta. Searches proceed
forward without wrapping, case-sensitively, without wildcard, format, whole-word,
phonetic or word-form matching. Match bounds and literal matched text are
checked before assignment. A caret in the search string is escaped for Find.

Paragraph indices remain direct-body indices. The backend filters WPS
paragraph ranges using the within-table indicator, checks the body count, then
checks the selected paragraph text against the offline target before mutation.
Unsupported structures that produce a different collection or text fail before
editing. The initial all-main-story ordinal assumption failed on this WPS build;
the implementation does not retain that assumption or silently choose a range.
Deletion read-back now measures removed matches instead of counting an empty
replacement string. Existing backup and operation recording remain in place.

## Verified Evidence

On 2026-10-07, an explicit opt-in test ran against local `kwps.Application`:

`WPS_AGENT_RUN_INTEGRATION=1 python -m unittest tests.test_writer_replace_scope -v`

Two tests passed in 24.268 seconds, including four WPS subcases: shorter text,
longer text, deletion, and a replacement containing the original needle.
Each document had a preceding paragraph, a table, a target paragraph containing
two lowercase matches and one uppercase near-match, and a following paragraph.
All four runs reported two backend replacements, preserved the uppercase text,
and left the neighboring paragraphs and table text unchanged. Fixtures and
backups were isolated in temporary test workspaces. Existing user documents
were not used. Normal test discovery skips this WPS integration unless opted in.

These results establish behavior only for this local build and tested fixtures.
Revision views, complex content controls, embedded stories and nonliteral WPS
special-character search behavior have not been broadly validated. Mismatched
paragraph collections/text are rejected rather than guessed.

P3-078 completed the exact read-back work. See P3_WRITER_EXACT_READBACK.md.
