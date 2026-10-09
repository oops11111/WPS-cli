# Writer Bookmark Fill

P3-079 adds `writer-fill-bookmark` and `wps_agent_writer_fill_bookmark` for
filling a unique, non-reserved bookmark whose paired endpoints sit in the same
direct body paragraph. P3-186 also accepts a same-paragraph bookmark in a direct-body
table cell, with a single-line replacement of at most 4096 characters. The result preserves surrounding paragraph text and
uses WPS to replace only the bookmarked range. Preflight requires one paired
name and valid character offsets; missing, duplicate, malformed, cross-paragraph,
nested-table, text-box and header/footer targets are rejected before backup.

`--dry-run` reports the bookmark name, paragraph index and text lengths without
opening WPS or creating a backup. A write creates a backup, opens the registered
document in WPS, checks the current range text, writes the requested value,
recreates the bookmark around the inserted text, saves, then verifies the WPS
range. After closing WPS, offline read-back checks the bookmark is still unique,
its value matches, and the complete target paragraph equals the expected text.
Failures after the write retain the backup for recovery. Request IDs replay a
recorded successful write.

P3-173 also compares every direct body paragraph and table-cell text after the write. When the original body ends in a table, WPS may append exactly one empty body paragraph during save; that single normalization is accepted and reported as `body_tail_normalized=true`. Any other extra paragraph or changed table text still fails validation. Real WPS tests passed for both inline-run and direct-paragraph-child bookmark markers on temporary copies, including neighboring table/header/footer text, backup, and replay. This does not expand the supported write scope.

This implementation does not fill bookmarks spanning paragraphs, in nested cells,
text boxes, headers/footers, notes or comments. It does not promise formatting
preservation across mixed-format runs; WPS controls formatting at the replaced
range. The current verified fixture checks that a single bold bookmark run
remains bold. Page layout and visual fidelity are not checked.

