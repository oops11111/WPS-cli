"""Summarize a fresh three-deck full-canvas run without relaxing failed gates.

Run after html_pptx_full_canvas_audit.py. This reads its single-run output and
the already accepted Stage2 evidence; it does not launch WPS or reconvert files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "8df12982bb5984fba18dbee92ece17bfd8166f9d"
STAGE2 = ROOT / "artifacts/html-pptx-stage2-20261122/manifest.json"
STAGE2_PROBE = ROOT / "artifacts/html-pptx-stage2-20261122/wps_probe.json"
STAGE2_PACKAGES = ROOT / "artifacts/html-pptx-full-canvas-verified-20261122"
CASE_NAMES = {"A-launch-pptx": "launch", "A-training-pptx": "training", "A-quarterly-pptx": "quarterly"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def changed_members(prior: Path, current: Path) -> list[str]:
    with zipfile.ZipFile(prior) as a, zipfile.ZipFile(current) as b:
        left = set(a.namelist())
        right = set(b.namelist())
        return sorted(left ^ right | {name for name in left & right if a.read(name) != b.read(name)})


def summarize(audit_path: Path) -> dict:
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    stage2 = json.loads(STAGE2.read_text(encoding="utf-8"))
    probe = json.loads(STAGE2_PROBE.read_text(encoding="utf-8"))
    cases = {}
    for case, short in CASE_NAMES.items():
        entry = audit["cases"][case]
        current = audit_path.parent / case / "candidate.pptx"
        previous = STAGE2_PACKAGES / case / "candidate.pptx"
        if sha(current) != entry["pptx_sha256"]:
            raise ValueError(f"{case}: package hash differs from fresh audit manifest")
        differences = changed_members(previous, current)
        layout = entry["fidelity"]["aspects"]["layout"]
        aspects = entry["fidelity"]["aspects"]
        semantic = {
            name: aspects[name].get("score") for name in ("text", "structure", "formatting", "animations", "data")
        }
        pages = layout["page_scores"]
        if not pages or any(score < 0.90 for score in pages):
            raise ValueError(f"{case}: static page score below 0.90")
        if any(score != 1.0 for score in semantic.values() if score is not None):
            raise ValueError(f"{case}: semantic aspect below 1.0")
        if differences:
            raise ValueError(f"{case}: PPTX members differ from Stage2 COM-tested package: {differences}")
        if entry["source_sha256"] != stage2["cases"][short]["source_sha256"]:
            raise ValueError(f"{case}: source changed since Stage2")
        cases[short] = {
            "source_sha256": entry["source_sha256"],
            "fresh_pptx_sha256": entry["pptx_sha256"],
            "stage2_com_tested_pptx_sha256": stage2["cases"][short]["pptx_sha256"],
            "changed_uncompressed_pptx_members_vs_stage2": differences,
            "aggregate_full_canvas_ssim": layout["score"],
            "page_full_canvas_ssim": pages,
            "legacy_page_ssim": layout["legacy_page_scores"],
            "semantic_scores": semantic,
            "mapped_objects": entry["conversion"]["mapped_objects"],
            "warnings": entry["conversion"]["warnings"],
        }
    launch_source = ROOT / "fixtures/html_complex/launch.html"
    launch_html = launch_source.read_text(encoding="utf-8")
    media = {
        "source_video_controls": '<video src="teaser.mp4" controls>' in launch_html,
        "source_teaser_exists": (launch_source.parent / "teaser.mp4").is_file(),
        "target_mapped_media": cases["launch"]["mapped_objects"]["media"],
        "visible_object_gate": "failed",
        "page5_pair": "A-launch-pptx/pages/page-005-0.948.png",
    }
    if not media["source_video_controls"] or media["source_teaser_exists"] or media["target_mapped_media"]:
        raise ValueError("launch video evidence changed; revisit the visible-object conclusion")
    return {
        "executed_main_base": BASE,
        "fresh_audit_manifest_sha256": sha(audit_path),
        "stage2_manifest_sha256": sha(STAGE2),
        "stage2_probe_sha256": sha(STAGE2_PROBE),
        "renderer_sha256": {name: item["sha256"] for name, item in audit["renderer_sha256"].items()},
        "cases": cases,
        "media": media,
        "animation_ooxml": "13/13 matched in Stage2; current PPTX uncompressed members identical",
        "wps_com": probe["fallback"]["rot_and_com"],
        "wps_clean_visual_playback": "unverified",
        "overall": "best-effort; complete high-fidelity acceptance failed",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.audit.resolve())
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
