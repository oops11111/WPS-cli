"""Stage37 fixed copied-contract wrap mechanism; no product edits."""

from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path
from zipfile import ZipFile

from lxml import etree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from html_docx_wps_matrix import color_pages, probe_wps  # noqa:E402
from paragraph_mark_font_mechanism import BASE, EXPECTED, W, sha, write  # noqa:E402

from wps_ai_agent_cli.wps_convert import wps_convert  # noqa:E402

GRID = [710, 724, 1370, 2729]


def patch_xml(source):
    root = ET.fromstring(source)
    table = root.find(W + "body").findall(W + "tbl")[0]
    grid = table.find(W + "tblGrid")
    if [int(e.get(W + "w")) for e in grid] != GRID:
        raise ValueError("Wrong grid")
    changes = []
    for c in grid:
        changes.append((c, c.get(W + "w")))
    rows = table.findall(W + "tr")
    if len(rows) != 5:
        raise ValueError("Wrong rows")
    expected = [[710, 1370, 2729], [2639, 724, 1370, 2639]] + [GRID] * 3
    for ri, row in enumerate(rows):
        cells = row.findall(W + "tc")
        if len(cells) != len(expected[ri]):
            raise ValueError("Wrong cell count")
        for ci, cell in enumerate(cells):
            width = cell.find(W + "tcPr/" + W + "tcW")
            if int(width.get(W + "w")) != expected[ri][ci]:
                raise ValueError("Wrong cell width")
            merge = cell.find(W + "tcPr/" + W + "vMerge")
            span = cell.find(W + "tcPr/" + W + "gridSpan")
            if (span is not None) != (ri == 0 and ci == 1) or (span is not None and span.get(W + "val") != "2"):
                raise ValueError("Wrong span topology")
            restart = ri == 0 and ci in (0, 2)
            continuation = ri == 1 and ci in (0, 3)
            if restart and (merge is None or merge.get(W + "val") != "restart"):
                raise ValueError("Wrong rowspan origin")
            if not restart and not continuation and merge is not None:
                raise ValueError("Unexpected merge")
            if continuation:
                if merge is None or merge.get(W + "val") not in (None, "continue"):
                    raise ValueError("Wrong continuation")
            else:
                changes.append((width, width.get(W + "w")))
    if len(changes) != 21:
        raise ValueError("Wrong allowlist count")
    for node, before in changes:
        node.set(W + "w", str(int(before) - 15))
    result = ET.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True)
    for node, before in changes:
        node.set(W + "w", before)
    if ET.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True) != source:
        raise ValueError("Inverse mismatch")
    return result


def serialize(root):
    return ET.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True)


def control_xml(source):
    root = ET.fromstring(source)
    body = root.find(W + "body")
    table = copy.deepcopy(body.findall(W + "tbl")[1])
    for run in table.iter(W + "r"):
        fonts = run.find(W + "rPr/" + W + "rFonts")
        size = run.find(W + "rPr/" + W + "sz")
        if (
            fonts is None
            or any(fonts.get(W + k) != "Microsoft YaHei" for k in ("ascii", "hAnsi", "eastAsia", "cs"))
            or size is None
            or size.get(W + "val") != "22"
        ):
            raise ValueError("Unexpected source font/size")
    before = copy.deepcopy(body.find(W + "p"))
    after = copy.deepcopy(before)
    for paragraph, text in ((before, "BEFORE"), (after, "FOLLOWING")):
        for run in paragraph.findall(W + "r"):
            paragraph.remove(run)
        run = ET.SubElement(paragraph, W + "r")
        props = ET.SubElement(run, W + "rPr")
        ET.SubElement(props, W + "rFonts", {W + k: "Microsoft YaHei" for k in ("ascii", "hAnsi", "eastAsia", "cs")})
        ET.SubElement(props, W + "sz", {W + "val": "22"})
        ET.SubElement(run, W + "t").text = text
    section = copy.deepcopy(body.find(W + "sectPr"))
    original_table = ET.tostring(body.findall(W + "tbl")[1], method="c14n")
    body[:] = [before, table, after, section]
    if ET.tostring(table, method="c14n") != original_table:
        raise ValueError("Copied table differs")
    return serialize(root)


