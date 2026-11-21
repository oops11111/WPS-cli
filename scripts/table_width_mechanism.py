"""Six fixed synthetic table width controls; offline generation and one safe WPS set."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from html_docx_wps_matrix import color_pages, probe_wps  # noqa: E402
from manual_geometry_attribution import normalize_rule  # noqa: E402

from wps_ai_agent_cli.wps_convert import wps_convert  # noqa: E402

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SOURCES = {
    "M": ROOT / "artifacts/closed-summary-marker-20261121/A-manual-docx/converted.docx",
    "C": ROOT / "artifacts/closed-summary-marker-20261121/A-contract-docx/converted.docx",
}
VARIANTS = ("M0", "M05", "M1", "C0", "C05", "C1")


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def child(parent, tag):
    found = parent.find(W + tag)
    return found if found is not None else ET.SubElement(parent, W + tag)


def variant_xml(source, name):
    if name not in VARIANTS:
        raise ValueError(name)
    root = ET.fromstring(source)
    body = root.find(W + "body")
    tables = body.findall(W + "tbl")
    table = copy.deepcopy(tables[0 if name[0] == "M" else 1])
    section = copy.deepcopy(body.find(W + "sectPr"))
    body[:] = [table, section]
    if name[0] == "C":
        for row in table.findall(W + "tr")[:2]:
            table.remove(row)
    allowance = {"0": 0, "05": 7.5, "1": 15}[name[1:]]
    widths = []
    for col in table.find(W + "tblGrid"):
        width = round(int(col.get(W + "w")) - 15 + allowance)
        col.set(W + "w", str(width))
        widths.append(width)
    for row in table.findall(W + "tr"):
        cells = row.findall(W + "tc")
        assert len(cells) == len(widths)
        for cell, width in zip(cells, widths, strict=True):
            assert cell.find(".//" + W + "gridSpan") is None
            assert cell.find(".//" + W + "vMerge") is None
            child(child(cell, "tcPr"), "tcW").set(W + "w", str(width))
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def without_widths(xml):
    root = ET.fromstring(xml)
    for element in root.iter():
        if element.tag in {W + "gridCol", W + "tcW"}:
            element.set(W + "w", "WIDTH")
    return ET.tostring(root)


def build(source, target, name):
    with ZipFile(source) as original, ZipFile(target, "w", compression=ZIP_DEFLATED) as output:
        for entry in sorted(original.namelist()):
            content = original.read(entry)
            if entry == "word/document.xml":
                content = variant_xml(content, name)
            info = ZipInfo(entry, (2000, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            output.writestr(info, content)


def measure(pdf):
    import pdfplumber

    with pdfplumber.open(pdf) as document:
        page = document.pages[0]
        rules = [r for obj in page.lines + page.rects if (r := normalize_rule(obj))]
        centers = sorted({r["position"] for r in rules if r["axis"] == "h"})
        return {
            "pages": len(document.pages),
            "page_points": [page.width, page.height],
            "rules": rules,
            "horizontal_centers": centers,
            "row_pitches": [round(b - a, 6) for a, b in zip(centers, centers[1:], strict=False)],
            "chars": [{k: c[k] for k in ("text", "x0", "x1", "top", "bottom", "size")} for c in page.chars],
        }


def cell_measurements(docx, pdf):
    import pdfplumber

    with ZipFile(docx) as package:
        table = ET.fromstring(package.read("word/document.xml")).find(".//" + W + "tbl")
    with pdfplumber.open(pdf) as document:
        chars = document.pages[0].chars
        rules = [r for obj in document.pages[0].lines + document.pages[0].rects if (r := normalize_rule(obj))]
        xs = sorted({r["position"] for r in rules if r["axis"] == "v"})
        ys = sorted({r["position"] for r in rules if r["axis"] == "h"})
        rows = table.findall(W + "tr")
        if len(xs) != len(rows[0].findall(W + "tc")) + 1 or len(ys) != len(rows) + 1:
            raise ValueError("Ambiguous table boundary attribution")
        result = []
        for i, row in enumerate(rows):
            for j, cell in enumerate(row.findall(W + "tc")):
                expected = "".join(t.text or "" for t in cell.iter(W + "t"))
                visible = [
                    c
                    for c in chars
                    if xs[j] < (c["x0"] + c["x1"]) / 2 < xs[j + 1] and ys[i] < (c["top"] + c["bottom"]) / 2 < ys[i + 1]
                ]
                actual = "".join(c["text"] for c in visible)
                result.append(
                    {
                        "row": i,
                        "column": j,
                        "expected": expected,
                        "actual": actual,
                        "retained": "".join(expected.split()) == "".join(actual.split()),
                        "line_tops": sorted({round(c["top"], 2) for c in visible}),
                        "row_pitch": ys[i + 1] - ys[i],
                        "bounds": [xs[j], ys[i], xs[j + 1], ys[i + 1]],
                    }
                )
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--export-wps", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    manifest = {
        "sources": {k: {"path": v.relative_to(ROOT).as_posix(), "sha256": digest(v)} for k, v in SOURCES.items()},
        "cases": {},
    }
    for name in VARIANTS:
        folder = args.out / name
        folder.mkdir()
        docx, pdf = folder / "input.docx", folder / "wps.pdf"
        build(SOURCES[name[0]], docx, name)
        case = {"docx_sha256": digest(docx)}
        manifest["cases"][name] = case
        if args.export_wps:
            raw, state = probe_wps()
            write(folder / "probe.json", raw)
            if state is None or state.get("processes"):
                case["stop"] = "WPS_SESSION_NOT_ISOLATED"
                write(args.out / "manifest.json", manifest)
                return
            case["wps_versions"] = state.get("executables", [])
            exported = wps_convert(docx.resolve(), pdf.resolve(), timeout_seconds=120)
            write(folder / "export.json", exported)
            if not exported[0]:
                case["stop"] = "EXPORT_FAILED"
                write(args.out / "manifest.json", manifest)
                return
            case["pdf_sha256"] = digest(pdf)
            case["geometry"] = measure(pdf)
            case["cells"] = cell_measurements(docx, pdf)
            if not all(cell["retained"] for cell in case["cells"]):
                case["stop"] = "TEXT_MISSING_OR_AMBIGUOUS"
                write(args.out / "manifest.json", manifest)
                return
            if case["geometry"]["pages"] != 1:
                case["stop"] = "PAGE_COUNT"
                write(args.out / "manifest.json", manifest)
                return
            color_pages(pdf, folder, "wps-page")
        write(args.out / "manifest.json", manifest)


if __name__ == "__main__":
    main()
