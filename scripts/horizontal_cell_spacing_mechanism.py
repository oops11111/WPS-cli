"""Stage29 fixed horizontal separate-cell spacing mechanism; product code untouched."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from lxml import etree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from html_docx_wps_matrix import color_pages, probe_wps  # noqa:E402

from wps_ai_agent_cli.html_editable import convert_html_editable  # noqa:E402
from wps_ai_agent_cli.html_render import render_html  # noqa:E402
from wps_ai_agent_cli.html_styles import _walk, load  # noqa:E402
from wps_ai_agent_cli.wps_convert import wps_convert  # noqa:E402

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
H_VALUES = (0, 2, 4)
ORDER = ("H0-C", "H0-N", "H2-C", "H2-N", "H4-C", "H4-N")


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_html(h):
    if h not in H_VALUES:
        raise ValueError(h)
    return f'<!doctype html><html><head><meta charset="utf-8"><style>body{{margin:8px;font-family:Consolas,monospace;font-size:12pt;line-height:18px}} p{{margin:0;padding:0;line-height:18px}} table{{border-collapse:separate;border-spacing:{h}px 0px;table-layout:fixed;width:{400 + 3 * h}px;margin:0;padding:0;border:0}} td{{box-sizing:border-box;width:200px;padding:0 12px;border:0;line-height:18px}}</style></head><body><p>BEFORE</p><table><tr><td>LEFT</td><td>RIGHT</td></tr></table><p>FOLLOWING</p></body></html>'


def patch_xml(source, twips):
    if twips not in (0, 30, 60):
        raise ValueError(twips)
    root = ET.fromstring(source)
    tables = root.find(W + "body").findall(W + "tbl")
    if len(tables) != 1:
        raise ValueError("Unexpected tables")
    table = tables[0]
    props = table.find(W + "tblPr")
    if len(table.findall(W + "tr")) != 1 or len(table.findall(W + "tr")[0].findall(W + "tc")) != 2:
        raise ValueError("Unexpected topology")
    if [int(c.get(W + "w")) for c in table.find(W + "tblGrid")] != [3015, 3015]:
        raise ValueError("Unexpected unchanged main grid")
    if root.findall(".//" + W + "tblCellSpacing"):
        raise ValueError("Existing spacing exception")
    spacing = ET.Element(W + "tblCellSpacing", {W + "w": str(twips), W + "type": "dxa"})
    anchor = props.find(W + "tblInd")
    if anchor is None:
        raise ValueError("Missing expected table indent")
    anchor.addprevious(spacing)
    result = ET.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True)
    props.remove(spacing)
    if ET.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True) != source:
        raise ValueError("Additional XML difference")
    return result


def candidate(source, target, twips):
    with ZipFile(source) as original, ZipFile(target, "w") as output:
        for info in original.infolist():
            data = original.read(info.filename)
            if info.filename == "word/document.xml":
                data = patch_xml(data, twips)
            output.writestr(copy.copy(info), data)


def pdf_geometry(pdf):
    import pdfplumber

    with pdfplumber.open(pdf) as document:
        if len(document.pages) != 1:
            raise ValueError("Expected one page")
        page = document.pages[0]
        words = page.extract_words()
        result = {
            "pages": 1,
            "paper": [page.width, page.height],
            "tokens": {},
            "lines": [line["text"] for line in page.extract_text_lines()],
        }
        for label in ("BEFORE", "LEFT", "RIGHT", "FOLLOWING"):
            matches = [w for w in words if w["text"] == label]
            if len(matches) != 1:
                raise ValueError("Missing/ambiguous " + label)
            word = matches[0]
            chars = [
                c for c in page.chars if word["x0"] - 0.01 <= c["x0"] < word["x1"] and abs(c["top"] - word["top"]) < 0.1
            ]
            if not chars:
                raise ValueError("No baseline " + label)
            result["tokens"][label] = {k: word[k] for k in ("x0", "x1", "top", "bottom")}
            result["tokens"][label]["baseline"] = page.height - chars[0]["matrix"][5]
        result["relative_x"] = {
            k: result["tokens"][k]["x0"] - result["tokens"]["BEFORE"]["x0"] for k in ("LEFT", "RIGHT")
        }
        return result


def preflight(out):
    from wps_ai_agent_cli import html_styles

    out.mkdir(parents=True, exist_ok=False)
    manifest = {
        "base": "810f9e3ccb7ffd8dc0b37f3d3651ba6c0d07f05a",
        "references": {},
        "wps_exports": 0,
        "not_run": list(ORDER),
    }
    for h in H_VALUES:
        folder = out / f"H{h}"
        folder.mkdir()
        source = folder / "input.html"
        pdf = folder / "browser.pdf"
        control = folder / "control.docx"
        native = folder / "native.docx"
        source.write_bytes(source_html(h).encode("utf-8"))
        styled = load(source)
        if styled.mode != "browser" or styled.browser != "157.0.4341.60":
            raise ValueError("Browser version unavailable")
        td = [n for n in _walk(styled.root) if n.tag == "td"]
        table = next(n for n in _walk(styled.root) if n.tag == "table")
        dom = {"cells": [styled.box(n) for n in td], "table": styled.box(table)}
        rendered = render_html(source, pdf, "pdf", margin_mm=10)
        write(folder / "browser-render.json", rendered)
        if not rendered[0]:
            raise ValueError("Browser render failed")
        g = pdf_geometry(pdf)
        gates = {
            "cells": len(td) == 2 and all(abs(b["width"] - 200) <= 0.02 for b in dom["cells"]),
            "table": abs(dom["table"]["width"] - (400 + 3 * h)) <= 0.02,
            "left": abs(g["relative_x"]["LEFT"] - (9 + 0.75 * h)) <= 0.10,
            "right": abs(g["relative_x"]["RIGHT"] - (159 + 1.5 * h)) <= 0.10,
        }
        record = {
            "h_px": h,
            "dom": dom,
            "geometry": g,
            "gates": gates,
            "source_sha256": sha(source),
            "browser_pdf_sha256": sha(pdf),
            "print_context": styled.print_context,
        }
        manifest["references"][f"H{h}"] = record
        write(out / "manifest.json", manifest)
        color_pages(pdf, folder, "browser-page")
        if not all(gates.values()):
            manifest["stop"] = "SOURCE_GEOMETRY_PREFLIGHT_FAILED"
            write(out / "manifest.json", manifest)
            return
        with patch.object(html_styles, "load", return_value=styled):
            converted = convert_html_editable(source, control, use_browser=False)
        if not converted[0]:
            raise ValueError(converted)
        candidate(control, native, h * 15)
        record["control_sha256"] = sha(control)
        record["native_sha256"] = sha(native)
        record["xml_pair_only_spacing"] = True
        write(out / "manifest.json", manifest)
    manifest["source_xml_preflight_passed"] = True
    write(out / "manifest.json", manifest)
    print(json.dumps({"preflight": True, "wps_exports": 0}))


def pair_gates(control, native, h, pixels):
    x = {label: native["relative_x"][label] - control["relative_x"][label] for label in ("LEFT", "RIGHT")}

    def occupied(g):
        return g["tokens"]["FOLLOWING"]["baseline"] - g["tokens"]["BEFORE"]["baseline"] - 13.5

    return {
        "left_increment": abs(x["LEFT"] - 0.75 * h) <= 0.10,
        "right_increment": abs(x["RIGHT"] - 1.5 * h) <= 0.10,
        "cell_y": all(
            abs(control["tokens"][label][k] - native["tokens"][label][k]) <= 0.05
            for label in ("LEFT", "RIGHT")
            for k in ("top", "baseline")
        ),
        "following_y": abs(control["tokens"]["FOLLOWING"]["top"] - native["tokens"]["FOLLOWING"]["top"]) <= 0.05,
        "occupied_row_height": abs(occupied(control) - occupied(native)) <= 0.05,
        "page": control["pages"] == native["pages"] == 1,
        "h0_pixels": h != 0 or pixels,
    }


def export_existing(out):
    from PIL import Image, ImageChops

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    if not manifest.get("source_xml_preflight_passed") or manifest.get("exports"):
        raise ValueError("Requires fresh passed source/XML preflight")
    first = manifest["references"]["H0"]["geometry"]
    extra = all(
        abs(r["dom"]["table"]["height"] * 0.75 - 13.5) <= 0.05
        and all(
            abs(r["geometry"]["tokens"][t][k] - first["tokens"][t][k]) <= 0.05
            for t in ("BEFORE", "LEFT", "RIGHT", "FOLLOWING")
            for k in ("top", "baseline")
        )
        for r in manifest["references"].values()
    )
    manifest["source_vertical_invariance_passed"] = extra
    if not extra:
        manifest["stop"] = "SOURCE_VERTICAL_PREFLIGHT_FAILED"
        write(out / "manifest.json", manifest)
        return
    manifest["exports"] = {}
    (out / "exports").mkdir()
    for name in ORDER:
        h = int(name[1])
        kind = name[-1]
        folder = out / "exports" / name
        folder.mkdir()
        source = out / f"H{h}" / ("control.docx" if kind == "C" else "native.docx")
        key = "control_sha256" if kind == "C" else "native_sha256"
        if sha(source) != manifest["references"][f"H{h}"][key]:
            raise ValueError("Input hash changed")
        raw, state = probe_wps()
        write(folder / "probe.json", raw)
        record = {"input_sha256": sha(source)}
        manifest["exports"][name] = record
        if (
            state is None
            or state.get("processes")
            or not any(v.get("file_version") == "12,8,2,18913" for v in state.get("executables", []))
        ):
            manifest["stop"] = "UNSAFE_OR_VERSION_MISMATCH"
            write(out / "manifest.json", manifest)
            return
        record["versions"] = state["executables"]
        manifest["not_run"].remove(name)
        pdf = folder / "wps.pdf"
        result = wps_convert(source.resolve(), pdf.resolve(), timeout_seconds=120)
        write(folder / "export.json", result)
        if not result[0]:
            manifest["stop"] = "EXPORT_FAILED"
            write(out / "manifest.json", manifest)
            return
        manifest["wps_exports"] += 1
        record["pdf_sha256"] = sha(pdf)
        try:
            record["geometry"] = pdf_geometry(pdf)
        except Exception as error:
            manifest["stop"] = "TEXT_OR_PAGE_ANOMALY"
            record["error"] = str(error)
            write(out / "manifest.json", manifest)
            return
        color_pages(pdf, folder, "wps-page")
        g = record["geometry"]
        record["absolute_source_x_error"] = {
            label: g["relative_x"][label] - manifest["references"][f"H{h}"]["geometry"]["relative_x"][label]
            for label in ("LEFT", "RIGHT")
        }
        if kind == "N":
            prior = manifest["exports"][f"H{h}-C"]
            pixels = (
                ImageChops.difference(
                    Image.open(out / "exports" / f"H{h}-C" / "wps-page-001.png"),
                    Image.open(folder / "wps-page-001.png"),
                ).getbbox()
                is None
            )
            record["pixels_identical"] = pixels
            record["gates"] = pair_gates(prior["geometry"], g, h, pixels)
            record["occupied_table_height"] = (
                g["tokens"]["FOLLOWING"]["baseline"] - g["tokens"]["BEFORE"]["baseline"] - 13.5
            )
            if not all(record["gates"].values()):
                manifest["stop"] = "GEOMETRY_OR_VERTICAL_COUPLING"
                manifest["stopped_at"] = name
                write(out / "manifest.json", manifest)
                print(
                    json.dumps(
                        {
                            "stop": manifest["stop"],
                            "case": name,
                            "gates": record["gates"],
                            "not_run": manifest["not_run"],
                        },
                        indent=2,
                    )
                )
                return
        write(out / "manifest.json", manifest)
    manifest["accepted"] = True
    write(out / "manifest.json", manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--export-existing", action="store_true")
    args = parser.parse_args()
    if args.export_existing:
        export_existing(args.out)
    else:
        preflight(args.out)


if __name__ == "__main__":
    main()
