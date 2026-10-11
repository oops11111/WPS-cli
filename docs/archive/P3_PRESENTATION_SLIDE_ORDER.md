# Presentation Logical Slide Order

P3-074 changes existing presentation reads and replacement preflight to follow
the ordered slide IDs in `ppt/presentation.xml` and resolve their relationships.
Part filenames are no longer interpreted as user-visible page numbers.
Unreferenced slide parts are ignored. Snapshot pages include blank and
image-only slides with zero text objects.

Missing or invalid slide relationships produce `INVALID_PRESENTATION_STRUCTURE`
through snapshot and replacement preflight. External targets, duplicate targets,
unknown relationship types and missing parts are rejected before mutation.
Absolute package part paths are supported. This reader currently accepts the
existing Transitional OOXML namespace; unsupported namespaces are rejected.
No filename-order fallback is used for malformed files.

Validation on 2026-10-07:

- Targeted presentation and snapshot suite: 13 tests passed.
- New cases cover reordered and non-contiguous slide parts, ignored orphan
  parts, logical slide-scoped dry-run counts, blank/image-only snapshots,
  empty decks, invalid relationships and absolute package targets.
- Existing three `fixtures/phase0/*.pptx` files read successfully; hashes were
  unchanged after reading. All three contain one logical slide.
- New fixture tests assert no COM call for dry-run and no backup or COM call
  for invalid relationships.

These are offline parsing and preflight results. They do not establish WPS
mutation behavior on reordered decks, visual fidelity, or new WPS version
compatibility. Shape indexing, grouped shapes and image replacement remain
separate product requirements.

Next task P3-075 extends the existing Writer snapshot with headings, paragraph
styles and bookmark locations. Keep current top-level body paragraph indices
stable; report unsupported locations explicitly rather than mapping table or
header bookmarks to a body paragraph. Resolve outline levels from direct
paragraph properties and style inheritance, with cyclic inheritance handled.
Test document integrity, missing styles, custom heading names, bookmarks across
paragraphs and existing snapshot consumers before declaring it complete.
