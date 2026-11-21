"""Offline original-five gates for the bounded horizontal margin candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from manual_geometry_attribution import normalize_rule
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
BEFORE = ROOT / "artifacts/figure-image-indent-20261121"
ANCHORS = {"contract": "第一条", "manual": "部署手册", "newsletter": "研发月刊", "pdfsource": "供应商评估报告"}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def geometry(pdf, case):
    import pdfplumber

    with pdfplumber.open(pdf) as document:
        pages = []
        for page in document.pages:
            pages.append(
                {
                    "paper": [page.width, page.height],
                    "lines": [line["text"] for line in page.extract_text_lines()],
                    "chars": [{k: c[k] for k in ("text", "x0", "x1", "top", "bottom")} for c in page.chars],
                    "images": [{k: i[k] for k in ("x0", "top", "width", "height")} for i in page.images],
                }
            )
        first = document.pages[0]
        lines = first.extract_text_lines()
        left = next(line["x0"] for line in lines if line["text"].startswith(ANCHORS[case]))
        if case == "contract":
            right = next(line["x1"] for line in lines if line["text"].startswith("合同编号"))
        elif case in {"manual", "newsletter"}:
            right = max(o["x1"] for o in first.lines + first.rects if o["width"] > 400)
        else:
            right = max(c["x1"] for c in first.chars)
        rules = [r for o in first.lines + first.rects if (r := normalize_rule(o))]
        relative = []
        for r in rules:
            r = dict(r)
            if r["axis"] == "v":
                r["position"] -= left
            else:
                r["start"] -= left
                r["end"] -= left
            relative.append(r)
        return {
            "pages": pages,
            "left": left,
            "right": right,
            "relative_rules": relative,
            "rects_relative": [
                {k: (o[k] - left if k in ("x0", "x1") else o[k]) for k in ("x0", "x1", "top", "bottom")}
                for o in first.rects
            ],
        }


def close_objects(a, b, keys):
    return len(a) == len(b) and all(all(abs(x[k] - y[k]) <= 0.05 for k in keys) for x, y in zip(a, b, strict=True))


def alignment_mode(source_align, holder_align, jc, left_margin, right_margin, indents):
    if source_align in {"start", "left"} and holder_align in {"start", "left"} and jc == "left":
        return "left"
    if source_align == holder_align == jc == "center":
        if left_margin != right_margin or any(str(v) != "0" for v in indents.values()):
            raise ValueError("Centered image requires symmetric margins and no indent")
        return "center"
    raise ValueError("Unknown/contradictory source-computed/DOCX image alignment")


def picture_contract(docx, source_images):
    from zipfile import ZipFile

    from lxml import etree as ET

    w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with ZipFile(docx) as z:
        root = ET.fromstring(z.read("word/document.xml"))
        styles = ET.fromstring(z.read("word/styles.xml"))
    section = root.find(".//" + w + "sectPr")
    margin = section.find(w + "pgMar")
    width = int(section.find(w + "pgSz").get(w + "w")) / 20
    left, right = int(margin.get(w + "left")) / 20, int(margin.get(w + "right")) / 20
    result = []
    for p in root.findall(".//" + w + "body/" + w + "p"):
        if p.find(".//{http://schemas.openxmlformats.org/drawingml/2006/main}blip") is None:
            continue
        props = p.find(w + "pPr")
        jc = props.find(w + "jc")
        ind = props.find(w + "ind")
        indents = {} if ind is None else dict(ind.attrib)
        style = props.find(w + "pStyle")
        sid = style.get(w + "val") if style is not None else "Normal"
        seen = set()
        while sid and sid not in seen:
            seen.add(sid)
            st = next((s for s in styles.findall(w + "style") if s.get(w + "styleId") == sid), None)
            if st is None:
                raise ValueError("Unknown picture paragraph style")
            inherited = st.find(w + "pPr/" + w + "ind")
            if inherited is not None:
                for k, v in inherited.attrib.items():
                    indents.setdefault(k, v)
            based = st.find(w + "basedOn")
            sid = based.get(w + "val") if based is not None else None
        if len(result) >= len(source_images):
            raise ValueError("No matching source image")
        source = source_images[len(result)]
        mode = alignment_mode(
            source["source_align"],
            source["holder_align"],
            jc.get(w + "val") if jc is not None else None,
            left,
            right,
            indents,
        )
        result.append(
            {
                "mode": mode,
                "source": source,
                "jc": jc.get(w + "val"),
                "indents": indents,
                "left_margin": left,
                "right_margin": right,
                "paper_width": width,
                "content_midline": (left + width - right) / 2,
            }
        )
    if len(result) != len(source_images):
        raise ValueError("Source/DOCX image count mismatch")
    return result


def image_invariant(mode, before, after, browser, body_before, body_after, mid_before, mid_after):
    common = all(abs(before[k] - after[k]) <= 0.05 for k in ("top", "width", "height"))
    if mode == "left":
        return common and abs((before["x0"] - body_before) - (after["x0"] - body_after)) <= 0.05
    if mode == "center":
        a, b, r = (i["x0"] + i["width"] / 2 for i in (before, after, browser))
        return (
            common
            and abs(a - b) <= 0.05
            and abs((a - mid_before) - (b - mid_after)) <= 0.05
            and abs(b - r) <= abs(a - r) + 0.001
        )
    raise ValueError("Unknown alignment invariant")


def assess(out):
    results = {}
    for name in ("report", "contract", "manual", "newsletter", "pdfsource"):
        old = BEFORE / f"A-{name}-docx"
        new = out / old.name
        a, b = read(old / "result.json"), read(new / "result.json")
        for filename, want in b["hashes"].items():
            file = new / ("input/" + filename if filename.endswith(".html") else filename)
            assert hashlib.sha256(file.read_bytes()).hexdigest() == want
        x, y = a["layout"], b["layout"]
        gates = {
            "execution": b["execution_ok"],
            "semantics": all(b["semantic"]["verdict"].values()),
            "pages": x["pages"] == y["pages"],
            "aggregate": y["score"] >= x["score"],
            "per_page": all(v >= w for v, w in zip(y["page_scores"], x["page_scores"], strict=True)),
        }
        if name in ("manual", "contract"):
            gates["required_improvement"] = y["score"] > x["score"]
        record = {"before": x, "after": y, "gates": gates}
        if name == "report":
            gates["pixels_identical"] = all(
                ImageChops.difference(Image.open(p), Image.open(old / p.name)).getbbox() is None
                for p in new.glob("wps-page-*.png")
            )
        else:
            previous, current, reference = (
                geometry(old / "wps.pdf", name),
                geometry(new / "wps.pdf", name),
                geometry(new / "browser.pdf", name),
            )
            pp, cp = previous["pages"], current["pages"]
            gates["line_page_assignment"] = len(pp) == len(cp) and all(
                p["lines"] == q["lines"] for p, q in zip(pp, cp, strict=True)
            )
            gates["paper"] = all(p["paper"] == q["paper"] for p, q in zip(pp, cp, strict=True))
            gates["all_char_y"] = all(
                len(p["chars"]) == len(q["chars"])
                and all(
                    c["text"] == d["text"]
                    and abs(c["top"] - d["top"]) <= 0.05
                    and abs(c["bottom"] - d["bottom"]) <= 0.05
                    for c, d in zip(p["chars"], q["chars"], strict=True)
                )
                for p, q in zip(pp, cp, strict=True)
            )
            gates["left"] = abs(current["left"] - reference["left"]) <= 0.10
            gates["right_no_worse"] = (
                abs(current["right"] - reference["right"]) <= abs(previous["right"] - reference["right"]) + 0.001
            )
            source_info = read(
                out.parent / "alignment-aware-margins-preflight-20261121" / f"A-{name}-docx-qualification.json"
            )["source_images"]
            prior_contract = picture_contract(old / "converted.docx", source_info)
            current_contract = picture_contract(new / "converted.docx", source_info)
            observed = read(new / "browser-styles.json")["elements"]
            observed_images = [e for e in observed if e["tag"] == "img"]
            if len(observed_images) != len(source_info) or any(
                e["style"].get("text-align") != s["source_align"]
                for e, s in zip(observed_images, source_info, strict=True)
            ):
                raise ValueError("Source alignment changed since preflight")
            gates["alignment_image_invariant"] = True
            for p, q, r in zip(pp, cp, reference["pages"], strict=True):
                if len(p["images"]) != len(q["images"]) or len(p["images"]) != len(r["images"]):
                    raise ValueError("PDF image cardinality mismatch")
                for i, (aimg, bimg, rimg) in enumerate(zip(p["images"], q["images"], r["images"], strict=True)):
                    a_contract, b_contract = prior_contract[i], current_contract[i]
                    if a_contract["mode"] != b_contract["mode"]:
                        raise ValueError("Image alignment mode changed")
                    gates["alignment_image_invariant"] &= image_invariant(
                        b_contract["mode"],
                        aimg,
                        bimg,
                        rimg,
                        previous["left"],
                        current["left"],
                        a_contract["content_midline"],
                        b_contract["content_midline"],
                    )
            record["image_contract"] = {"before": prior_contract, "after": current_contract}
            if name == "contract":
                gates["contract_relative_rules"] = len(previous["relative_rules"]) == len(
                    current["relative_rules"]
                ) and all(
                    p["axis"] == q["axis"]
                    and all(abs(p[k] - q[k]) <= 0.05 for k in ("position", "start", "end", "thickness"))
                    for p, q in zip(previous["relative_rules"], current["relative_rules"], strict=True)
                )
                gates["contract_header_rects"] = close_objects(
                    previous["rects_relative"], current["rects_relative"], ("x0", "x1", "top", "bottom")
                )
            record["geometry"] = {
                "before": previous,
                "after": current,
                "browser": reference,
                "left_error": current["left"] - reference["left"],
                "right_error_before": previous["right"] - reference["right"],
                "right_error_after": current["right"] - reference["right"],
            }
        results[name] = record
    return {"cases": results, "passed": all(all(r["gates"].values()) for r in results.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = assess(args.out)
    (args.out / "acceptance.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps({"passed": result["passed"], "gates": {n: v["gates"] for n, v in result["cases"].items()}}, indent=2)
    )


if __name__ == "__main__":
    main()
