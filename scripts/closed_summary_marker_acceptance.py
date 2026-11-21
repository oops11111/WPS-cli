"""Offline current-source marker and original-five no-regression evidence gates."""

import argparse
import hashlib
import json
from pathlib import Path

from closed_details_acceptance import positions, read

from wps_ai_agent_cli.docx_details_marker import is_managed_marker
from wps_ai_agent_cli.fidelity import read_model

ROOT = Path(__file__).resolve().parents[1]
BEFORE = ROOT / "artifacts/plain-pre-whitespace-20261121"


def triangle(path):
    import pdfplumber

    with pdfplumber.open(path) as document:
        page = next(p for p in document.pages if "计算口径" in p.extract_text())
        word = next(w for w in page.extract_words() if w["text"] == "计算口径")
        char = next(c for c in page.chars if c["text"] == "计")
        baseline = page.height - char["matrix"][5]
        vectors = [
            v
            for v in page.curves
            if v.get("fill")
            and not v.get("stroke")
            and 0 < word["x0"] - v["x0"] < 20
            and abs(v["bottom"] - baseline) <= 0.1
        ]
        return {
            "count": len(vectors),
            "baseline": baseline,
            "vectors": [{k: v[k] for k in ("x0", "x1", "top", "bottom", "pts")} for v in vectors],
        }


def assess(out):
    import numpy as np
    from docx import Document
    from docx.oxml.ns import qn
    from PIL import Image

    result = {"cases": {}}
    for name in ("report", "contract", "newsletter", "manual", "pdfsource"):
        folder = out / f"A-{name}-docx"
        before = read(BEFORE / f"A-{name}-docx/result.json")
        current = read(folder / "result.json")
        for filename, want in current["hashes"].items():
            file = folder / ("input/" + filename if filename.endswith(".html") else filename)
            assert hashlib.sha256(file.read_bytes()).hexdigest() == want, file
        for item in read(folder / "input-manifest.json"):
            if item["exists"]:
                assert hashlib.sha256((folder / "input" / item["reference"]).read_bytes()).hexdigest() == item["sha256"]
        a, b = current["layout"], before["layout"]
        gates = {
            "execution": current["execution_ok"],
            "aggregate": a["score"] >= b["score"],
            "pages": a["pages"] == b["pages"],
            "per_page": len(a["page_scores"]) == len(b["page_scores"])
            and all(x >= y for x, y in zip(a["page_scores"], b["page_scores"], strict=True)),
            "semantics": all(current["semantic"]["verdict"].values()),
        }
        result["cases"][name] = {"before": b, "after": a, "gates": gates, "hashes_verified": True}
    old, new = BEFORE / "A-report-docx", out / "A-report-docx"
    metadata = next(e["summary_marker"] for e in read(new / "browser-styles.json")["elements"] if e["tag"] == "summary")
    expected_advance = float(metadata["marker"]["font-size"].removesuffix("px")) * 0.75 * 1.06
    data = {
        "metadata": metadata,
        "browser": positions(new / "browser.pdf"),
        "before": positions(old / "wps.pdf"),
        "after": positions(new / "wps.pdf"),
        "source_triangle": triangle(new / "browser.pdf"),
        "target_triangle": triangle(new / "wps.pdf"),
    }
    doc = Document(new / "converted.docx")
    paragraph = next(p for p in doc.paragraphs if "计算口径" in p.text)
    body = "收入按权责发生制确认。"
    drawings = doc.element.body.findall(".//" + qn("w:drawing"))
    source, target = data["source_triangle"], data["target_triangle"]
    sv = source["vectors"][0] if source["count"] == 1 else None
    tv = target["vectors"][0] if target["count"] == 1 else None
    summary = "summary"
    following = ("mail", "phone", "unsafe_label")
    gates = {
        "source_target_triangle": sv is not None and tv is not None,
        "shape_size": sv is not None
        and tv is not None
        and all(abs((tv[b] - tv[a]) - (sv[b] - sv[a])) <= 0.10 for a, b in (("x0", "x1"), ("top", "bottom"))),
        "relative_left": sv is not None
        and tv is not None
        and abs((tv["x0"] - data["after"]["mail"]["x"]) - (sv["x0"] - data["browser"]["mail"]["x"])) <= 0.10,
        "baseline": tv is not None and abs(tv["bottom"] - target["baseline"]) <= 0.10,
        "summary_x_improved": abs(data["after"][summary]["x"] - data["browser"][summary]["x"])
        < abs(data["before"][summary]["x"] - data["browser"][summary]["x"]),
        "native_advance": abs(data["after"][summary]["x"] - data["before"][summary]["x"] - expected_advance) <= 0.10,
        "y_unchanged": all(
            abs(data["after"][k]["top"] - data["before"][k]["top"]) <= 0.05 for k in (summary, *following)
        ),
        "page1_pixels": np.array_equal(
            np.asarray(Image.open(old / "wps-page-001.png")), np.asarray(Image.open(new / "wps-page-001.png"))
        ),
        "page2_improved": result["cases"]["report"]["after"]["page_scores"][1] > 0.9778,
        "aggregate_improved": result["cases"]["report"]["after"]["score"] > 0.9302,
        "text_retained": paragraph.text == "计算口径" + body
        and "".join(p.text for p in doc.paragraphs).count(body) == 1,
        "body_hidden": any(r.text == body and r.font.hidden for r in paragraph.runs)
        and "hidden_body" not in data["after"],
        "one_marker": sum(is_managed_marker(d) for d in drawings) == 1,
        "one_real_image": sum(b.kind == "image" for b in read_model(new / "converted.docx").blocks) == 1,
    }
    result.update(
        {
            "report_data": data,
            "report_gates": gates,
            "passed": all(gates.values()) and all(all(c["gates"].values()) for c in result["cases"].values()),
        }
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = assess(args.out)
    (args.out / "acceptance.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "report_gates": result["report_gates"]}, indent=2))


if __name__ == "__main__":
    main()
