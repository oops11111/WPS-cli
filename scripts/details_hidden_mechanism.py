"""Fixed V/H/P/C retained-text experiment; no product conversion or setting changes."""

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

VARIANTS = ("V", "H", "P", "C")
SENTINELS = ("SUMMARY", "RETAINED-BODY", "FOLLOWING")


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(path, variant):
    from docx import Document
    from docx.oxml import OxmlElement
    from docx.shared import Inches, Mm, Pt

    if variant not in VARIANTS:
        raise ValueError(variant)
    document = Document()
    section = document.sections[0]
    section.page_width, section.page_height = Mm(210), Mm(297)
    section.top_margin = section.bottom_margin = section.left_margin = section.right_margin = Inches(1)

    def paragraph(text, hidden=False):
        p = document.add_paragraph()
        p.paragraph_format.space_before = p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = Pt(18)
        run(p, text, hidden)
        return p

    def run(p, text, hidden=False):
        r = p.add_run(text)
        r.font.name, r.font.size = "Arial", Pt(12)
        if hidden:
            r.font.hidden = True

    summary = paragraph("SUMMARY")
    if variant == "H":
        run(summary, "RETAINED-BODY", True)
    elif variant in {"V", "P"}:
        body = paragraph("RETAINED-BODY", variant == "P")
        if variant == "P":
            props = OxmlElement("w:rPr")
            props.append(OxmlElement("w:vanish"))
            body._p.get_or_add_pPr().append(props)
    paragraph("FOLLOWING")
    buffer = io.BytesIO()
    document.save(buffer)
    with ZipFile(buffer) as original, ZipFile(path, "w", compression=ZIP_DEFLATED) as output:
        for name in sorted(original.namelist()):
            info = ZipInfo(name, (2000, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            output.writestr(info, original.read(name))


def measure(path):
    import pdfplumber

    with pdfplumber.open(path) as document:
        return {
            "pages": len(document.pages),
            "words": [
                {"page": index + 1, **{key: word[key] for key in ("text", "x0", "top", "x1", "bottom")}}
                for index, page in enumerate(document.pages)
                for word in page.extract_words()
            ],
        }


def gates(cases):
    def texts(name):
        return [w["text"] for w in cases[name]["pdf"]["words"]]

    def following(name):
        return next(w["top"] for w in cases[name]["pdf"]["words"] if w["text"] == "FOLLOWING")

    required = {
        "one_page_each": all(c["pdf"]["pages"] == 1 for c in cases.values()),
        "visible_control": texts("V") == list(SENTINELS),
        "closed_reference": texts("C") == ["SUMMARY", "FOLLOWING"],
        "H_retains": cases["H"]["retained"] == list(SENTINELS),
        "H_visible": texts("H") == ["SUMMARY", "FOLLOWING"],
        "H_following": abs(following("H") - following("C")) <= 0.05,
    }
    return {
        "required": required,
        "passed": all(required.values()),
        "P_diagnostic": {"visible": texts("P"), "following_delta_pt": following("P") - following("C")},
    }


def main():
    from docx import Document

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--export-wps", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    manifest = {
        "base": "5779f84c258aa1dc9690e8a88240b5f53b7b9e59",
        "runner_sha256": sha(Path(__file__)),
        "python": platform.python_version(),
        "pdfplumber": importlib.metadata.version("pdfplumber"),
        "settings": "Not queried or changed; WPS hidden display/printing preferences unknown.",
        "cases": {},
    }
    for name in VARIANTS:
        folder = args.out / name
        folder.mkdir()
        docx, pdf = folder / "input.docx", folder / "wps.pdf"
        build(docx, name)
        text = "".join(p.text for p in Document(docx).paragraphs)
        case = {"docx_sha256": sha(docx), "retained": [s for s in SENTINELS if s in text]}
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
