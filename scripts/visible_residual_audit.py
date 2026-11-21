"""Offline Stage46 immutable contract visible-residual audit; no conversion or native export."""

from __future__ import annotations

import argparse
import collections
import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pdfplumber
import pypdfium2 as pdfium
from lxml import etree as E
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wps_ai_agent_cli.fidelity import _pdf_pages, ssim  # noqa:E402


def extract():
    root = ROOT
    old = root / "artifacts/natural-merged-rows-20261121/A-contract-docx"
    source = root / "artifacts/schema-table-width-20261121/A-contract-docx"
    neg = root / "artifacts/row-baseline-padding-20261121"
    S = _pdf_pages(source / "browser.pdf", 800)[0]
    T = _pdf_pages(old / "wps.pdf", 800)[0].resize(S.size)
    N = _pdf_pages(neg / "wps.pdf", 800)[0].resize(S.size)
    a, b = np.asarray(S).astype(float), np.asarray(T).astype(float)
    d = np.abs(a - b)
    result = {
        "whole": float(ssim(a, b)),
        "size": S.size,
        "versions": {n: importlib.metadata.version(n) for n in ("pypdfium2", "Pillow", "numpy", "pdfplumber")},
        "hashes": {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (
                source / "browser.pdf",
                source / "browser-styles.json",
                old / "wps.pdf",
                old / "wps-page-001.png",
                old / "candidate.docx",
                neg / "wps-page-001.png",
            )
        },
        "negative_same_gray": S.size == N.size and np.array_equal(np.asarray(T), np.asarray(N)),
    }
    scale = 800 / 595.92
    edges = [0, int(348 * scale), int(395 * scale), int(470 * scale), int(640 * scale), S.height]
    part = []
    for name, lo, hi in zip(("before", "header", "body", "later", "after"), edges[:-1], edges[1:], strict=True):
        part.append(
            {
                "region": name,
                "raster_y": [lo, hi],
                "ssim": float(ssim(a[lo:hi], b[lo:hi])),
                "gray_abs_mass": float(d[lo:hi].sum()),
                "fraction_mass": float(d[lo:hi].sum() / d.sum()),
            }
        )
    result["partitions"] = part
    result["mass_sum_exact"] = sum(p["gray_abs_mass"] for p in part) == float(d.sum())
    sp = np.asarray(Image.open(old / "wps-page-001.png").convert("RGB"))
    npic = np.asarray(Image.open(neg / "wps-page-001.png").convert("RGB"))
    result["negative_same_rgb"] = np.array_equal(sp, npic)
    result["anchors"] = {}
    with pdfplumber.open(source / "browser.pdf") as sd, pdfplumber.open(old / "wps.pdf") as td:
        for prefix in ("合同总价", "第三条", "双方对", "第四条", "任何一方", "甲方（盖章）"):
            detail = {}
            for label, page, img in [("source", sd.pages[0], a), ("native", td.pages[0], b)]:
                hits = [line for line in page.extract_text_lines() if line["text"].startswith(prefix)]
                if len(hits) != 1:
                    detail[label] = {"ambiguous": len(hits)}
                    continue
                line = hits[0]
                c = line["chars"][0]
                x0 = max(0, int(c["x0"] * scale))
                x1 = min(S.width, int((c["x0"] + c["size"]) * scale) + 1)
                y0 = max(0, int((line["top"] - 2) * scale))
                y1 = min(S.height, int((line["bottom"] + 2) * scale) + 1)
                ys = np.flatnonzero((img[y0:y1, x0:x1] < 160).any(axis=1))
                detail[label] = {
                    "baseline": page.height - c["matrix"][5],
                    "bbox_pt": [line["x0"], line["top"], line["x1"], line["bottom"]],
                    "first_glyph_ink_raster_rows": ([int(ys.min() + y0), int(ys.max() + y0)] if len(ys) else None),
                    "text": line["text"],
                }
            result["anchors"][prefix] = detail
        snap = json.loads((source / "browser-styles.json").read_text(encoding="utf-8"))
        result["source_boxes"] = []
        prefixes = ("合同总价", "第三条", "双方对", "第四条", "任何一方", "甲方（盖章）")
        # Nodes have no text field; document order tags identify source CSS independently.
        for e in snap["elements"]:
            if e["tag"] in ("h2", "p", "table"):
                keys = (
                    "font-size",
                    "line-height",
                    "margin-top",
                    "margin-bottom",
                    "padding-top",
                    "padding-bottom",
                    "border-collapse",
                    "border-spacing",
                )
                result["source_boxes"].append(
                    {"tag": e["tag"], "attrs": e["attrs"], "box": e["box"], "css": {k: e["style"].get(k) for k in keys}}
                )
    with ZipFile(old / "candidate.docx") as z:
        w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        doc = E.fromstring(z.read("word/document.xml"))
        result["paragraph_xml"] = []
        for p in doc.find(w + "body").findall(w + "p"):
            text = "".join(p.itertext())
            if any(text.startswith(s) for s in prefixes):
                result["paragraph_xml"].append({"text": text, "pPr": E.tostring(p.find(w + "pPr"), encoding="unicode")})
    result["repeat_same_scores"] = float(ssim(np.asarray(S), np.asarray(T))) == result["whole"]

    r = result
    s = source / "browser.pdf"
    t = old / "wps.pdf"
    images = []
    r["vectors"] = {}
    for label, path in [("source", s), ("native", t)]:
        with pdfium.PdfDocument(str(path)) as doc:
            images.append(
                np.asarray(doc[0].render(scale=800 / doc[0].get_width()).to_pil().convert("RGB")).astype(float)
            )
        with pdfplumber.open(path) as doc:
            objs = [o for o in doc.pages[0].lines + doc.pages[0].rects if 348 <= (o["top"] + o["bottom"]) / 2 <= 470]
            count = collections.Counter(
                (o["object_type"], o.get("linewidth"), str(o.get("stroking_color")), str(o.get("non_stroking_color")))
                for o in objs
            )
            r["vectors"][label] = {"table_object_styles": [[list(k), v] for k, v in count.items()]}
    d = np.abs(images[0] - images[1])
    r["rgb_total_abs_mass"] = float(d.sum())
    for v in r["partitions"]:
        lo, hi = v["raster_y"]
        v["rgb_abs_mass"] = float(d[lo:hi].sum())
        v["rgb_fraction_mass"] = float(d[lo:hi].sum() / d.sum())
    r["fixed_roi"] = {}
    a, b = [np.asarray(Image.fromarray(v.astype("uint8")).convert("L")) for v in images]
    for name, lo, hi in [("header", 348, 395), ("body", 395, 470), ("table", 348, 470), ("later", 470, 640)]:
        box = (30, int(lo * 800 / 595.92), 770, int(hi * 800 / 595.92))
        x, y, X, Y = box
        r["fixed_roi"][name] = {"raster": box, "ssim": float(ssim(a[y:Y, x:X], b[y:Y, x:X]))}
    r["repeat_rgb_gray_whole"] = float(ssim(a, b))
    assert r["repeat_rgb_gray_whole"] == r["whole"]
    r["rgb_partition_sum_exact"] = sum(v["rgb_abs_mass"] for v in r["partitions"]) == float(d.sum())

    return r


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Refuse to overwrite audit evidence")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(extract(), ensure_ascii=False, indent=2), encoding="utf-8")
