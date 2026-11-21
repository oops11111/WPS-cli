"""Stage49 read-only saved-snapshot feasibility; no collector/converter/native execution."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]


def extract():
    from docx import Document
    from lxml import etree as ET
    from table_width_environment import restore_snapshot

    from wps_ai_agent_cli import docx_styling, html_styles
    from wps_ai_agent_cli.html_editable import _text, table_grid, table_rows

    result = {"tables": {}, "boundaries": [], "missing_guard_fields": []}
    for case in ("report", "contract", "newsletter", "manual", "pdfsource"):
        folder = ROOT / f"artifacts/natural-merged-rows-20261121/A-{case}-docx"
        snapshot = json.loads((folder / "browser-styles.json").read_text(encoding="utf-8"))
        source = ROOT / f"artifacts/schema-table-width-20261121/A-{case}-docx/input"
        styled = restore_snapshot(next(source.glob("*.html")), snapshot)
        width = docx_styling.apply_page(Document(), styled)
        tables = []
        for node in html_styles._walk(styled.root):
            if node.tag == "table":
                natural = docx_styling.measured_merged_row_minima(
                    styled, node, table_grid(node)[0], table_rows(node), width
                )
                tables.append({"attrs": node.attrs, "minima": natural})
        result["tables"][case] = tables
        if case != "contract":
            continue
        entries = {e["attrs"].get("data-wps-i"): e for e in snapshot["elements"]}
        nodes = {node.attrs.get("data-wps-i"): node for node in html_styles._walk(styled.root)}
        w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        with ZipFile(folder / "candidate.docx") as archive:
            body = ET.fromstring(archive.read("word/document.xml")).find(w + "body")
        paragraphs = {"".join(p.itertext()): p for p in body.findall(w + "p")}
        for pi, hi in (("49", "51"), ("52", "55")):
            p, h = entries[pi], entries[hi]
            gap = h["box"]["y"] - p["box"]["y"] - p["box"]["height"]
            m1, m2 = float(p["style"]["margin-bottom"][:-2]), float(h["style"]["margin-top"][:-2])
            detail = {
                "p": pi,
                "h2": hi,
                "p_box": p["box"],
                "h2_box": h["box"],
                "p_line": p["style"]["line-height"],
                "h2_line": h["style"]["line-height"],
                "gap": gap,
                "max_margin": max(m1, m2),
                "gap_error": abs(gap - max(m1, m2)),
                "current_p_after_twips": int(
                    paragraphs[_text(nodes[pi])].find(w + "pPr/" + w + "spacing").get(w + "after")
                ),
                "current_h2_before_twips": int(
                    paragraphs[_text(nodes[hi])].find(w + "pPr/" + w + "spacing").get(w + "before")
                ),
                "full_h2_before_twips": round(m2 * 0.75 * 20),
                "styles": {},
            }
            for name, entry in (("p", p), ("h2", h)):
                keys = (
                    "position",
                    "display",
                    "transform",
                    "zoom",
                    "float",
                    "writing-mode",
                    "direction",
                    "overflow-x",
                    "overflow-y",
                    "clip-path",
                    "opacity",
                    "visibility",
                    "text-lines",
                    "break-before",
                    "page-break-before",
                    "break-after",
                    "page-break-after",
                    "break-inside",
                    "page-break-inside",
                )
                detail["styles"][name] = {key: entry["style"].get(key, "MISSING") for key in keys}
            result["boundaries"].append(detail)
        for key in ("break-after", "page-break-after", "break-inside", "page-break-inside"):
            if any(key not in entries[i]["style"] for i in ("49", "51", "52", "55")):
                result["missing_guard_fields"].append(key)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Refuse to overwrite original feasibility evidence")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(extract(), ensure_ascii=False, indent=2), encoding="utf-8")
