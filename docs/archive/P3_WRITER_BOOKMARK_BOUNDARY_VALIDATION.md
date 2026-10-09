# Writer Bookmark Boundary Validation

P3-170 refuses bookmark text ranges in paragraphs containing tracked insertions, deletions, moves, or text boxes. Endpoints hidden inside excluded containers no longer receive a fabricated paragraph-end offset. The same preflight keeps `writer-fill-bookmark` limited to a supported direct body paragraph. Offline tests cover deleted/moved endpoints, insertion before a bookmark, a text box within a bookmark, duplicate names, and mixed hyperlink/tab/break/hyphen text.

The controlled mixed-run fixture is `fixtures/phase3/writer_mixed_run_wps_fixture.docx`, built once by `scripts/build_writer_mixed_run_fixture.py` (which refuses to overwrite it). `MixedMark` spans ordinary text, hyperlink text, and a tab inside a table cell. Offline extraction, CLI, MCP, and read-only WPS `Range.Text` returned `AB\tC`. WPS left the fixture SHA-256 unchanged: `0CF410E40E6B1AD88A9AA7471CCA3CBF03BF5125A8C045D9BBB281EF1BC34B6C`.

The opt-in WPS test is `WPS_AGENT_RUN_INTEGRATION=1 python -m unittest tests.test_writer_mixed_run_fixture`. After the parser change, the original structure parity passed 6/6 and nested parity passed 3/3 in real WPS. The default suite passed 319 tests (24 skipped). This validates the controlled cases only; it does not establish cross-version revision rendering or general layout fidelity.