For a supported direct table cell, post-save readback checks the bookmark remains
in the same cell and story paragraph, all document paragraphs match the expected
single-range replacement, and direct-body table topology is unchanged (grid
columns, row/cell arrangement, merge flags, and cell paragraph/nested-table counts).
The real WPS temporary-file test verifies adjacent cell and body text, backup,
post-save registration identity, and Python/CLI/MCP replay. P3-187 additionally
verified horizontal/vertical merges, a multi-paragraph cell, table style, and
neighboring italic and target bold runs on disposable real-WPS files. P3-188
normalizes relationship hyperlinks and simple/complex fields to semantic targets,
instructions, and display text for post-save comparison. Real WPS retained a
same-cell hyperlink and merge field through two consecutive bookmark fills, even
though it converted both nodes to complex fields. A bookmark range overlapping a
hyperlink or field is rejected before backup. Malformed/nested field boundaries,
broader formatting, and visual fidelity remain unverified.
P3-189 also rejects missing hyperlink relationships, empty field instructions,
orphaned field separators, unclosed complex fields, and nested fields before
backup or WPS startup. Offline tampering tests confirm that changed relationship
targets and field instructions fail post-save validation.
P3-190 extends table-cell readback to inline and anchored drawing trees, image
relationship targets and image-byte hashes, extents, transform, crop, position,
wrap, and visible object descriptions. A disposable real-WPS inline image passed;
a bookmark range enclosing a drawing is rejected before backup. P3-191 verified
one positioned, cropped anchor and two cropped inline images through WPS save.
P3-192 verified two anchors with distinct stacking ranks, horizontal positions,
crop data, relationship targets, and image hashes. P3-193 exports the disposable
document to PDF before and after WPS save, rasterizes both, and verifies that the
red and blue image masks are pixel-identical. An overlap sample confirms the
expected top drawing. P3-194 verified page and column/paragraph reference frames
through rendered WPS output and rejects character-relative anchors that can drift
when preceding bookmark text changes width. P3-195 verified cell-edge clamping,
page-edge raster clipping with `layoutInCell` disabled, and stable none, square,
and top-and-bottom wrap modes with unchanged adjacent text geometry. P3-196
verified unchanged page count, marker geometry, and full-page raster output in a
multi-page table-bookmark fixture. P3-197 audits multiple anchors across page
breaks and confirmed per-page visibility, stacking ranks, marker geometry, and
pixel-identical full-page output. P3-198 verified tight/through diamond wrap
polygons through WPS save. P3-199 verified left/right/largest plus asymmetric
floating distances and long text flow; the snapshot now records all four
distances. P3-200 rejects malformed polygons and invalid distances before
backup. P3-201 verified concave tight/through paths and rejects self-intersecting
or zero-area geometry before backup. P3-202 passed eight real-WPS tight/through
combinations across both winding directions and explicit/implicit closure; each
variant retained its own DrawingML, text, and raster through bookmark fill.
WPS renders a repeated terminal start point differently from implicit closure,
so the two source forms are not treated as equivalent. P3-203 audits WPS vertex
serialization and semantic readback normalization. Four cyclic start vertices
of a concave path also render differently from one another under both tight and
through; each raw vertex sequence nevertheless round-trips unchanged. Do not
canonicalize polygon start vertices. P3-204 tests redundant collinear vertices.
P3-204 found that adding collinear midpoints changes both tight and through
WPS rasters even though the outline is geometrically unchanged; both variants
round-trip individually, so collinear points also must not be simplified.
P3-205 audits near-degenerate and boundary coordinates.
P3-205 passed valid one-unit adjacent vertices and coordinates at 1/21599 near
the polygon bounds through four tight/through WPS round-trips with DrawingML,
text, and raster stability. P3-206 checks nearly collinear points before any
geometric tolerance is considered.
P3-206 found a 120/21600 midpoint offset is pixel-identical to a straight edge
at 1.5x PDF raster, while exact DrawingML vertices and per-file WPS round-trip
remain stable. P3-207 raised raster scale to 4x; straight and 120/600-unit
offsets remained pixel-identical for this fixture in tight/through, with exact
input geometry preserved. This does not prove semantic equivalence. P3-208
audits coordinate lexical validation. Signed/whitespace/leading-zero integer
spellings normalize numerically and pass WPS; decimal/empty coordinates reject
before backup with unchanged bytes. P3-209 confirms WPS boundary coordinates
0/21600 and rejects a 200-digit integer before backup. P3-210 checks non-ASCII
digits against the XML integer lexical contract.
P3-210 found Python's integer parser accepted Arabic-Indic numerals. Coordinate
preflight and snapshots now share an ASCII XML integer parser; Unicode digits,
decimal/empty strings, and huge out-of-range values reject before backup with
unchanged bytes. P3-211 checks XML whitespace boundaries.
P3-211 confirmed XML tab/newline whitespace folding and preflight rejection of
NBSP. P3-212 verified `-0`/`+00` normalization and four legal integer spellings
through real WPS. P3-213 rejects repeated/sign-only signs and embedded spaces
before backup. P3-214 confirms negative coordinates reject while negative zero
and inclusive endpoints are valid. P3-215 applies the same lexical normalization
to floating distances and rejects invalid values before backup. P3-216 enforces
nonnegative 635-EMU/twip alignment and Word signed-32 bounds; the maximum
aligned value round-trips through WPS, while overflow and nonaligned values
reject before backup. P3-217 compares omitted distance defaults with explicit
zero. The measured WPS defaults are `distT=0`, `distB=0`, `distL=114300`, and
`distR=114300` EMU. Snapshot normalization preserves those distinct defaults
instead of treating all omitted attributes as explicit zero. Real WPS
bookmarked fills passed for `none`, `square`, `tight`, `through`, and
`top_and_bottom`; each individual input retained semantics, text, and PDF
raster. Cross-input pixel differences are not required because the fixture
does not make the semantic difference visible in every wrap mode.
For `square`, an omitted `wrapText` now snapshots as `bothSides`, matching the
explicit default; the real-WPS bookmark-fill PDF text and raster remained
stable. The same equivalence and WPS readback stability hold for `tight` and
`through` polygon wraps and `top_and_bottom` wrapping.
Real WPS rewrites `top_and_bottom` `wrapText=left`, `right`, or `largest` to
`bothSides`. Those combinations are rejected during snapshot preflight, before
backup or COM, with source bytes unchanged.
On `wrapNone`, WPS preserves left/right/largest attributes; round-trip
structure, PDF text, and raster remain stable. Invalid `wrapText` enum values
are rejected before backup/COM for `wrapNone` as well.

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
