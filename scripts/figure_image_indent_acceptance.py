"""Offline figure image geometry and original-five acceptance gates."""

import argparse
import hashlib
import json
from pathlib import Path

from closed_details_acceptance import positions, read

ROOT = Path(__file__).resolve().parents[1]
BEFORE = ROOT / "artifacts/closed-summary-marker-20261121"


def image_geometry(pdf):
    import pdfplumber

    with pdfplumber.open(pdf) as document:
        page = document.pages[0]
        assert len(page.images) == 1
        image = page.images[0]
        body = next(line for line in page.extract_text_lines() if line["text"].startswith("本季度"))
        captions = [
            {"page": i + 1, "text": line["text"], "x": line["x0"], "top": line["top"]}
            for i, p in enumerate(document.pages)
            for line in p.extract_text_lines()
            if line["text"].startswith("图 1")
        ]
        return {
            "image": {k: image[k] for k in ("x0", "top", "width", "height")},
            "body_x": body["x0"],
            "relative_x": image["x0"] - body["x0"],
            "captions": captions,
            "following": positions(pdf),
        }


def assess(out):
    from PIL import Image, ImageChops

    result = {"cases": {}}
    for name in ("report", "contract", "newsletter", "manual", "pdfsource"):
        folder = out / f"A-{name}-docx"
        old = BEFORE / folder.name
        a, b = read(folder / "result.json"), read(old / "result.json")
        for filename, want in a["hashes"].items():
            file = folder / ("input/" + filename if filename.endswith(".html") else filename)
            assert hashlib.sha256(file.read_bytes()).hexdigest() == want
        for item in read(folder / "input-manifest.json"):
            if item["exists"]:
                assert hashlib.sha256((folder / "input" / item["reference"]).read_bytes()).hexdigest() == item["sha256"]
        x, y = a["layout"], b["layout"]
        gates = {
            "execution": a["execution_ok"],
            "pages": x["pages"] == y["pages"],
            "aggregate": x["score"] >= y["score"],
            "per_page": all(v >= w for v, w in zip(x["page_scores"], y["page_scores"], strict=True)),
            "semantics": all(a["semantic"]["verdict"].values()),
        }
        if name != "report":
            gates["pixels_identical"] = all(
                ImageChops.difference(Image.open(p), Image.open(old / p.name)).getbbox() is None
                for p in folder.glob("wps-page-*.png")
            )
        result["cases"][name] = {"before": y, "after": x, "gates": gates}
    old, new = BEFORE / "A-report-docx", out / "A-report-docx"
    a, b = image_geometry(new / "wps.pdf"), image_geometry(old / "wps.pdf")
    x, y = result["cases"]["report"]["after"], result["cases"]["report"]["before"]
    gates = {
        "relative_x": abs(a["relative_x"] - 30) <= 0.1,
        "image_y_size": all(abs(a["image"][k] - b["image"][k]) <= 0.05 for k in ("top", "width", "height")),
        "caption_unchanged": a["captions"] == b["captions"],
        "following_unchanged": a["following"] == b["following"],
        "page1_improves": x["page_scores"][0] > y["page_scores"][0],
        "aggregate_improves": x["score"] > y["score"],
        "page2_pixels_identical": ImageChops.difference(
            Image.open(new / "wps-page-002.png"), Image.open(old / "wps-page-002.png")
        ).getbbox()
        is None,
    }
    result["report_geometry"] = {"before": b, "after": a, "gates": gates}
    result["passed"] = all(gates.values()) and all(all(c["gates"].values()) for c in result["cases"].values())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = assess(args.out)
    (args.out / "acceptance.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "report": result["report_geometry"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
