"""Measure only the original manual after the hr-following-paragraph spacing repair."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from direct_container_evidence import write  # noqa: E402
from html_docx_wps_matrix import run_case  # noqa: E402

from wps_ai_agent_cli.fidelity import ssim  # noqa: E402

LOWER_REGION = (40, 495, 760, 625)  # fixed from stage-4 source before measuring the repair


def paragraph_spacing(path):
    from docx import Document
    from docx.oxml.ns import qn

    rows = []
    for paragraph in Document(path).paragraphs:
        props = paragraph._p.pPr
        rows.append(
            {
                "text": paragraph.text,
                "style": paragraph.style.name,
                "is_rule": props is not None and props.find(qn("w:pBdr")) is not None and not paragraph.text,
                "spacing": dict(props.spacing.attrib) if props is not None and props.spacing is not None else None,
            }
        )
    return rows


def text_positions(path):
    import pdfplumber

    with pdfplumber.open(path) as document:
        page = document.pages[0]
        records = {}
        for label, char, heading in (("third_heading", "3", True), ("question", "问", False), ("answer", "答", False)):
            matches = [c for c in page.chars if c["text"] == char and (c["size"] > 14 if heading else c["size"] < 14)]
            c = matches[-1] if heading else matches[0]
            records[label] = {
                "top_pt": c["top"],
                "top_at_800px": c["top"] * 800 / page.width,
                "font_size_pt": c["size"],
            }
        return records


def region_pair(folder):
    import numpy as np
    from PIL import Image

    a = Image.open(folder / "browser-page-001.png").convert("RGB").crop(LOWER_REGION)
    b = Image.open(folder / "wps-page-001.png").convert("RGB").crop(LOWER_REGION)
    pair = Image.new("RGB", (a.width * 2 + 8, a.height), "gray")
    pair.paste(a, (0, 0))
    pair.paste(b, (a.width + 8, 0))
    return pair, round(ssim(np.asarray(a.convert("L")), np.asarray(b.convert("L"))), 4)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    previous = ROOT / "artifacts/html-docx-wps-matrix-20261121/A-manual-docx"
    baseline = json.loads((ROOT / "config/fidelity_baselines.json").read_text(encoding="utf-8"))["cases"]
    current = run_case("A-manual-docx", "fixtures/fidelity/manual.html", out / "manual", baseline)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10)
    diff = subprocess.run(["git", "diff", "--", "src"], cwd=ROOT, capture_output=True, timeout=10)
    report = {
        "git_head": head.stdout.strip(),
        "product_diff_sha256": hashlib.sha256(diff.stdout).hexdigest(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "region": LOWER_REGION,
        "baseline": json.loads((previous / "result.json").read_text(encoding="utf-8")),
        "current": current,
    }
    write(out / "before-spacing.json", paragraph_spacing(previous / "converted.docx"))
    if current["execution_ok"]:
        import numpy as np
        from PIL import Image

        write(out / "after-spacing.json", paragraph_spacing(out / "manual/converted.docx"))
        report["positions"] = {
            "browser": text_positions(previous / "browser.pdf"),
            "before": text_positions(previous / "wps.pdf"),
            "after": text_positions(out / "manual/wps.pdf"),
        }
        for label, folder in (("before", previous), ("after", out / "manual")):
            pair, score = region_pair(folder)
            pair.save(out / (label + "-lower-region.png"))
            report[label + "_region_ssim"] = score
        old = np.asarray(Image.open(previous / "wps-page-001.png"))
        new = np.asarray(Image.open(out / "manual/wps-page-001.png"))
        report["earlier_page_equal"] = np.array_equal(old[: LOWER_REGION[1]], new[: LOWER_REGION[1]])
        positions = report["positions"]
        report["gates"] = {
            "whole_improved": current["layout"]["score"] > 0.8872,
            "region_improved": report["after_region_ssim"] > report["before_region_ssim"],
            "positions_improved": all(
                abs(positions["after"][key]["top_at_800px"] - positions["browser"][key]["top_at_800px"])
                < abs(positions["before"][key]["top_at_800px"] - positions["browser"][key]["top_at_800px"])
                for key in positions["browser"]
            ),
            "earlier_page_unchanged": bool(report["earlier_page_equal"]),
            "semantics": all(
                current["semantic"]["aspects"][key]["score"] == 1.0
                for key in ("text", "structure", "formatting", "data")
            ),
            "pages": current["layout"]["pages"] == {"source": 1, "target": 1},
        }
    write(out / "comparison.json", report)
    print(
        json.dumps(
            {
                "execution_ok": current["execution_ok"],
                "layout": current.get("layout"),
                "before_region_ssim": report.get("before_region_ssim"),
                "after_region_ssim": report.get("after_region_ssim"),
                "gates": report.get("gates"),
                "positions": report.get("positions"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
