"""Fixed C/Z/N vector-picture-bullet experiment, at 12pt and 18pt."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import io
import json
import platform
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from html_docx_wps_matrix import color_pages, probe_wps  # noqa: E402

from wps_ai_agent_cli.wps_convert import wps_convert  # noqa: E402

VARIANTS = ("C12", "Z12", "N12", "C18", "Z18", "N18")
TEXT = ("SUMMARY", "RETAINED-BODY", "FOLLOWING")
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prediction(size):
    return {
        "square_pt": 0.66 * size,
        "width_pt": 0.86 * 0.66 * size,
        "advance_twips": round(1.06 * size * 20),
        "advance_pt": round(1.06 * size * 20) / 20,
    }


def build(path, variant):
    from docx import Document
    from docx.oxml import OxmlElement, parse_xml
    from docx.oxml.ns import qn
    from docx.shared import Inches, Mm, Pt

    if variant not in VARIANTS:
        raise ValueError(variant)
    mode, size = variant[0], int(variant[1:])
    document = Document()
    section = document.sections[0]
    section.page_width, section.page_height = Mm(210), Mm(297)
    section.top_margin = section.bottom_margin = section.left_margin = section.right_margin = Inches(1)
    for text in ("SUMMARY", "FOLLOWING"):
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.line_spacing = Pt(1.5 * size)
        paragraph.paragraph_format.space_before = paragraph.paragraph_format.space_after = Pt(0)
        run = paragraph.add_run(text)
        run.font.name, run.font.size = "Arial", Pt(size)
        if text == "SUMMARY":
            summary = paragraph
            hidden = paragraph.add_run("RETAINED-BODY")
            hidden.font.name, hidden.font.size, hidden.font.hidden = "Arial", Pt(size), True
    if mode != "C":
        numbering = document.part.numbering_part.element

        def fresh(tag, attribute):
            return max([int(n.get(qn("w:" + attribute))) for n in numbering.findall(qn("w:" + tag))] + [-1]) + 1

        picture_id, abstract_id, num_id = (
            fresh("numPicBullet", "numPicBulletId"),
            fresh("abstractNum", "abstractNumId"),
            fresh("num", "numId"),
        )

        def element(tag, **attrs):
            node = OxmlElement("w:" + tag)
            for key, value in attrs.items():
                node.set(qn("w:" + key), str(value))
            return node

        picture = element("numPicBullet", numPicBulletId=picture_id)
        pict = element("pict")
        square = prediction(size)["square_pt"]
        shape = parse_xml(
            f'<v:shape xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office" id="triangle_{size}" o:bullet="t" style="width:{square:g}pt;height:{square:g}pt" coordsize="1000,1000" path="m 0,0 l 860,500 0,1000 x e" filled="t" fillcolor="#000000" stroked="f"/>'
        )
        pict.append(shape)
        picture.append(pict)
        numbering.insert(0, picture)
        abstract = element("abstractNum", abstractNumId=abstract_id)
        abstract.append(element("multiLevelType", val="singleLevel"))
        level = element("lvl", ilvl=0)
        for tag, value in (
            ("start", 1),
            ("numFmt", "bullet"),
            ("suff", "tab" if mode == "N" else "nothing"),
            ("lvlText", "X"),
            ("lvlPicBulletId", picture_id),
            ("lvlJc", "left"),
        ):
            level.append(element(tag, val=value))
        props = element("pPr")
        advance = prediction(size)["advance_twips"] if mode == "N" else 0
        if mode == "N":
            tabs = element("tabs")
            tabs.append(element("tab", val="num", pos=advance))
            props.append(tabs)
        props.append(element("ind", left=advance, hanging=advance))
        level.append(props)
        run_props = element("rPr")
        run_props.append(element("rFonts", ascii="Arial", hAnsi="Arial"))
        run_props.append(element("sz", val=2 * size))
        run_props.append(element("szCs", val=2 * size))
        level.append(run_props)
        abstract.append(level)
        first_num = numbering.find(qn("w:num"))
        numbering.insert(list(numbering).index(first_num) if first_num is not None else len(numbering), abstract)
        num = element("num", numId=num_id)
        num.append(element("abstractNumId", val=abstract_id))
        numbering.append(num)
        pnum = element("numPr")
        pnum.append(element("ilvl", val=0))
        pnum.append(element("numId", val=num_id))
        summary._p.get_or_add_pPr().insert(0, pnum)
    buffer = io.BytesIO()
    document.save(buffer)
    with ZipFile(buffer) as source, ZipFile(path, "w", compression=ZIP_DEFLATED) as output:
        for name in sorted(source.namelist()):
            info = ZipInfo(name, (2000, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            output.writestr(info, source.read(name))


def measure(path):
    import pdfplumber

    with pdfplumber.open(path) as document:
        page = document.pages[0]
        words = [{k: w[k] for k in ("text", "x0", "x1", "top", "bottom")} for w in page.extract_words()]
        vectors = [
            {k: o.get(k) for k in ("x0", "x1", "top", "bottom", "pts", "path", "fill", "stroke", "non_stroking_color")}
            for o in page.curves + page.rects
            if o.get("fill") and o["x1"] - o["x0"] < 30 and o["bottom"] - o["top"] < 30
        ]
        char = next((c for c in page.chars if c["text"] == "S"), None)
        baseline = page.height - char["matrix"][5] if char and char.get("matrix") else None
        return {
            "pages": len(document.pages),
            "words": words,
            "vectors": vectors,
            "summary_baseline": baseline,
            "images": len(page.images),
        }


def right_triangle(vector):
    if not vector or not vector["fill"] or vector["stroke"]:
        return False
    expected = (
        (vector["x0"], vector["top"]),
        (vector["x1"], (vector["top"] + vector["bottom"]) / 2),
        (vector["x0"], vector["bottom"]),
    )
    points = vector.get("pts") or []
    return all(any(abs(x - a) <= 0.10 and abs(y - b) <= 0.10 for x, y in points) for a, b in expected) and all(
        any(abs(x - a) <= 0.10 and abs(y - b) <= 0.10 for a, b in expected) for x, y in points
    )


def gates(cases):
    required = {}
    for size in (12, 18):
        control = cases[f"C{size}"]["pdf"]
        native = cases[f"N{size}"]["pdf"]
        expected = prediction(size)

        def word(pdf, text):
            return next((w for w in pdf["words"] if w["text"] == text), None)

        c, n = word(control, "SUMMARY"), word(native, "SUMMARY")
        vectors = native["vectors"]
        v = vectors[0] if len(vectors) == 1 else None
        required[str(size)] = {
            "vector": right_triangle(v),
            "size": v is not None
            and abs(v["x1"] - v["x0"] - expected["width_pt"]) <= 0.10
            and abs(v["bottom"] - v["top"] - expected["square_pt"]) <= 0.10,
            "marker_left": v is not None and c is not None and abs(v["x0"] - c["x0"]) <= 0.10,
            "baseline": v is not None
            and native["summary_baseline"] is not None
            and abs(v["bottom"] - native["summary_baseline"]) <= 0.10,
            "advance": c is not None and n is not None and abs(n["x0"] - c["x0"] - expected["advance_pt"]) <= 0.10,
            "y": all(
                word(control, t) is not None
                and word(native, t) is not None
                and abs(word(control, t)["top"] - word(native, t)["top"]) <= 0.05
                for t in ("SUMMARY", "FOLLOWING")
            ),
        }
    common = {
        name: {
            "page": c["pdf"]["pages"] == 1,
            "visible": [w["text"] for w in c["pdf"]["words"]] == ["SUMMARY", "FOLLOWING"],
            "retained": c["retained"] == list(TEXT),
            "hidden_xml": c["hidden_xml"],
        }
        for name, c in cases.items()
    }
    return {
        "required_N": required,
        "common": common,
        "passed": all(all(g.values()) for g in list(required.values()) + list(common.values())),
        "Z": "diagnostic geometry retained in case records; no advance target",
    }


def main():
    from docx import Document

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--export-wps", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    manifest = {
        "base": "c113181c7977648294652a9e6d53b620aefbe768",
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
            "prediction": prediction(int(name[1:])),
            "docx_sha256": sha(docx),
            "retained": [s for s in TEXT if text.count(s) == 1],
            "hidden_xml": any(r.text == "RETAINED-BODY" and r.font.hidden for p in document.paragraphs for r in p.runs),
        }
        manifest["cases"][name] = case
        if args.export_wps:
            raw, state = probe_wps()
            write(folder / "probe.json", raw)
            if state is None or state.get("processes"):
                case["stop"] = "WPS_SESSION_NOT_ISOLATED"
                write(args.out / "manifest.json", manifest)
                return
            case["wps_versions"] = state.get("executables", [])
            result = wps_convert(docx.resolve(), pdf.resolve(), timeout_seconds=120)
            write(folder / "export.json", result)
            if not result[0]:
                case["stop"] = "EXPORT_FAILED"
                write(args.out / "manifest.json", manifest)
                return
            case["pdf_sha256"], case["pdf"] = sha(pdf), measure(pdf)
            color_pages(pdf, folder, "wps-page")
        write(args.out / "manifest.json", manifest)
    if args.export_wps:
        manifest["gates"] = gates(manifest["cases"])
        write(args.out / "manifest.json", manifest)


if __name__ == "__main__":
    main()
