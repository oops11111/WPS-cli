# Writer Structure Inspection

`writer-structure --document-id DOC_ID --limit 50` reads a registered DOCX without opening WPS or modifying the document. The matching MCP tool is `wps_agent_writer_structure`.

The response includes total body paragraph, heading, used paragraph-style, bookmark, and warning counts. Each corresponding list is limited to 1-200 entries (default 50), and `truncated` signals omitted entries. Headings include a 120-character preview; styles show their ID, name and resolution; bookmarks retain pairing status and scope. Invalid limits, missing or non-Writer registrations, and malformed DOCX files return structured failures.

For large documents, select one list and follow its `pagination.next_offset` until null. Pass the first page's `source_sha256` as `--expected-sha256` on subsequent pages; a changed file is rejected instead of silently shifting results. For example:

```powershell
python -m wps_ai_agent_cli writer-structure --document-id DOC_ID --section headings --limit 100
python -m wps_ai_agent_cli writer-structure --document-id DOC_ID --section headings --limit 100 --offset 100 --expected-sha256 HASH_FROM_FIRST_PAGE
python -m wps_ai_agent_cli writer-structure --document-id DOC_ID --section bookmarks --bookmark-name ClientName
```

Bookmark lookup matches the exact name and reports `bookmark_query.status` as `missing`, `unique`, or `ambiguous`, with `match_count`. Matching duplicates can also be paged. `--offset` requires a selected section; the default `all` view remains the first page of every list.

Add `--include-text --text-limit 200` to a bookmark-name query to inspect its bounded text (1-4096 characters). The `bookmark_value` status distinguishes `available`, `empty`, `missing`, `ambiguous`, `unsupported_scope`, and `invalid_range`; `text_length` gives the full character count when readable, while `truncated` reports clipping. Text is returned only for a uniquely paired bookmark in one paragraph of the body, a table cell, or a header/footer story. Cross-paragraph, cross-container, text-box, ambiguous, and revision-bearing paragraphs remain unsupported. Use offset zero for text inspection. The CLI and MCP tool expose the same parameters and results. This read-only capability does not extend `writer-fill-bookmark`, which remains limited to direct body paragraphs without revision or text-box content.

```powershell
python -m wps_ai_agent_cli writer-structure --document-id DOC_ID --section bookmarks --bookmark-name ClientName --include-text --text-limit 200
```

The `evidence_backend` is `offline-ooxml` and `wps_validated` is false. Headings and styles concern direct body paragraphs; bookmarks include document, header and footer parts as described in `scope`. This is structural file inspection, not a claim about rendered layout or WPS version fidelity.
