"""Fixed synthetic C/I/G inline DrawingML mechanism, no product conversion."""

from __future__ import annotations

import argparse
import importlib.metadata
import io
import platform
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from summary_picture_bullet_mechanism import (  # noqa: E402
    color_pages,
    measure,
    probe_wps,
    right_triangle,
    sha,
    wps_convert,
    write,
)

VARIANTS = ("C12", "I12", "G12", "C18", "I18", "G18")
TEXT = ("SUMMARY", "RETAINED-BODY", "FOLLOWING")


def build(path, name):
    from docx import Document
    from docx.oxml import parse_xml
    from docx.shared import Inches, Mm, Pt

    if name not in VARIANTS:
        raise ValueError(name)
    mode, size = name[0], int(name[1:])
    document = Document()
    section = document.sections[0]
    section.page_width, section.page_height = Mm(210), Mm(297)
    section.top_margin = section.bottom_margin = section.left_margin = section.right_margin = Inches(1)
    for text in ("SUMMARY", "FOLLOWING"):
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.line_spacing = Pt(1.5 * size)
        paragraph.paragraph_format.space_before = paragraph.paragraph_format.space_after = Pt(0)
        if text == "SUMMARY" and mode != "C":
            advance = (0.66 if mode == "I" else 1.06) * size
            cx, cy = round(advance * 12700), round(0.66 * size * 12700)
            canvas = 6600 if mode == "I" else 10600
            xml = f'''<mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
<mc:Choice Requires="wps"><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">
<wp:extent cx="{cx}" cy="{cy}"/><wp:effectExtent l="0" t="0" r="0" b="0"/><wp:docPr id="1" name="Disclosure marker"/><wp:cNvGraphicFramePr/>
<a:graphic><a:graphicData uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"><wps:wsp><wps:cNvSpPr/><wps:spPr>
<a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
<a:custGeom><a:avLst/><a:gdLst/><a:ahLst/><a:cxnLst/><a:rect l="0" t="0" r="0" b="0"/><a:pathLst><a:path w="{canvas}" h="6600" stroke="0" fill="norm"><a:moveTo><a:pt x="0" y="0"/></a:moveTo><a:lnTo><a:pt x="5676" y="3300"/></a:lnTo><a:lnTo><a:pt x="0" y="6600"/></a:lnTo><a:close/></a:path></a:pathLst></a:custGeom>
<a:solidFill><a:srgbClr val="000000"/></a:solidFill><a:ln><a:noFill/></a:ln></wps:spPr><wps:bodyPr/></wps:wsp></a:graphicData></a:graphic>
</wp:inline></w:drawing></mc:Choice></mc:AlternateContent>'''
            run = paragraph.add_run()
            run.font.name, run.font.size = "Arial", Pt(size)
            run._r.append(parse_xml(xml))
        run = paragraph.add_run(text)
        run.font.name, run.font.size = "Arial", Pt(size)
        if text == "SUMMARY":
            hidden = paragraph.add_run("RETAINED-BODY")
            hidden.font.name, hidden.font.size, hidden.font.hidden = "Arial", Pt(size), True
    buffer = io.BytesIO()
    document.save(buffer)
    with ZipFile(buffer) as source, ZipFile(path, "w", compression=ZIP_DEFLATED) as output:
        for part in sorted(source.namelist()):
            info = ZipInfo(part, (2000, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            output.writestr(info, source.read(part))


def gates(cases):
    required = {}
    for size in (12, 18):

        def word(name, text, size=size):
            return next((w for w in cases[f"{name}{size}"]["pdf"]["words"] if w["text"] == text), None)

        control = word("C", "SUMMARY")
        for mode in ("I", "G"):
            pdf = cases[f"{mode}{size}"]["pdf"]
            summary = word(mode, "SUMMARY")
            vectors = pdf["vectors"]
            v = vectors[0] if len(vectors) == 1 else None
            required[f"{mode}{size}"] = {
                "triangle": right_triangle(v),
                "size": v is not None
                and abs(v["x1"] - v["x0"] - 0.5676 * size) <= 0.10
                and abs(v["bottom"] - v["top"] - 0.66 * size) <= 0.10,
                "left": v is not None and control is not None and abs(v["x0"] - control["x0"]) <= 0.10,
                "baseline": v is not None
                and pdf["summary_baseline"] is not None
                and abs(v["bottom"] - pdf["summary_baseline"]) <= 0.10,
                "advance": control is not None
                and summary is not None
                and abs(summary["x0"] - control["x0"] - (0.66 if mode == "I" else 1.06) * size) <= 0.10,
                "y": all(
                    word("C", t) is not None
                    and word(mode, t) is not None
                    and abs(word("C", t)["top"] - word(mode, t)["top"]) <= 0.05
                    for t in ("SUMMARY", "FOLLOWING")
                ),
            }
        i, g = word("I", "SUMMARY"), word("G", "SUMMARY")
        required[f"gap{size}"] = {
            "gap": i is not None and g is not None and abs(g["x0"] - i["x0"] - 0.4 * size) <= 0.10
        }
    common = {
        name: {
            "page": c["pdf"]["pages"] == 1,
            "visible": [w["text"] for w in c["pdf"]["words"]] == ["SUMMARY", "FOLLOWING"],
            "retained": c["retained"] == list(TEXT),
            "hidden": c["hidden_xml"],
        }
        for name, c in cases.items()
    }
    return {
        "required": required,
        "common": common,
        "passed": all(all(g.values()) for g in list(required.values()) + list(common.values())),
    }


def main():
    from docx import Document

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--export-wps", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    result = {
        "base": "9a33efd851b4e00bca3d21d8ec600518828cf637",
        "runner_sha256": sha(Path(__file__)),
        "python": platform.python_version(),
        "pdfplumber": importlib.metadata.version("pdfplumber"),
        "python_docx": importlib.metadata.version("python-docx"),
        "settings": "Unqueried and unchanged",
        "cases": {},
    }
    for name in VARIANTS:
        folder = args.out / name
        folder.mkdir()
        docx, pdf = folder / "input.docx", folder / "wps.pdf"
        build(docx, name)
        document = Document(docx)
        text = "".join(p.text for p in document.paragraphs)
        case = {
            "docx_sha256": sha(docx),
            "retained": [s for s in TEXT if text.count(s) == 1],
            "hidden_xml": any(r.text == "RETAINED-BODY" and r.font.hidden for p in document.paragraphs for r in p.runs),
        }
        result["cases"][name] = case
        if args.export_wps:
            raw, state = probe_wps()
            write(folder / "probe.json", raw)
            if state is None or state.get("processes"):
                case["stop"] = "WPS_SESSION_NOT_ISOLATED"
                write(args.out / "manifest.json", result)
                return
            case["wps_versions"] = state.get("executables", [])
            exported = wps_convert(docx.resolve(), pdf.resolve(), timeout_seconds=120)
            write(folder / "export.json", exported)
            if not exported[0]:
                case["stop"] = "EXPORT_FAILED"
                write(args.out / "manifest.json", result)
                return
            case["pdf_sha256"], case["pdf"] = sha(pdf), measure(pdf)
            color_pages(pdf, folder, "wps-page")
        write(args.out / "manifest.json", result)
    if args.export_wps:
        result["gates"] = gates(result["cases"])
        write(args.out / "manifest.json", result)


if __name__ == "__main__":
    main()
