# P3-117/118 Controlled HTML Import, Verification, and Export

`html-controlled-import` accepts only valid owned HTML v1 and creates a new
editable DOCX plus `<output>.wpsmap.json`. Every mapped object ID is represented
by a deterministic hashed Word bookmark name in the DOCX; the sidecar retains
the original ID, type, source order/index, parent, and content digest. Both
outputs refuse overwrite, and source HTML is unchanged.

`html-roundtrip-verify` reads the mapping and DOCX bookmarks. Text edits are
allowed; missing, duplicate, unexpected, and same-type reordered identities
fail verification. The check is structural and does not rewrite documents.

```powershell
python -m wps_ai_agent_cli html-controlled-import --input .\owned.html --output .\controlled.docx
python -m wps_ai_agent_cli html-roundtrip-verify --docx .\controlled.docx --mapping .\controlled.docx.wpsmap.json
python -m wps_ai_agent_cli html-roundtrip-export --docx .\controlled.docx --mapping .\controlled.docx.wpsmap.json --output .\roundtrip.html
```

Tests cover import, text edits, deletion/reordering detection, and no-overwrite.
The opt-in WPS integration opened the generated controlled DOCX in Writer,
saved a copy, verified all five object bookmarks, exported that copy, and
revalidated all stable IDs in the resulting owned HTML.

P3-118 adds `html-roundtrip-export` and MCP `wps_agent_html_roundtrip_export`.
It verifies the DOCX against its sidecar first, preserves object IDs, and
fails closed on unsupported WordprocessingML. Exported HTML is capped at 70 MiB.
P3-119 is next: bounded batch conversion with per-file result isolation.
