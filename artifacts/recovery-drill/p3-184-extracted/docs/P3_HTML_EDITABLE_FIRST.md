# P3-115 HTML Editable-First Semantic Conversion

## Delivered

`html-editable` and MCP tool `wps_agent_html_editable` create a new editable
DOCX from bounded local HTML. The mapper creates native heading/paragraph
styles, bullet/numbered paragraphs, editable tables, clickable DOCX hyperlinks,
and local inline images. It records object counts and a SHA-256 digest.

## Fidelity and resource policy

CSS layout is not replicated. Inline styles, class selectors, embedded and
linked stylesheets are listed as unsupported; scripts and unsupported elements
are omitted and reported. Links are retained as hyperlinks but are never
visited during conversion. Images must resolve inside the HTML directory after
symlink resolution. HTML is limited to 10 MiB; at most 100 images, 20 MiB each
and 50 MiB total are embedded. Remote images and data URLs are not embedded.
Existing output paths are rejected and the source file is never modified.

Install with `pip install .[html]`. The generated DOCX is structurally editable;
this mode makes no visual-equivalence claim. WPS opening and cross-version
rendering remain separate validation gates.

## Verification

Offline integration verifies headings, paragraphs, list styles, table cell
readback, hyperlink relationship, embedded image count, CSS/script warnings,
remote-image omission, and output no-overwrite behavior.

The opt-in local WPS integration also opened the generated DOCX in Writer and
saved a verification copy successfully. This proves basic WPS open/save
compatibility, not pixel-level fidelity or a broad WPS version matrix.

P3-116 implemented the read-only `html-roundtrip-plan` prototype and P3-117
adds stable DOCX bookmarks plus an identity sidecar. See
`P3_HTML_CONTROLLED_ROUNDTRIP_SCHEMA.md`. P3-118 adds controlled DOCX-to-owned
HTML export while preserving identities; P3-119 is bounded batch conversion.
