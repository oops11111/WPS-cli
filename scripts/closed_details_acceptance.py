"""Offline acceptance of the fixed five-case closed-details evidence set."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wps_ai_agent_cli import html_styles  # noqa: E402
from wps_ai_agent_cli.fidelity import fidelity_check  # noqa: E402


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def positions(path):
    import pdfplumber

    records = {}
    with pdfplumber.open(path) as document:
        for index, page in enumerate(document.pages):
            for word in page.extract_words():
                for label, token in (
                    ("summary", "计算口径"),
                    ("mail", "finance@example.com"),
                    ("phone", "021-0000-0000"),
                    ("unsafe_label", "不安全链接"),
                    ("hidden_body", "收入按权责发生制确认"),
                ):
                    if token in word["text"]:
                        records[label] = {
                            "page": index + 1,
                            "text": word["text"],
                            "top": word["top"],
                            "x": word["x0"],
                            "page_width": page.width,
                            "top_at_800px": word["top"] * 800 / page.width,
                            "x_at_800px": word["x0"] * 800 / page.width,
                        }
    return records


def assess(out):
    import numpy as np
    from docx import Document
    from PIL import Image

    report = {
        "base": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "product_files_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in ("src/wps_ai_agent_cli/html_editable.py", "src/wps_ai_agent_cli/fidelity.py")
        },
        "cases": {},
    }
    for name in ("report", "contract", "newsletter", "manual", "pdfsource"):
        folder = out / f"A-{name}-docx"
        old = ROOT / "artifacts/html-docx-wps-matrix-20261121" / f"A-{name}-docx"
        if name == "contract":
            old = ROOT / "artifacts/contract-merge-borders-20261121/contract"
        if name == "manual":
            old = ROOT / "artifacts/manual-rule-spacing-20261121/manual"
        current, baseline = read(folder / "result.json"), read(old / "result.json")
        for filename, expected in current["hashes"].items():
            path = folder / ("input/" + filename if filename.endswith(".html") else filename)
            assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, path
        for item in read(folder / "input-manifest.json"):
            if item["exists"]:
                archived = folder / "input" / item["reference"]
                assert hashlib.sha256(archived.read_bytes()).hexdigest() == item["sha256"], archived
        before, after = baseline["layout"], current["layout"]
        gates = {
            "execution": current["execution_ok"],
            "aggregate": after["score"] >= before["score"],
            "pages": after["pages"] == before["pages"],
            "per_page": len(after["page_scores"]) == len(before["page_scores"])
            and all(a >= b for a, b in zip(after["page_scores"], before["page_scores"], strict=True)),
            "semantics": all(current["semantic"]["verdict"].values()),
        }
        report["cases"][name] = {"before": before, "after": after, "gates": gates, "hashes_verified": True}
    old = ROOT / "artifacts/html-docx-wps-matrix-20261121/A-report-docx"
    new = out / "A-report-docx"
    visible = {
        "browser": positions(old / "browser.pdf"),
        "before": positions(old / "wps.pdf"),
        "after": positions(new / "wps.pdf"),
    }
    paragraphs = Document(new / "converted.docx").paragraphs
    body = "收入按权责发生制确认。"
    visible["body_xml_count"] = "".join(p.text for p in paragraphs).count(body)
    visible["summary_body_runs"] = [
        {"text": r.text, "hidden": r.font.hidden} for p in paragraphs if "计算口径" in p.text for r in p.runs
    ]
    gates = {
        "body_retained_once": visible["body_xml_count"] == 1,
        "body_hidden_xml": any(r["text"] == body and r["hidden"] is True for r in visible["summary_body_runs"]),
        "body_not_visible": "hidden_body" not in visible["after"],
        "summary_unchanged": all(
            abs(visible["after"]["summary"][k] - visible["before"]["summary"][k]) <= 0.05 for k in ("x", "top")
        ),
        "page1_pixels": np.array_equal(
            np.asarray(Image.open(old / "wps-page-001.png")), np.asarray(Image.open(new / "wps-page-001.png"))
        ),
    }
    gates["following_positions"] = all(
        label in visible["after"]
        and visible["after"][label]["page"] == visible["browser"][label]["page"]
        and all(
            abs(visible["after"][label][axis] - visible["browser"][label][axis])
            <= abs(visible["before"][label][axis] - visible["browser"][label][axis])
            for axis in ("top", "x")
        )
        for label in ("mail", "phone", "unsafe_label")
    )
    # Reuse the exact measured source styles, avoiding cascade-vs-browser noise.
    styled = html_styles.load(ROOT / "fixtures/html_complex/report.html", use_browser=False)
    raw = read(old / "browser-styles.json")
    records = {e["attrs"].get("data-wps-i"): e for e in raw["elements"]}
    for node in html_styles._walk(styled.root):
        if record := records.get(node.attrs.get("data-wps-i")):
            styled.styles[id(node)] = record["style"]
            if record.get("box"):
                styled.boxes[id(node)] = record["box"]
    styled.mode, styled.warnings = "browser", raw["warnings"]
    with patch.object(html_styles, "load", return_value=styled):
        checked = fidelity_check(ROOT / "fixtures/html_complex/report.html", old / "converted.docx", use_browser=False)
    assert checked[0], checked
    visible["old_docx_new_scorer"] = checked[1]["aspects"]["formatting"]
    gates["old_expanded_rejected"] = checked[1]["aspects"]["formatting"]["score"] < 1 and any(
        "hidden True -> False" in p for p in checked[1]["aspects"]["formatting"]["problems"]
    )
    report["report_visible_state"], report["report_gates"] = visible, gates
    report["passed"] = all(gates.values()) and all(all(c["gates"].values()) for c in report["cases"].values())
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="existing completed matrix directory")
    args = parser.parse_args()
    result = assess(args.out)
    (args.out / "acceptance.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "report_gates": result["report_gates"]}, indent=2))


if __name__ == "__main__":
    main()
