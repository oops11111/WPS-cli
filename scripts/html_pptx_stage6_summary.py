"""Summarize one exact-main Stage6 HTML-to-PPTX run and its remaining gates."""

from __future__ import annotations

import argparse
import json
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from html_pptx_stage3_summary import ROOT, sha, summarize

BASE = "e10b10a45f63b2f8d315c0c1ed90a2d81f11b2ba"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"


def build(audit_path: Path) -> dict:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if head != BASE:
        raise ValueError(f"expected exact main {BASE}, got {head}")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    result = summarize(audit_path)
    result["executed_main_base"] = head
    result["fresh_audit_manifest_sha256"] = sha(audit_path)
    result["stage3_summary_reused_for_package_comparison"] = True
    result["case_slide_counts"] = {}
    result["case_effect_counts"] = {}
    result["case_transition_counts"] = {}
    result["case_notes_counts"] = {}
    for case, short in (
        ("A-launch-pptx", "launch"),
        ("A-training-pptx", "training"),
        ("A-quarterly-pptx", "quarterly"),
    ):
        entry = audit["cases"][case]
        slides = entry["slides"]
        result["case_slide_counts"][short] = len(slides)
        result["case_effect_counts"][short] = sum(len(slide["effects"]) for slide in slides)
        result["case_transition_counts"][short] = sum(bool(slide["transition"]) for slide in slides)
        result["case_notes_counts"][short] = entry["conversion"]["mapped_objects"]["notes"]
    if sum(result["case_effect_counts"].values()) != 13:
        raise ValueError("source/OOXML effect count changed from Stage2 inventory")
    if sum(result["case_transition_counts"].values()) != 12:
        raise ValueError("transition count changed from Stage2 inventory")
    if sum(result["case_notes_counts"].values()) != 3:
        raise ValueError("notes count changed from Stage2 inventory")
    source = ROOT / "fixtures/html_complex/launch.html"
    with zipfile.ZipFile(audit_path.parent / "A-launch-pptx/candidate.pptx") as package:
        slide5 = ET.fromstring(package.read("ppt/slides/slide5.xml"))
    shape_targets = slide5.findall(f".//{P}spTgt")
    paragraph_ranges = slide5.findall(f".//{P}spTgt/{P}txEl/{P}pRg")
    character_ranges = slide5.findall(f".//{P}spTgt/{P}txEl/{P}charRg")
    warnings = audit["cases"]["A-launch-pptx"]["conversion"]["warnings"]
    inline_warning = any("part of a paragraph" in message and "whole paragraph" in message for message in warnings)
    result["inline_animation"] = {
        "source_span_fade": 'class="fade"' in source.read_text(encoding="utf-8"),
        "slide5_whole_shape_targets": len(shape_targets),
        "slide5_paragraph_range_targets": len(paragraph_ranges),
        "slide5_character_range_targets": len(character_ranges),
        "whole_paragraph_warning": inline_warning,
        "gate": "failed",
    }
    if (
        not result["inline_animation"]["source_span_fade"]
        or len(shape_targets) != 2
        or paragraph_ranges
        or character_ranges
        or not inline_warning
    ):
        raise ValueError("launch inline animation evidence changed")
    result["media"]["page5_pair"] = "A-launch-pptx/pages/page-005-0.948.png"
    result["wps_clean_visual_playback"] = "unverified: current read-only CopyFromScreen probe failed (invalid handle)"
    result["overall"] = "best-effort; complete high-fidelity acceptance failed"
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.audit.resolve())
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
