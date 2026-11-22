"""Build a disposable launch slide-5 character-range animation candidate.

The script changes only the animation target in a copy of the accepted PPTX.
It does not modify the HTML source or the converter.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "fixtures/html_complex/launch.html"
PACKAGE = ROOT / "artifacts/html-pptx-stage3-20261122/A-launch-pptx/candidate.pptx"
SLIDE = "ppt/slides/slide5.xml"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
SPAN = "全渠道开售"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utf16_length(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def make_candidate(out: Path) -> dict:
    generated = (
        "launch-char-range-candidate.pptx",
        "launch-char-range-end14-control.pptx",
        "candidate_manifest.json",
    )
    if any((out / name).exists() for name in generated):
        raise ValueError("Candidate output files already exist")
    out.mkdir(parents=True, exist_ok=True)
    html = SOURCE.read_text(encoding="utf-8")
    if '<p>10 月 24 日 <span class="fade">全渠道开售</span></p>' not in html:
        raise ValueError("Fixed source paragraph changed")
    with zipfile.ZipFile(PACKAGE) as original:
        slide = original.read(SLIDE)
        root = ET.fromstring(slide)
        text_shapes = []
        for shape in root.iter(f"{P}sp"):
            marker = shape.find(f"{P}nvSpPr/{P}cNvPr")
            if marker is None:
                continue
            runs = [node.text or "" for node in shape.iter(f"{A}t")]
            if SPAN in "".join(runs):
                text_shapes.append((marker.get("id"), runs))
        if len(text_shapes) != 1 or text_shapes[0][1] != ["10 月 24 日 ", SPAN]:
            raise ValueError(f"Target run segmentation changed or is ambiguous: {text_shapes}")
        spid, runs = text_shapes[0]
        prefix = runs[0]
        start = utf16_length(prefix)
        end = start + utf16_length(SPAN)
        if start != 10 or end != 15:
            raise ValueError("Fixed launch offset changed")
        old = f'<p:spTgt spid="{spid}"/>'.encode()
        new = (f'<p:spTgt spid="{spid}"><p:txEl><p:charRg st="{start}" end="{end}"/></p:txEl></p:spTgt>').encode()
        occurrences = slide.count(old)
        if occurrences != 2:
            raise ValueError(f"Expected two shape targets for visibility and fade, got {occurrences}")
        modified = slide.replace(old, new)
        candidate = out / "launch-char-range-candidate.pptx"
        with zipfile.ZipFile(candidate, "w") as result:
            for item in original.infolist():
                result.writestr(copy.copy(item), modified if item.filename == SLIDE else original.read(item.filename))
        control = out / "launch-char-range-end14-control.pptx"
        control_slide = modified.replace(f'end="{end}"'.encode(), f'end="{end - 1}"'.encode())
        if control_slide.count(f'<p:charRg st="{start}" end="{end - 1}"/>'.encode()) != 2:
            raise ValueError("Could not create the end-minus-one control")
        with zipfile.ZipFile(control, "w") as result:
            for item in original.infolist():
                result.writestr(
                    copy.copy(item), control_slide if item.filename == SLIDE else original.read(item.filename)
                )
        with zipfile.ZipFile(candidate) as result:
            changed = [name for name in original.namelist() if original.read(name) != result.read(name)]
            candidate_slide = result.read(SLIDE)
        if changed != [SLIDE] or candidate_slide.count(new) != 2:
            raise ValueError(f"Candidate changed unexpected members: {changed}")
        static_prefix_before = slide.split(b"<p:timing", 1)[0]
        static_prefix_after = candidate_slide.split(b"<p:timing", 1)[0]
        if static_prefix_before != static_prefix_after:
            raise ValueError("Static slide XML changed")
        report = {
            "base_commit": "0a65bb1f54f7ec3e788d9f4fb9af50a7800a4669",
            "source_sha256": sha(SOURCE.read_bytes()),
            "original_pptx_sha256": sha(PACKAGE.read_bytes()),
            "candidate_pptx_sha256": sha(candidate.read_bytes()),
            "end14_control_pptx_sha256": sha(control.read_bytes()),
            "target_shape_id": spid,
            "text_runs": runs,
            "target_text": SPAN,
            "range_units_hypothesis": "UTF-16 code units, start inclusive, end exclusive; WPS behavior not yet proven",
            "char_range": {"st": start, "end": end},
            "modified_target_elements": occurrences,
            "changed_uncompressed_pptx_members": changed,
            "static_slide_prefix_sha256_before": sha(static_prefix_before),
            "static_slide_prefix_sha256_after": sha(static_prefix_after),
            "counterexamples": [
                "An end-minus-one OOXML control distinguishes whether WPS COM reports the raw end or a range length",
                "Non-BMP prefix such as 🚀 occupies one Python code point but two UTF-16 code units",
                "Repeated identical inline text needs DOM/run identity rather than substring search",
                "HTML whitespace collapse can change source offsets before PPTX serialization",
            ],
        }
        (out / "candidate_manifest.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(make_candidate(args.out.resolve()), ensure_ascii=False, indent=2))
