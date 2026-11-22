"""Recheck the three fixed HTML decks with full-slide and legacy layout scores.

Run on Windows with Edge, WPS, Node Playwright and Python test dependencies.
The output directory must be empty so each manifest describes one fresh run.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from html_pptx_stage0_audit import CASES, LOCAL_ASSETS, ROOT, _sha, _slides, _writable_mkdtemp

from wps_ai_agent_cli.convert import convert
from wps_ai_agent_cli.fidelity import fidelity_check
from wps_ai_agent_cli.html_styles import browser_runtime

PRODUCT_BASE = "dd0d1eaa719f26c3b168507083340ca5645e282d"
STAGE0 = ROOT / "artifacts/html-pptx-stage0-verified-20261122"


def _renderer_hashes(wps: Path) -> dict[str, dict[str, str]]:
    node, browser = browser_runtime()
    if not node or not browser:
        raise RuntimeError("Node and Edge/Chromium are required for full-slide source rendering")
    playwright = subprocess.run(
        [node, "-p", "require.resolve('playwright')"], capture_output=True, text=True, check=False
    )
    if playwright.returncode:
        raise RuntimeError(f"Playwright is unavailable: {playwright.stderr.strip()}")
    paths = {
        "fidelity_py": ROOT / "src/wps_ai_agent_cli/fidelity.py",
        "html_styles_py": ROOT / "src/wps_ai_agent_cli/html_styles.py",
        "html_layout_playwright_cjs": ROOT / "src/wps_ai_agent_cli/html_layout_playwright.cjs",
        "node": Path(node),
        "playwright_entrypoint": Path(playwright.stdout.strip()),
        "edge": Path(browser),
        "wps_presentation": wps,
    }
    if any(not path.is_file() for path in paths.values()):
        raise FileNotFoundError(f"A renderer file is missing: {paths}")
    return {name: {"path": str(path), "sha256": _sha(path)} for name, path in paths.items()}


def _slide_xml_equal(first: Path, second: Path) -> bool:
    with zipfile.ZipFile(first) as a, zipfile.ZipFile(second) as b:
        names = [name for name in a.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml")]
        return bool(names) and all(a.read(name) == b.read(name) for name in names)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--wps-executable", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        parser.error("output directory must be empty for a single fresh run")
    out.mkdir(parents=True, exist_ok=True)
    tempfile.mkdtemp = _writable_mkdtemp  # managed Windows sandbox needs ordinary directory ACLs
    old = json.loads((STAGE0 / "manifest.json").read_text(encoding="utf-8"))
    manifest = {
        "product_base": PRODUCT_BASE,
        "stage0_manifest_sha256": _sha(STAGE0 / "manifest.json"),
        "python": sys.version.split()[0],
        "renderer_sha256": _renderer_hashes(args.wps_executable.resolve()),
        "cases": {},
    }
    for case, source, fidelity in CASES:
        folder = out / case
        folder.mkdir()
        shutil.copyfile(source, folder / source.name)
        for name in LOCAL_ASSETS.get(case, ()):
            shutil.copyfile(source.parent / name, folder / name)
        target = folder / "candidate.pptx"
        ok, data, errors = convert(folder / source.name, target, fidelity=fidelity)
        if not ok:
            raise RuntimeError(f"{case} conversion failed: {errors}")
        checked, report, check_errors = fidelity_check(
            folder / source.name, target, renderer="wps", images_dir=folder / "pages"
        )
        if not checked:
            raise RuntimeError(f"{case} fidelity check failed: {check_errors}")
        prior = old["cases"][case]
        if _sha(source) != prior["source_sha256"]:
            raise ValueError(f"{case} source changed since stage 0")
        old_pptx = STAGE0 / case / "candidate.pptx"
        slide_xml_equal = _slide_xml_equal(old_pptx, target)
        if not slide_xml_equal:
            raise ValueError(f"{case} slide OOXML changed despite no converter change")
        slides = _slides(target)
        if slides != prior["slides"]:
            raise ValueError(f"{case} animation/transition inventory changed")
        aspects = report["aspects"]
        for name in ("text", "structure", "formatting", "animations", "data"):
            aspect = aspects.get(name, {})
            if "score" in aspect and aspect["score"] != 1.0:
                raise ValueError(f"{case} {name} semantic score regressed: {aspect}")
        layout = aspects["layout"]
        if layout.get("status") != "measured" or layout.get("canvas_mode") != "browser-native-1280x720-slide-viewport":
            raise ValueError(f"{case} full-slide layout is unavailable: {layout}")
        prior_pages = prior["fidelity"]["report"]["aspects"]["layout"]["page_scores"]
        if len(layout["legacy_page_scores"]) != len(prior_pages) or any(
            abs(new - old) > 0.002 for new, old in zip(layout["legacy_page_scores"], prior_pages, strict=True)
        ):
            raise ValueError(f"{case} legacy page scores do not reproduce stage 0 within 0.002")
        entry = {
            "source": str(source.relative_to(ROOT)).replace("\\", "/"),
            "source_sha256": _sha(source),
            "pptx_sha256": _sha(target),
            "stage0_pptx_sha256": prior["pptx_sha256"],
            "slide_xml_equal_stage0": slide_xml_equal,
            "mode": fidelity,
            "conversion": data,
            "slides": slides,
            "fidelity": report,
        }
        entry["files_sha256"] = {
            str(path.relative_to(folder)).replace("\\", "/"): _sha(path)
            for path in sorted(folder.rglob("*"))
            if path.is_file()
        }
        manifest["cases"][case] = entry
        (out / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        print(case, "full=", layout["page_scores"], "legacy=", layout["legacy_page_scores"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
