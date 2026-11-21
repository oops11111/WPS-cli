"""Seven fixed synthetic DOCX controls; offline generation and one safe WPS set."""

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
SOURCE = ROOT / "artifacts/manual-rule-spacing-20261121/manual/converted.docx"
VARIANTS = ("B", "E", "R", "L", "LR", "N", "NR")


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
    table = copy.deepcopy(body.find(W + "tbl"))
    section = copy.deepcopy(body.find(W + "sectPr"))
    body[:] = [table, section]
    for row in table.findall(W + "tr"):
        height = child(child(row, "trPr"), "trHeight")
        height.set(W + "val", "375" if name in {"R", "LR", "NR"} else "390")
        height.set(W + "hRule", "exact" if name == "E" else "atLeast")
    if name in {"L", "LR"}:
        for cell in table.iter(W + "tc"):
            props = child(cell, "tcPr")
            margins = child(props, "tcMar")
            for side in ("top", "bottom"):
                child(margins, side).attrib.update({W + "w": "0", W + "type": "dxa"})
            for element in list(cell):
                if element.tag != W + "tcPr":
                    cell.remove(element)
            paragraph = ET.SubElement(cell, W + "p")
            pprops = ET.SubElement(paragraph, W + "pPr")
            ET.SubElement(
                pprops, W + "spacing", {W + "before": "0", W + "after": "0", W + "line": "20", W + "lineRule": "exact"}
            )
            run = ET.SubElement(paragraph, W + "r")
            rprops = ET.SubElement(run, W + "rPr")
            for tag in ("sz", "szCs"):
                ET.SubElement(rprops, W + tag, {W + "val": "2"})
            ET.SubElement(run, W + "t").text = "X"
    if name in {"N", "NR"}:
        holders = [child(table, "tblPr")] + [child(c, "tcPr") for c in table.iter(W + "tc")]
        for holder in holders:
            borders = child(holder, "tblBorders" if holder.tag == W + "tblPr" else "tcBorders")
            borders.clear()
            for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
                ET.SubElement(borders, W + side, {W + "val": "nil"})
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--export-wps", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    manifest = {"source": SOURCE.relative_to(ROOT).as_posix(), "source_sha256": digest(SOURCE), "cases": {}}
    for name in VARIANTS:
        folder = args.out / name
        folder.mkdir()
        docx, pdf = folder / "input.docx", folder / "wps.pdf"
        build(SOURCE, docx, name)
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
            color_pages(pdf, folder, "wps-page")
        write(args.out / "manifest.json", manifest)


if __name__ == "__main__":
    main()
