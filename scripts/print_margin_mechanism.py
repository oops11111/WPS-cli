"""Fixed browser-only first gate for page margin quantization; no product changes."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from html_docx_wps_matrix import color_pages, probe_wps  # noqa: E402

from wps_ai_agent_cli.html_render import render_html  # noqa: E402
from wps_ai_agent_cli.wps_convert import wps_convert  # noqa: E402

REFERENCES = (
    ("A4-default", "A4", 10, False),
    ("A4-css12", "A4", 12, True),
    ("Letter-default", "Letter", 10, False),
    ("Letter-css12", "Letter", 12, True),
)


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_html(size, margin, explicit):
    page = f"@page {{ size:{size}; margin:{margin}mm; }}" if explicit else ""
    lines = "".join(f"<p>LINE-{i:02d}</p>" for i in range(1, 46))
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{page} body{{margin:8px;font:12pt Consolas,monospace}} p{{margin:0;line-height:17.25pt}} .bar{{height:4px;background:#00ffff;width:100%}}</style></head><body><div class="bar"></div><p>ANCHOR</p><p>{"A " * 40}</p>{lines}</body></html>'


def stream_origin(data):
    number = rb"[-+]?(?:\d*\.)?\d+"
    pattern = (
        rb"("
        + number
        + rb")\s+("
        + number
        + rb")\s+("
        + number
        + rb")\s+("
        + number
        + rb")\s+("
        + number
        + rb")\s+("
        + number
        + rb")\s+cm\b"
    )
    matrices = [list(map(float, m)) for m in re.findall(pattern, data)]
    if len(matrices) < 2:
        raise ValueError("No inspectable two-stage Chromium transform")
    a, b = matrices[:2]
    if any(abs(v) > 1e-7 for v in (a[1], a[2], a[4], b[1], b[2])):
        raise ValueError("Unexpected non-axis transform")
    return {"matrices": matrices, "content_left": a[0] * b[4]}


def measure(pdf, margin):
    import pdfplumber

    with pdfplumber.open(pdf) as document:
        page = document.pages[0]
        data = b"\n".join(
            s.resolve().get_data() if hasattr(s, "resolve") else s.get_data() for s in page.page_obj.contents
        )
        origin = stream_origin(data)
        bars = [
            r for r in page.rects if r["width"] > 400 and r["height"] < 5 and r.get("non_stroking_color") == (0, 1, 1)
        ]
        if len(bars) != 1:
            raise ValueError("Missing/ambiguous full-width cyan bar")
        bar = bars[0]
        anchor = next(w for w in page.extract_words() if w["text"] == "ANCHOR")
        expected = (math.floor(margin * 96 / 25.4) + 8) * 0.75
        return {
            "page_points": [page.width, page.height],
            "pages": len(document.pages),
            "origin": origin,
            "expected_left": expected,
            "bar": {k: bar[k] for k in ("x0", "x1", "top", "bottom")},
            "anchor": {k: anchor[k] for k in ("x0", "top")},
            "lines_by_page": [[line["text"] for line in p.extract_text_lines()] for p in document.pages],
            "gates": {
                "origin_formula": abs(origin["content_left"] - (expected - 6)) <= 0.10,
                "bar_left_formula": abs(bar["x0"] - expected) <= 0.10,
                "anchor_formula": abs(anchor["x0"] - expected) <= 0.10,
            },
        }


def build_docx(path, size, margin, quantized):
    from docx import Document
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Mm, Pt

    document = Document()
    section = document.sections[0]
    width, height = (210, 297) if size == "A4" else (215.9, 279.4)
    section.page_width, section.page_height = Mm(width), Mm(height)
    base = math.floor(margin * 96 / 25.4) * 0.75 if quantized else margin * 72 / 25.4
    section.top_margin = section.bottom_margin = Pt(base)
    section.left_margin = section.right_margin = Pt(base + 6)
    for grid in list(section._sectPr.findall(qn("w:docGrid"))):
        section._sectPr.remove(grid)
    document.styles["Normal"].font.name = "Consolas"
    document.styles["Normal"].font.size = Pt(12)
    for i, text in enumerate([" ", "ANCHOR", "A " * 40] + [f"LINE-{n:02d}" for n in range(1, 46)]):
        paragraph = document.add_paragraph()
        form = paragraph.paragraph_format
        form.space_before = Pt(6 if i == 0 else 0)
        form.space_after = Pt(0)
        form.line_spacing = Pt(3 if i == 0 else 17.25)
        paragraph.add_run(text)
        if i == 0:
            shd = OxmlElement("w:shd")
            shd.set(qn("w:fill"), "00FFFF")
            paragraph._p.get_or_add_pPr().append(shd)
    buffer = io.BytesIO()
    document.save(buffer)
    with ZipFile(buffer) as original, ZipFile(path, "w", compression=ZIP_DEFLATED) as output:
        for name in sorted(original.namelist()):
            info = ZipInfo(name, (2000, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            output.writestr(info, original.read(name))


def measure_wps(pdf):
    import pdfplumber

    with pdfplumber.open(pdf) as document:
        page = document.pages[0]
        bars = [
            r for r in page.rects if r["width"] > 400 and r["height"] < 10 and r.get("non_stroking_color") == (0, 1, 1)
        ]
        if len(bars) != 1:
            raise ValueError("Missing/ambiguous native cyan shading")
        anchor = next(w for w in page.extract_words() if w["text"] == "ANCHOR")
        return {
            "page_points": [page.width, page.height],
            "pages": len(document.pages),
            "bar": {k: bars[0][k] for k in ("x0", "x1", "top", "bottom")},
            "anchor": {k: anchor[k] for k in ("x0", "top")},
            "lines_by_page": [[line["text"] for line in p.extract_text_lines()] for p in document.pages],
        }


def export_native(out):
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    if not manifest.get("browser_gate_passed") or manifest.get("native"):
        raise ValueError("No passed fresh browser gate")
    manifest["native"] = {}
    for name, size, margin, _ in REFERENCES:
        for variant in ("precise", "floor"):
            folder = out / name / variant
            folder.mkdir()
            docx = folder / "input.docx"
            pdf = folder / "wps.pdf"
            build_docx(docx, size, margin, variant == "floor")
            raw, state = probe_wps()
            write(folder / "probe.json", raw)
            case = {"input_sha256": sha(docx)}
            manifest["native"][name + "-" + variant] = case
            if state is None or state.get("processes"):
                manifest["stop"] = "UNSAFE_WPS"
                write(out / "manifest.json", manifest)
                return
            case["versions"] = state.get("executables", [])
            exported = wps_convert(docx.resolve(), pdf.resolve(), timeout_seconds=120)
            write(folder / "export.json", exported)
            if not exported[0]:
                manifest["stop"] = "EXPORT_FAILED"
                write(out / "manifest.json", manifest)
                return
            manifest["wps_exports"] += 1
            case["pdf_sha256"] = sha(pdf)
            case["geometry"] = measure_wps(pdf)
            color_pages(pdf, folder, "wps-page")
            expected = manifest["references"][name]["geometry"]["lines_by_page"]
            actual = case["geometry"]["lines_by_page"]

            def compact(pages):
                return "".join("".join(line.split()) for page in pages for line in page)

            if compact(expected) != compact(actual):
                manifest["stop"] = "TEXT_LOSS"
                write(out / "manifest.json", manifest)
                return
            case["text_retained"] = True
            case["line_page_match"] = expected == actual
            target = manifest["references"][name]["geometry"]
            case["left_error"] = case["geometry"]["anchor"]["x0"] - target["anchor"]["x0"]
            case["right_error"] = case["geometry"]["bar"]["x1"] - target["bar"]["x1"]
            if variant == "floor":
                precise = manifest["native"][name + "-precise"]["geometry"]
                case["gates"] = {
                    "left": abs(case["left_error"]) <= 0.10,
                    "no_more_pages": case["geometry"]["pages"] <= precise["pages"],
                    "no_more_lines": sum(map(len, actual)) <= sum(map(len, precise["lines_by_page"])),
                    "bar_height": abs(
                        (case["geometry"]["bar"]["bottom"] - case["geometry"]["bar"]["top"])
                        - (precise["bar"]["bottom"] - precise["bar"]["top"])
                    )
                    <= 0.05,
                }
                if not all(case["gates"].values()):
                    manifest["stop"] = "FLOOR_GEOMETRY_OR_FLOW_GATE_FAILED"
                    write(out / "manifest.json", manifest)
                    return
            write(out / "manifest.json", manifest)
    manifest["mechanism_observed"] = all(
        abs(c["left_error"]) <= 0.10 for n, c in manifest["native"].items() if n.endswith("-floor")
    )
    manifest["product_safety_proven"] = False
    write(out / "manifest.json", manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--wps-from-existing", action="store_true")
    args = parser.parse_args()
    if args.wps_from_existing:
        export_native(args.out)
        return
    args.out.mkdir(parents=True, exist_ok=False)
    manifest = {
        "references": {},
        "wps_exports": 0,
        "formula": "floor(mm*96/25.4)*.75+6pt",
        "base": "ab96820f1423131c68f516aa6c1d342b0d683c7d",
    }
    for name, size, margin, explicit in REFERENCES:
        folder = args.out / name
        folder.mkdir()
        source = folder / "input.html"
        pdf = folder / "browser.pdf"
        source.write_bytes(source_html(size, margin, explicit).encode("utf-8"))
        exported = render_html(source, pdf, "pdf", page_size=size, margin_mm=10)
        write(folder / "browser-render.json", exported)
        if not exported[0]:
            manifest["stop"] = "BROWSER_EXPORT_FAILED"
            write(args.out / "manifest.json", manifest)
            return
        geometry = measure(pdf, margin)
        write(folder / "geometry.json", geometry)
        color_pages(pdf, folder, "browser-page")
        manifest["references"][name] = {
            "size": size,
            "css_margin_mm": margin if explicit else None,
            "api_margin_mm": 10,
            "source_sha256": sha(source),
            "pdf_sha256": sha(pdf),
            "geometry": geometry,
            "render": exported[1],
        }
        write(args.out / "manifest.json", manifest)
    manifest["browser_gate_passed"] = all(all(v["geometry"]["gates"].values()) for v in manifest["references"].values())
    if not manifest["browser_gate_passed"]:
        manifest["stop"] = "PREDECLARED_FLOOR_FORMULA_FAILED_NO_WPS"
    write(args.out / "manifest.json", manifest)
    print(
        json.dumps(
            {"browser_gate_passed": manifest["browser_gate_passed"], "stop": manifest.get("stop"), "wps_exports": 0},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
