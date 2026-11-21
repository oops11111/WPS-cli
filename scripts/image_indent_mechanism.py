"""Six fixed native image indentation controls; offline generation and one safe WPS set."""

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

from wps_ai_agent_cli.wps_convert import wps_convert  # noqa: E402

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SOURCE = ROOT / "artifacts/closed-summary-marker-20261121/A-report-docx/converted.docx"
VARIANTS = ("C0", "N0", "C40", "N40", "C80", "N80")


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
    picture = next(
        p
        for p in body.findall(W + "p")
        if p.find(".//{http://schemas.openxmlformats.org/drawingml/2006/main}blip") is not None
    )
    picture = copy.deepcopy(picture)
    props = child(picture, "pPr")
    for ind in list(props.findall(W + "ind")):
        props.remove(ind)
    if name.startswith("N"):
        ET.SubElement(props, W + "ind", {W + "left": str(int(name[1:]) * 15)})

    def text_paragraph(text):
        p = ET.Element(W + "p")
        pp = ET.SubElement(p, W + "pPr")
        ET.SubElement(
            pp, W + "spacing", {W + "before": "0", W + "after": "0", W + "line": "360", W + "lineRule": "exact"}
        )
        r = ET.SubElement(p, W + "r")
        rp = ET.SubElement(r, W + "rPr")
        ET.SubElement(rp, W + "sz", {W + "val": "24"})
        ET.SubElement(r, W + "t").text = text
        return p

    body[:] = [text_paragraph("BEFORE"), picture, text_paragraph("FOLLOWING"), copy.deepcopy(body.find(W + "sectPr"))]
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def without_indent(xml):
    root = ET.fromstring(xml)
    for props in root.iter(W + "pPr"):
        for ind in list(props.findall(W + "ind")):
            props.remove(ind)
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
        words = {w["text"]: w for w in page.extract_words()}
        if len(page.images) != 1 or not {"BEFORE", "FOLLOWING"}.issubset(words):
            raise ValueError("Missing/ambiguous image or control text")
        image = page.images[0]
        return {
            "pages": len(document.pages),
            "image": {k: image[k] for k in ("x0", "top", "width", "height")},
            "before": {k: words["BEFORE"][k] for k in ("x0", "top")},
            "following": {k: words["FOLLOWING"][k] for k in ("x0", "top")},
            "relative_x": image["x0"] - words["BEFORE"]["x0"],
        }


def gates(case, baseline, name):
    expected = int(name[1:]) * 0.75 if name.startswith("N") else 0
    return {
        "x": abs(case["relative_x"] - expected) <= 0.10,
        "pages": case["pages"] == baseline["pages"] == 1,
        "image_y_size": all(abs(case["image"][k] - baseline["image"][k]) <= 0.05 for k in ("top", "width", "height")),
        "text_y": all(abs(case[k]["top"] - baseline[k]["top"]) <= 0.05 for k in ("before", "following")),
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
            baseline = manifest["cases"]["C0"]["geometry"]
            case["gates"] = gates(case["geometry"], baseline, name)
            if not all(case["gates"].values()):
                case["stop"] = "GEOMETRY_GATE_FAILED"
                write(args.out / "manifest.json", manifest)
                return
        write(args.out / "manifest.json", manifest)


if __name__ == "__main__":
    main()
