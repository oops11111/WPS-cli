"""Offline original-five-case acceptance for plain pre whitespace preservation."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

from closed_details_acceptance import positions, read

ROOT = Path(__file__).resolve().parents[1]
BEFORE = ROOT / "artifacts/closed-details-mapping-20261121"


def sql_positions(path):
    import pdfplumber

    with pdfplumber.open(path) as document:
        return {
            w["text"]: {"top": w["top"], "x": w["x0"]}
            for page in document.pages
            for w in page.extract_words()
            if w["text"] in {"SELECT", "FROM", "WHERE", "GROUP"}
        }


def assess(out):
    import numpy as np
    from docx import Document
    from PIL import Image

    report = {
        "base": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "product_sha256": hashlib.sha256((ROOT / "src/wps_ai_agent_cli/html_editable.py").read_bytes()).hexdigest(),
        "cases": {},
    }
    for name in ("report", "contract", "newsletter", "manual", "pdfsource"):
        folder = out / f"A-{name}-docx"
        before, current = read(BEFORE / f"A-{name}-docx/result.json"), read(folder / "result.json")
        for filename, expected in current["hashes"].items():
            path = folder / ("input/" + filename if filename.endswith(".html") else filename)
            assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, path
        for item in read(folder / "input-manifest.json"):
            if item["exists"]:
                assert hashlib.sha256((folder / "input" / item["reference"]).read_bytes()).hexdigest() == item["sha256"]
        a, b = current["layout"], before["layout"]
        gates = {
            "execution": current["execution_ok"],
            "aggregate": a["score"] >= b["score"],
            "per_page": len(a["page_scores"]) == len(b["page_scores"])
            and all(x >= y for x, y in zip(a["page_scores"], b["page_scores"], strict=True)),
            "pages": a["pages"] == b["pages"],
            "semantics": all(current["semantic"]["verdict"].values()),
        }
        report["cases"][name] = {"before": b, "after": a, "gates": gates, "hashes_verified": True}
    old, new = BEFORE / "A-report-docx", out / "A-report-docx"
    original = (ROOT / "fixtures/html_complex/report.html").read_bytes().decode("utf-8")
    source_pre = re.search(r"<pre>(.*?)</pre>", original, re.S).group(1).replace("\r\n", "\n").replace("\r", "\n")
    expected = source_pre.removeprefix("\n")
    paragraphs = Document(new / "converted.docx").paragraphs
    pre = next(p for p in paragraphs if "SELECT" in p.text)
    data = {
        "source_pre": source_pre,
        "expected_pre": expected,
        "actual_pre": pre.text,
        "before_pre": next(p.text for p in Document(old / "converted.docx").paragraphs if "SELECT" in p.text),
        "br_count": len(pre._p.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}br")),
        "browser": positions(old / "browser.pdf"),
        "before": positions(old / "wps.pdf"),
        "after": positions(new / "wps.pdf"),
        "sql_before": sql_positions(old / "wps.pdf"),
        "sql_after": sql_positions(new / "wps.pdf"),
    }
    labels = ("summary", "mail", "phone", "unsafe_label")
    gates = {
        "pre_text": pre.text == expected,
        "pre_br": data["br_count"] == expected.count("\n"),
        "page1_pixels": np.array_equal(
            np.asarray(Image.open(old / "wps-page-001.png")), np.asarray(Image.open(new / "wps-page-001.png"))
        ),
        "page2_improved": report["cases"]["report"]["after"]["page_scores"][1]
        > report["cases"]["report"]["before"]["page_scores"][1],
        "aggregate_improved": report["cases"]["report"]["after"]["score"]
        > report["cases"]["report"]["before"]["score"],
        "vertical_errors_improved": all(
            abs(data["after"][k]["top"] - data["browser"][k]["top"])
            < abs(data["before"][k]["top"] - data["browser"][k]["top"])
            for k in labels
        ),
        "x_unchanged": all(abs(data["after"][k]["x"] - data["before"][k]["x"]) <= 0.05 for k in labels),
        "sql_unchanged": data["sql_after"].keys() == data["sql_before"].keys()
        and all(
            abs(data["sql_after"][k][axis] - data["sql_before"][k][axis]) <= 0.05
            for k in data["sql_before"]
            for axis in ("top", "x")
        ),
        "hidden_body_absent": "hidden_body" not in data["after"],
        "hidden_body_retained": "".join(p.text for p in paragraphs).count("收入按权责发生制确认。") == 1
        and any(r.text == "收入按权责发生制确认。" and r.font.hidden for p in paragraphs for r in p.runs),
    }
    report.update(
        {
            "report_data": data,
            "report_gates": gates,
            "passed": all(gates.values()) and all(all(c["gates"].values()) for c in report["cases"].values()),
        }
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = assess(args.out)
    (args.out / "acceptance.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "report_gates": result["report_gates"]}, indent=2))


if __name__ == "__main__":
    main()
