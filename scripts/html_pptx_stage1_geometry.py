"""Audit whether the fixed HTML slide screenshots and WPS pages share a canvas.

Run with ``PYTHONPATH=src``, Node Playwright on ``NODE_PATH`` and a runnable
Edge/Chromium browser. The committed stage 0 page pairs and PPTX packages are
the target inputs. This script does not change scoring or conversion behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops
from pptx import Presentation

from wps_ai_agent_cli.html_slides import collect_slides
from wps_ai_agent_cli.html_styles import load

ROOT = Path(__file__).resolve().parents[1]
CASES = (
    ("A-launch-pptx", "launch.html"),
    ("A-training-pptx", "training.html"),
    ("A-quarterly-pptx", "quarterly.html"),
)
PAIRS = ROOT / "artifacts/html-pptx-stage0-verified-20261122"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _content_size(image: Image.Image) -> tuple[int, int]:
    # Stage 0's _save_pairs pastes the page onto a grey (128) sheet. Its bounds
    # are the non-grey rectangle, including blank white areas of the page.
    difference = ImageChops.difference(image.convert("L"), Image.new("L", image.size, 128))
    box = difference.getbbox()
    if box is None or box[:2] != (0, 0):
        raise ValueError(f"Could not recover the rendered page bounds: {box}")
    return box[2:]


def run(out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    baseline = json.loads((PAIRS / "manifest.json").read_text(encoding="utf-8"))
    result = {
        "product_base": "309954b71103893aaf4eaf94baaa9a501003b769",
        "stage0_manifest_sha256": _sha(PAIRS / "manifest.json"),
        "scorer_path": "src/wps_ai_agent_cli/fidelity.py:_html_images/_pdf_pages/score_layout",
        "scorer_behavior": "target PDF page at width 800 is resized to each source section screenshot's size",
        "cases": {},
    }
    for case, source_name in CASES:
        folder = PAIRS / case
        source = folder / source_name
        target = folder / "candidate.pptx"
        entry = baseline["cases"][case]
        if _sha(source) != entry["source_sha256"] or _sha(target) != entry["pptx_sha256"]:
            raise ValueError(f"Stage 0 source or PPTX hash changed: {case}")
        styled = load(source, screenshots_dir=out / "source-shots" / case, viewport=(1280, 720))
        if styled.mode != "browser":
            raise RuntimeError(f"Browser source geometry unavailable: {case}: {styled.warnings}")
        source_slides = collect_slides(styled.root)
        pptx = Presentation(target)
        if len(source_slides) != len(pptx.slides) or len(source_slides) != len(styled.section_screenshots):
            raise ValueError(f"Slide count mismatch: {case}")
        slides = []
        for index, (slide, screenshot) in enumerate(zip(source_slides, styled.section_screenshots, strict=True), 1):
            source_image = Image.open(screenshot)
            pair_path = next((folder / "pages").glob(f"page-{index:03d}-*.png"))
            pair = Image.open(pair_path).convert("L")
            source_width = source_image.width
            target_width = pair.width - source_width - 8
            if target_width <= 0:
                raise ValueError(f"Invalid stage 0 page pair width: {pair_path}")
            target_image = pair.crop((source_width + 8, 0, pair.width, pair.height))
            target_size = _content_size(target_image)
            section = styled.box(slide.section)
            slides.append(
                {
                    "slide": index,
                    "source_section_css_px": [section["width"], section["height"]],
                    "source_screenshot_px": list(source_image.size),
                    "target_wps_page_px": list(target_size),
                    "scorer_target_resize_px": list(source_image.size),
                    "target_vertical_scale": round(source_image.height / target_size[1], 4),
                    "stage0_pair": str(pair_path.relative_to(ROOT)).replace("\\", "/"),
                    "stage0_pair_sha256": _sha(pair_path),
                    "stage0_ssim": entry["fidelity"]["report"]["aspects"]["layout"]["page_scores"][index - 1],
                }
            )
        result["cases"][case] = {
            "source_sha256": _sha(source),
            "pptx_sha256": _sha(target),
            "pptx_canvas_emu": [pptx.slide_width, pptx.slide_height],
            "slides": slides,
        }
    (out / "geometry.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    result = run(parser.parse_args().out.resolve())
    for case, entry in result["cases"].items():
        print(case, [(slide["source_screenshot_px"], slide["target_wps_page_px"]) for slide in entry["slides"]])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
