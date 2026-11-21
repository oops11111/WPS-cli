"""Offline measurements of the committed manual PDFs and DOCX; no renderer calls."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "artifacts/manual-rule-spacing-20261121/manual"
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def points(twips):
    return int(twips) / 20


def normalize_rule(obj):
    """Compare painted rectangle centers with stroked line centers, not edges."""
    x0, x1, top, bottom = (obj[k] for k in ("x0", "x1", "top", "bottom"))
    width, height = x1 - x0, bottom - top
    if width > 20 and height <= 1:
        return {
            "axis": "h",
            "position": round((top + bottom) / 2, 6),
            "start": x0,
            "end": x1,
            "thickness": height or obj.get("linewidth", 0),
        }
    if height > 10 and width <= 1:
        return {
            "axis": "v",
            "position": round((x0 + x1) / 2, 6),
            "start": top,
            "end": bottom,
            "thickness": width or obj.get("linewidth", 0),
        }
    return None


def pdf_geometry(path):
    import pdfplumber

    with pdfplumber.open(path) as document:
        page = document.pages[0]
        # Fixed original-table window in PDF points, not fitted to target output.
        objects = [o for o in page.lines + page.rects if 100 <= o["top"] < 195 and o["x1"] < 310]
        rules = [rule for o in objects if (rule := normalize_rule(o))]
        horizontal = sorted({r["position"] for r in rules if r["axis"] == "h"})
        words = [
            {k: w[k] for k in ("text", "x0", "top", "x1", "bottom")}
            for w in page.extract_words()
            if 105 <= w["top"] < 215
        ]
        return {
            "page_points": [page.width, page.height],
            "rules": rules,
            "horizontal_centers": horizontal,
            "row_pitches": [round(b - a, 6) for a, b in zip(horizontal, horizontal[1:], strict=False)],
            "words": words,
        }


def docx_geometry(path):
    from xml.etree import ElementTree as ET

    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    table = root.find("w:body/w:tbl", NS)
    rows = []
    for row in table.findall("w:tr", NS):
        height = row.find("w:trPr/w:trHeight", NS)
        rows.append(
            {
                "height": dict(height.attrib) if height is not None else None,
                "cells": [ET.tostring(c.find("w:tcPr", NS), encoding="unicode") for c in row.findall("w:tc", NS)],
                "paragraphs": [
                    ET.tostring(p.find("w:pPr", NS), encoding="unicode") for p in row.findall("w:tc/w:p", NS)
                ],
            }
        )
    return {
        "grid_points": [points(c.attrib[f"{{{NS['w']}}}w"]) for c in table.findall("w:tblGrid/w:gridCol", NS)],
        "rows": rows,
    }


def extract():
    files = [EVIDENCE / name for name in ("browser.pdf", "wps.pdf", "converted.docx", "browser-styles.json")]
    files += [ROOT / "fixtures/fidelity/manual.html", ROOT / "src/wps_ai_agent_cli/docx_styling.py"]
    styles = json.loads((EVIDENCE / "browser-styles.json").read_text(encoding="utf-8"))
    return {
        "sources": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        "versions": {"python": platform.python_version(), "pdfplumber": importlib.metadata.version("pdfplumber")},
        "browser": pdf_geometry(EVIDENCE / "browser.pdf"),
        "wps": pdf_geometry(EVIDENCE / "wps.pdf"),
        "docx": docx_geometry(EVIDENCE / "converted.docx"),
        "browser_table_nodes": [e for e in styles["elements"] if e["tag"] in {"table", "tr", "th", "td"}],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = extract()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
