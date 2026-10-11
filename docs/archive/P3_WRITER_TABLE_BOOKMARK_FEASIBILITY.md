# P3-185 Writer Table-Cell Bookmark Fill Feasibility

A disposable DOCX contained a uniquely paired bookmark around `Old` in one table-cell paragraph, with `Before ` and ` After` outside the bookmark, a neighboring cell, and body paragraphs on both sides of the table. Offline inspection classified the range as supported read-only table text but outside the public fill scope.

With an opt-in real WPS run, a verified pre-change backup was created and the existing low-level bookmark COM routine replaced `Old` with `New`. Post-save source identity remained stable through readback. The bookmark read `New`; its cell read `Before New After`; the neighboring cell and body paragraphs were unchanged; the backup hash matched its recorded source identity. The focused WPS test passed 1/1.

This P3-185 record is feasibility evidence, not a public capability claim at that point. P3-186 subsequently added a narrowly bounded public path with backup, structure/readback, replay, and CLI/MCP verification; see `P3_WRITER_BOOKMARK_FILL.md`. The P3-185 default suite ran 355 tests (30 skipped, no failures). No original user file or remote Git was touched.
