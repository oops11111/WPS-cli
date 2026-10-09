# P3-114 HTML Visual-First Conversion

## Delivered

- Added `html-render` for local HTML/HTM to PDF or PNG through Playwright and Microsoft Edge.
- Added MCP tool `wps_agent_html_render` with explicit artifact-write, resource, timeout, and script-execution policy.
- Added optional task status tracking. Existing output paths are rejected; source HTML is never modified.
- Packaged the JavaScript runner as Python package data.

## Boundaries

- HTML input: 10 MiB maximum. Local resources must resolve within the HTML directory after symlink resolution; each is at most 20 MiB and aggregate resources at most 100 MiB.
- HTTP(S) and other non-file schemes are blocked. JavaScript is disabled unless explicitly enabled.
- Timeout is bounded to 1-120 seconds and rendered document height to 20,000 pixels.
- PDF supports A4, Letter, Legal, and Tabloid page sizes. PNG uses the requested viewport and full-page capture.
- Browser, Playwright, and Node versions affect font rasterization and CSS support. This mode creates a visual artifact, not editable WPS content.

## Verification

- Offline guard tests confirm format/extension validation and no-overwrite behavior.
- Real local Edge integration generated both PDF and PNG, checked metadata and signatures, verified nonblank image pixels, and included an external URL that was blocked.
- Full test suite: 200 passed, 13 skipped by opt-in environment gates.
- At P3-114 completion, MCP catalog guard: 69 tools, 16 mutating, 17 WPS-required, 53 read-only; zero catalog drift. P3-115 subsequently adds one conversion tool.
- Browser integration can be repeated with `WPS_AGENT_RUN_BROWSER_INTEGRATION=1`, `WPS_AGENT_NODE`, `WPS_AGENT_EDGE`, and `NODE_PATH` configured.

P3-115 follows this milestone; see `P3_HTML_EDITABLE_FIRST.md`. P3-116 and P3-117 add controlled identity planning and DOCX persistence; batch conversion remains later.