def build(target, zero=False):
    source = BASE / "converted.docx"
    if sha(source) != EXPECTED:
        raise ValueError("Source hash mismatch")
    with ZipFile(source) as old, ZipFile(target, "w") as new:
        for info in old.infolist():
            data = old.read(info.filename)
            if info.filename == "word/document.xml":
                data = control_xml(data)
                if zero:
                    data = patch_xml(data)
            new.writestr(copy.copy(info), data)
    with ZipFile(source) as old, ZipFile(target) as new:
        if any(old.read(n) != new.read(n) for n in old.namelist() if n != "word/document.xml"):
            raise ValueError("Other package payload difference")


def measure(path, original=False):
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != 1:
            raise ValueError("Page count")
        page = pdf.pages[0]
        vertical = [o for o in page.lines if abs(o["x1"] - o["x0"]) < 0.01 and o["bottom"] - o["top"] > 90]
        x = sorted({round(o["x0"], 4) for o in vertical})
        if len(x) != 5:
            raise ValueError("Unknown vertical topology")
        top = min(o["top"] for o in vertical)
        bottom = max(o["bottom"] for o in vertical)
        horizontal = [
            o
            for o in page.lines
            if top - 0.01 <= o["top"] <= bottom + 0.01 and o["x1"] - o["x0"] > 50 and abs(o["bottom"] - o["top"]) < 0.01
        ]
        y = sorted({round(o["top"], 4) for o in horizontal})
        if len(y) != 6:
            raise ValueError("Unknown horizontal topology")
        top, bottom = y[0], y[-1]
        for line in vertical:
            col = x.index(round(line["x0"], 4))
            cap = line["linewidth"] / 2
            if abs(line["top"] - y[1 if col == 2 else 0]) > cap + 0.05 or abs(line["bottom"] - y[-1]) > cap + 0.05:
                raise ValueError("Vertical merge segment mismatch")
        for line in horizontal:
            row = y.index(round(line["top"], 4))
            lo, hi = (1, 3) if row == 1 else (0, 4)
            half = line["linewidth"] / 2
            if abs(line["x0"] - (x[lo] - half)) > 0.05 or abs(line["x1"] - (x[hi] + half)) > 0.05:
                raise ValueError("Horizontal merge segment mismatch")
        polygons = [(0, 0, 1, 2), (0, 1, 3, 1), (0, 3, 4, 2), (1, 1, 2, 2), (1, 2, 3, 2)]
        polygons += [(r, c, c + 1, r + 1) for r in range(2, 5) for c in range(4)]
        groups = [[] for _ in polygons]
        for char in page.chars:
            cx, cy = (char["x0"] + char["x1"]) / 2, (char["top"] + char["bottom"]) / 2
            if not top < cy < bottom:
                continue
            hits = [i for i, (r, lo, hi, end) in enumerate(polygons) if x[lo] < cx < x[hi] and y[r] < cy < y[end]]
            if len(hits) != 1:
                raise ValueError("Glyph assignment ambiguous")
            groups[hits[0]].append(char)
        cells = []
        for polygon, chars in zip(polygons, groups, strict=True):
            r, lo, hi, end = polygon
            if not chars or any(
                c["x0"] <= x[lo] or c["x1"] >= x[hi] or c["top"] <= y[r] or c["bottom"] >= y[end] for c in chars
            ):
                raise ValueError("Missing or crossing glyph")
            cells.append(
                {
                    "polygon": polygon,
                    "text": "".join(c["text"] for c in chars if not c["text"].isspace()),
                    "baselines": sorted({round(page.height - c["matrix"][5] - top, 4) for c in chars}),
                    "fonts": sorted({(c["fontname"].split("+")[-1], round(c["size"], 5)) for c in chars}),
                    "chars": [{k: c[k] for k in ("text", "x0", "x1", "top", "bottom", "adv", "matrix")} for c in chars],
                }
            )
        controls = (
            {}
            if original
            else {
                text: [
                    {k: w[k] for k in ("x0", "top", "x1", "bottom")} for w in page.extract_words() if w["text"] == text
                ]
                for text in ("BEFORE", "FOLLOWING")
            }
        )
        if not original and any(len(words) != 1 for words in controls.values()):
            raise ValueError("Missing control")
        return {
            "x": x,
            "y": y,
            "pitches": [round(b - a, 4) for a, b in zip(y, y[1:], strict=False)],
            "height": bottom - top,
            "cells": cells,
            "controls": controls,
        }


