# HTML to PPTX stage 2: OOXML matched, playback unverified

Base: `main` `5279bd35a625d190895d9484057047ebe7e30cfe`. This stage used only the three fixed source files and the exact PPTX packages from the accepted stage 1A manifest. It made no converter, fixture, media, threshold or static-layout change.

## Source to package audit

Run `PYTHONPATH=src python scripts/html_pptx_stage2_inventory.py --out artifacts/html-pptx-stage2-20261122/manifest.json` with the project's Python dependencies. The [machine-readable inventory](../artifacts/html-pptx-stage2-20261122/manifest.json) contains source and package SHA-256 values, each source effect, matched OOXML shape/paragraph, preset class/subtype, node type, order, delay, behavior duration, transition and note text. The comparison fails on an unrecognized preset, ambiguous/missing target, changed text, trigger, order, delay, duration, transition or note. All 13 effects across 12 slides match the package representation, including the training click effect and following delayed effect; all 12 transitions and 3 notes are present.

The match proves package structure, not presentation behavior. CSS `span.fade` on launch slide 5 is represented by a whole paragraph effect, so its target scope is broader than the source inline span. The inventory exposes this approximation rather than claiming exact inline animation. Hover effects are unsupported and the absent `teaser.mp4` remains the Stage 1B visible-object failure. The retained PPTX packages are not fresh WPS playback evidence. Stage 1A's renderer and package hashes remain in its manifest; this stage did not rerender slides.

## WPS device gate: STOP

The new [WPS probe record](../artifacts/html-pptx-stage2-20261122/wps_probe.json) shows the installed `wpp.exe` file version 12.8.2.18913. `@oai/sky.list_apps()` returned no running WPS Presentation window. A subsequent `sky.launch_app` call with that executable never returned for about 1409 seconds and was interrupted. A later `Get-Process wpp` check returned `NO_WPP_PROCESS`. No deck was opened, COM was not attempted, and no fresh slideshow frame was captured. This is evidence that the attempted UI path did not yield an observable session, not proof that WPS rejects the PPTX animation syntax. The historical `scripts/windows_check/results/20261022T150940Z-c149caf-fidelity/playback.json` does not satisfy the new device gate.

Therefore WPS acceptance of timing properties, actual shape motion/display, trigger sequence and transitions remain **unverified**. Stage 2 is **STOP**, not animation high-fidelity acceptance. A later device run must open disposable copies of all three exact packages, record COM acceptance separately from timestamped screen observations, and cover entrance, click/after, emphasis, exit, direction and transitions. The final project gate still fails independently on the missing visible video control.

## Verification

Targeted `unittest` run: 9 passed (the new package audit and existing HTML slide tests). The first direct run hit the managed Windows temp-directory ACL (`PermissionError` inside `AppData\\Local\\Temp`); rerunning with the existing workspace-local `_writable_mkdtemp` helper passed. Ruff check and format check apply to the new script and test. CI on this PR remains a separate gate for the primary agent; it cannot replace the missing WPS device evidence.
