# Product Requirements Evidence Audit

Date: 2026-10-07. Source: user-supplied WPS_AI_Agent_CLI_PRD_v1.1.docx,
sections 4, 5, 7, 8 and 9, read from its DOCX XML. This is a capability gap
audit, not a claim that all PRD acceptance criteria are met.

| PRD requirement | Current evidence | Remaining work |
| --- | --- | --- |
| Stable document IDs, backup, recovery | sessions.py records content and file identity; source/backup checks surround COM, P3-175 serializes cooperating Agent mutations, P3-176 atomically persists shared registries, P3-177 records post-save identity for replay repair, and P3-178 blocks automatic reapplication when a derived backup exists but the unrecorded source changed; real Writer/Spreadsheet WPS writes passed | Registrations are not live COM sessions; the locks do not exclude external editors, and a changed source without a main operation record is deliberately ambiguous rather than proven successful |
| Writer structure and targeted editing | `writer-structure` reads bounded heading/style/bookmark metadata and uniquely paired same-paragraph body/table/header/footer bookmark text; current WPS parity passed 7/7 and 4/4 on controlled fixtures; P3-173 fixed a false fill readback failure on a second valid direct-body marker layout | `writer-fill-bookmark` remains direct-body only; cross-version matrix and visual fidelity remain unverified |
| Spreadsheet read/write and real calculation | bounded range/formula operations, format and WPS display inspection; worksheet inventory covers layout, visibility, protection, names, calculations and bounded validation/formatting metadata; worksheet mutations have WPS-backed transaction tests; P3-113 verifies 1904 dates and host-locale display | Broader WPS version/locale matrix and macro-enabled WPS round-trip/data preservation still need distinct verification |
| Presentation page/object targeting | presentation_text.py resolves logical slide order; snapshots include blank/image-only slides, grouped text and tables; replacement traverses nested shapes/cells, preserves matched-range formatting and verifies per-object text | Presentation mutation/idempotency checks are implemented; spreadsheet write-range area limits remain, see P3-088 |
| Conversion matrix and HTML modes | `html-render`, `html-editable`, controlled import/verify/export; real WPS rich-media round-trip retains stable image/link identities | Broader WPS version fidelity validation remains |
| Batch conversion with per-file results | `html-batch-convert` and `wps_agent_html_batch_convert` convert up to 100 HTML files to PDF/PNG/DOCX with isolated failures and SHA-256 provenance; `batch-template-report` and `wps_agent_batch_template_report` render validated manifests through local Markdown or DOCX templates | Broader cross-version and multipage visual fidelity evidence remains |
| Tasks, cancellation, progress | `html-batch-convert --task-id` updates per-file progress, polls shared task status between files, and retains a partial manifest on cancellation | Live progress streaming and process recovery remain |
| Structured CLI/MCP contract | cli.py, mcp_adapter.py, mcp_server.py; unit and smoke tests | Real desktop-client integration and broad Agent user-story evaluation need distinct evidence |
| Content, calculation and format verification | validators.py, snapshots.py, regression manifest | Current structural checks do not establish visual fidelity or cross-version success thresholds |

Historical Phase 0/1/2 completion refers to the implemented local milestones;
it must not be interpreted as full PRD delivery. The 123 passing unit tests on
the audit date proved their assertions, not all product requirements. Current
test totals and WPS integration evidence are maintained in
`PHASE3_RELEASE_READINESS_REFRESH.md`.

## Scheduled Work

