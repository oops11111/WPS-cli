"""Stage30 fixed paragraph-mark font falsification; no converter changes."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from zipfile import ZipFile

from lxml import etree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from html_docx_wps_matrix import color_pages, probe_wps  # noqa:E402
from manual_geometry_attribution import normalize_rule  # noqa:E402

from wps_ai_agent_cli.wps_convert import wps_convert  # noqa:E402

BASE = ROOT / "artifacts/alignment-aware-print-margins-20261121/A-contract-docx"
EXPECTED = "ee563430a86295acb8ac59ad31e5c72b1b2052e64e545fb7360a1b4feec6139f"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def patch_xml(source):
    root = ET.fromstring(source)
    table = root.find(W + "body").findall(W + "tbl")[1]
    rows = table.findall(W + "tr")
    if len(rows) != 5:
        raise ValueError("Unexpected row count")
    inserted = []
    for row in rows[2:5]:
        cells = row.findall(W + "tc")
        if len(cells) != 4:
            raise ValueError("Unexpected cell count")
        for cell in cells:
            if cell.findall(".//" + W + "vMerge") or cell.findall(".//" + W + "gridSpan"):
                raise ValueError("Merged body cell")
            paragraphs = cell.findall(W + "p")
            if len(paragraphs) != 1:
                raise ValueError("Unexpected paragraph count")
            p = paragraphs[0]
            props = p.find(W + "pPr")
            if props is None or props.find(W + "rPr") is not None:
                raise ValueError("Unexpected mark properties")
            runs = p.findall(W + "r")
            if not runs:
                raise ValueError("No visible runs")
            for run in runs:
                fonts = run.find(W + "rPr/" + W + "rFonts")
                size = run.find(W + "rPr/" + W + "sz")
                if (
                    fonts is None
                    or any(fonts.get(W + k) != "Microsoft YaHei" for k in ("ascii", "hAnsi", "eastAsia", "cs"))
                    or size is None
                    or size.get(W + "val") != "22"
                ):
                    raise ValueError("Unexpected visible font")
            mark = ET.SubElement(props, W + "rPr")
            ET.SubElement(mark, W + "rFonts", {W + k: "Microsoft YaHei" for k in ("ascii", "hAnsi", "eastAsia", "cs")})
            inserted.append((props, mark))
    if len(inserted) != 12:
        raise ValueError("Wrong target count")
    result = ET.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True)
    for props, mark in inserted:
        props.remove(mark)
    if ET.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True) != source:
        raise ValueError("Inverse XML differs")
    return result


def build(source, target):
    if sha(source) != EXPECTED:
        raise ValueError("Immutable source hash mismatch")
    with ZipFile(source) as old, ZipFile(target, "w") as new:
        for info in old.infolist():
            data = old.read(info.filename)
            if info.filename == "word/document.xml":
                data = patch_xml(data)
            new.writestr(copy.copy(info), data)
    with ZipFile(source) as old, ZipFile(target) as new:
        if old.namelist() != new.namelist() or any(
            old.read(n) != new.read(n) for n in old.namelist() if n != "word/document.xml"
        ):
            raise ValueError("Other package payload differs")


def geometry(path):
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != 1:
            raise ValueError("Expected one page")
        page = pdf.pages[0]
        chars = [
            {
                "text": c["text"],
                "x": c["x0"],
                "top": c["top"],
                "baseline": page.height - c["matrix"][5],
                "size": c["size"],
                "font": c["fontname"].split("+")[-1],
            }
            for c in page.chars
        ]
        rules = [r for o in page.lines + page.rects if (r := normalize_rule(o))]
        bounds = sorted({r["position"] for r in rules if r["axis"] == "h" and 394 < r["position"] < 469})
        if len(bounds) != 4:
            raise ValueError(f"Unexpected body boundaries: {bounds}")
        anchors = []
        for text in ("签约", "验收", "质保"):
            words = [w for w in page.extract_words() if w["text"] == text and 395 < w["top"] < 465]
            if len(words) != 1:
                raise ValueError("Ambiguous anchor")
            matching = [
                c
                for c in chars
                if c["text"] == text[0]
                and abs(c["top"] - words[0]["top"]) < 0.01
                and abs(c["x"] - words[0]["x0"]) < 0.01
            ]
            if len(matching) != 1:
                raise ValueError("Ambiguous baseline")
            anchors.append(matching[0]["baseline"])
        return {"chars": chars, "rules": rules, "boundaries": bounds, "baselines": anchors}


def assess(pdf):
    import numpy as np
    import pypdfium2 as pdfium
    from PIL import ImageChops

    from wps_ai_agent_cli.fidelity import fidelity_check, score_layout, ssim

    old, new, source = (geometry(p) for p in (BASE / "wps.pdf", pdf, BASE / "browser.pdf"))
    with pdfium.PdfDocument(str(BASE / "wps.pdf")) as a, pdfium.PdfDocument(str(pdf)) as b:
        images = [d[0].render(scale=800 / d[0].get_width()).to_pil().convert("RGB") for d in (a, b)]
        identical = ImageChops.difference(*images).getbbox() is None
    with pdfium.PdfDocument(str(BASE / "browser.pdf")) as d:
        browser = d[0].render(scale=800 / d[0].get_width()).to_pil().convert("L")
    crop = (30, int(395 * 800 / 595.92), 770, int(465 * 800 / 595.92))
    roi = [float(ssim(np.asarray(browser.crop(crop)), np.asarray(im.convert("L").crop(crop)))) for im in images]
    pairs = list(zip(old["chars"], new["chars"], strict=True))
    gates = {
        "text_line_page": all(a["text"] == b["text"] and abs(a["top"] - b["top"]) < 10 for a, b in pairs),
        "rules": old["rules"] == new["rules"],
        "glyph_x_font": all(
            abs(a["x"] - b["x"]) <= 0.05 and a["font"] == b["font"] and abs(a["size"] - b["size"]) <= 0.005
            for a, b in pairs
        ),
        "outside_body": all(abs(a["top"] - b["top"]) <= 0.05 for a, b in pairs if not 395 < a["top"] < 465),
    }

    def offsets(g):
        return [
            b - (lo + hi) / 2 for b, lo, hi in zip(g["baselines"], g["boundaries"], g["boundaries"][1:], strict=False)
        ]

    old_errors = [a - b for a, b in zip(offsets(old), offsets(source), strict=True)]
    new_errors = [a - b for a, b in zip(offsets(new), offsets(source), strict=True)]
    shifts = [b - a for a, b in zip(old["baselines"], new["baselines"], strict=True)]
    layout = score_layout(BASE / "browser.pdf", pdf, renderer="wps", images_dir=pdf.parent / "pages")
    semantic = fidelity_check(BASE / "input/contract.html", pdf.parent / "candidate.docx", layout=False)
    gates["semantics"] = semantic[0] and all(semantic[1]["verdict"].values())
    gates["ssim"] = layout["score"] >= 0.8644
    positive = (
        all(abs(a) - abs(b) >= 0.20 for a, b in zip(old_errors, new_errors, strict=True))
        and max(shifts) - min(shifts) <= 0.05
        and roi[1] > 0.5516
    )
    zero = identical and old == new
    return {
        "baseline": old,
        "candidate": new,
        "source": source,
        "old_errors": old_errors,
        "new_errors": new_errors,
        "shifts": shifts,
        "roi_ssim": roi,
        "layout": layout,
        "semantic": semantic,
        "gates": gates,
        "pixels_identical": identical,
        "outcome": "ZERO_INFLUENCE"
        if zero and all(gates.values())
        else "POSITIVE"
        if positive and all(gates.values())
        else "STOP",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--export-wps", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    target = args.out / "candidate.docx"
    build(BASE / "converted.docx", target)
    manifest = {
        "base": "5a1137b3a830011cb765197f5fbb450fb8a616d0",
        "baseline": BASE.relative_to(ROOT).as_posix(),
        "sources": {n: sha(BASE / n) for n in ("converted.docx", "browser.pdf", "wps.pdf")},
        "candidate_sha256": sha(target),
        "preflight": True,
        "wps_exports": 0,
    }
    write(args.out / "manifest.json", manifest)
    if not args.export_wps:
        return
    raw, state = probe_wps()
    write(args.out / "probe.json", raw)
    if (
        state is None
        or state.get("processes")
        or not any(v.get("file_version") == "12,8,2,18913" for v in state.get("executables", []))
    ):
        manifest["stop"] = "UNSAFE_OR_VERSION"
        write(args.out / "manifest.json", manifest)
        return
    manifest["versions"] = state["executables"]
    pdf = args.out / "wps.pdf"
    export = wps_convert(target.resolve(), pdf.resolve(), timeout_seconds=120)
    write(args.out / "export.json", export)
    manifest["wps_exports"] = 1
    write(args.out / "manifest.json", manifest)
    if not export[0]:
        raise RuntimeError("Single export failed; no retry")
    color_pages(pdf, args.out, "wps-page")
    result = assess(pdf)
    write(args.out / "acceptance.json", result)
    manifest.update(outcome=result["outcome"], pdf_sha256=sha(pdf))
    write(args.out / "manifest.json", manifest)
    print(json.dumps({"outcome": result["outcome"], "gates": result["gates"], "shifts": result["shifts"]}))


if __name__ == "__main__":
    main()