def baseline_gate(original, control):
    return all(abs(p - 24) <= 0.05 for p in control["pitches"]) and all(
        a["text"] == b["text"] and a["fonts"] == b["fonts"] and len(b["baselines"]) == 1
        for a, b in zip(original["cells"], control["cells"], strict=True)
    )


def compare(a, b):
    gates = {
        "rule_delta": all(
            abs((new - old) + i * 0.75) <= 0.10 for i, (old, new) in enumerate(zip(a["x"], b["x"], strict=True))
        ),
        "row_height": all(abs(old - new) <= 0.05 for old, new in zip(a["y"], b["y"], strict=True)),
        "controls": a["controls"] == b["controls"],
        "cell_text_font_line_baseline": all(
            old["text"] == new["text"]
            and old["fonts"] == new["fonts"]
            and len(new["baselines"]) == 1
            and abs(old["baselines"][0] - new["baselines"][0]) <= 0.05
            for old, new in zip(a["cells"], b["cells"], strict=True)
        ),
    }
    return {"gates": gates, "accepted": all(gates.values()), "product_safety": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--export-wps", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    manifest = {
        "base": "ab3b548667cabbe8b09b59cc181ffd88b523b2db",
        "source_sha256": EXPECTED,
        "exports": [],
        "not_run": ["C1", "C0"],
    }
    for name in ("C1", "C0"):
        folder = args.out / name
        folder.mkdir()
        build(folder / "input.docx", zero=name == "C0")
    write(args.out / "manifest.json", manifest)
    if not args.export_wps:
        return
    measurements = {}
    original = measure(BASE / "wps.pdf", original=True)
    for name in ("C1", "C0"):
        folder = args.out / name
        raw, state = probe_wps()
        write(folder / "probe.json", raw)
        if (
            state is None
            or state.get("processes")
            or not any(v.get("file_version") == "12,8,2,18913" for v in state.get("executables", []))
        ):
            manifest["stop"] = "UNSAFE_OR_VERSION"
            break
        manifest["versions"] = state["executables"]
        result = wps_convert((folder / "input.docx").resolve(), (folder / "wps.pdf").resolve(), timeout_seconds=120)
        write(folder / "export.json", result)
        manifest["exports"].append(name)
        manifest["not_run"].remove(name)
        write(args.out / "manifest.json", manifest)
        if not result[0]:
            manifest["stop"] = "EXPORT_FAILED"
            break
        color_pages(folder / "wps.pdf", folder, "wps-page")
        measurements[name] = measure(folder / "wps.pdf")
        write(folder / "measurement.json", measurements[name])
        if name == "C1" and not baseline_gate(original, measurements[name]):
            manifest["stop"] = "CONTROL_MISMATCH"
            break
    if len(measurements) == 2:
        acceptance = compare(measurements["C1"], measurements["C0"])
        write(args.out / "acceptance.json", acceptance)
        manifest["outcome"] = "PASS_MECHANISM_ONLY" if acceptance["accepted"] else "STOP"
    manifest["hashes"] = {
        p.relative_to(args.out).as_posix(): sha(p)
        for p in sorted(args.out.rglob("*"))
        if p.is_file() and p.name != "manifest.json"
    }
    write(args.out / "manifest.json", manifest)
    print(manifest)


if __name__ == "__main__":
    main()