1. P3-159 complete: safe baseline and artifact-dependent release gates are separated. The local safe run passed 15/15 and release run passed 3/3 after package refresh; old failed artifacts were retained.
2. P3-160 complete: `local-release-gates` passed the five-step local package/safe/refresh/readiness/release sequence and saved both regression artifacts.
3. P3-161 complete: bounded, read-only Writer heading/style/bookmark inspection is available via CLI/MCP. It is offline OOXML evidence, not a WPS layout claim.
4. P3-162 complete: selected-section pagination and exact bookmark lookup now report source hashes and ambiguity.
5. P3-163 complete: bounded bookmark text inspection distinguishes available, empty, missing, ambiguous, unsupported scope, and invalid range without claiming WPS validation.
6. P3-164 complete: controlled local WPS read-only observations agreed on paragraph text/order, heading levels, and bookmark text; localized style display names differed from OOXML style IDs as expected.
7. P3-165 complete: opt-in Writer parity CLI/MCP passed 6/6 checks on the controlled local fixture and retained a JSON report with source hash.
8. P3-166 complete: local handoff includes the latest Writer parity JSON; readiness checks report status, fixture/script hashes, and package byte equality without launching WPS.
9. P3-167 complete: a separate controlled fixture verified table and header/footer bookmark presence and text through read-only WPS; this was before nested offline text reads were implemented.
10. P3-168 complete: bounded same-paragraph nested bookmark reads agree with the controlled WPS fixture through CLI/MCP; cross-container and ambiguous reads remain unsupported, and Writer mutation scope stays body-only.
11. P3-169 complete: an opt-in nested-scope Writer parity command retained a passed 3/3 local WPS JSON report; local handoff readiness verifies its source/script hashes and packaged bytes.
12. P3-170 complete: revision/text-box paragraphs are rejected for bookmark reads and fills; a controlled mixed-run table bookmark matched read-only WPS with unchanged SHA-256.
13. P3-171 complete: both Writer parity reports now bind four implementation-file hashes; local readiness marks reports stale when code changes, even if file mtimes are preserved.
14. P3-172 complete: registrations bind SHA-256 and file identity; mutation backup preflight rejects stale or legacy-unverified records, detects copy-time changes, and refreshes the identity after successful local operations. See `P3_DOCUMENT_IDENTITY_AUDIT.md` for the remaining race.
15. P3-173 complete: the observed bookmark fill had correctly updated text, but WPS appended one empty paragraph after a terminal table; narrowly accepting that normalization preserved neighboring text/table checks, backup, and replay.
16. P3-174 complete: a shared guard rechecks source identity and backup bytes just before COM, then checks post-COM source identity after readback; controlled Writer and Spreadsheet replacements are rejected without starting COM.
17. P3-175 complete: a workspace/document-ID lock spans cooperating Agent mutation and registration calls; cross-process contention returns `DOCUMENT_BUSY`, and real Writer/Spreadsheet WPS writes passed under the lock.
18. P3-176 complete: shared documents/operations registry read-modify-write transactions now use bounded cross-process locks and same-directory atomic replacement. Four processes retained 48 distinct records in each registry; concurrent reads saw complete JSON; failed replacement preserved the old state. Real WPS Writer/Spreadsheet checks passed.
19. P3-177 complete: committed file identity allows safe replay repair when registration refresh failed; a changed file or failed identity capture produces explicit non-replayable evidence. Windows transient lock initialization and read sharing races found by repeated concurrency tests were fixed.
20. P3-178 complete: a derived backup with unchanged source allows retry; a changed or unreadable source without a main operation record returns `UNRECORDED_MUTATION_AMBIGUOUS` before target lookup, preventing automatic reapplication. This is not evidence that WPS saved successfully.
21. P3-179 complete: `mutation-request-inspect` and its MCP mapping report main operation, derived backup, and current file identity without writing; recorded-but-stale, changed, retryable, ambiguous, and no-evidence states are distinguished.
22. P3-180 complete: all eight mutation inspection states include non-destructive recovery guidance in CLI/MCP results, and the local validation runbook begins with read-only request evidence inspection; ambiguous states explicitly prohibit automatic overwrite or retry.
23. P3-181 complete: real WPS Writer/Spreadsheet saves on disposable files were interrupted before main ledger commit; retained current/backup artifacts and hashes show ambiguity, CLI/MCP agreed, and same-ID retry did not alter either saved source.
24. P3-182 complete: a bounded, read-only verifier checks both retained manifests and file hashes, rejects missing/malformed/redirected evidence, and reports the two-component result through local handoff; the current workspace passed.
25. P3-183 complete: package creation now rejects incomplete or changed recovery evidence before rebuilding; six valid generated files are included and compared byte-for-byte in package readiness. The current local package passed 6/6 comparisons.
26. P3-184 next: extract the portable package into a clean disposable workspace and verify recovered evidence independently of the source checkout.
27. Later: broaden visual/semantic fidelity and WPS version coverage while preserving independent failures and artifact provenance.

These milestones are actionable entirely in the local workspace. Offline parsing fixes
must remain labelled as file-library behavior; WPS end-to-end validation is a
separate gate, not implied by offline tests.
