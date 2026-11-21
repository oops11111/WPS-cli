"""Stage43 single AT_LEAST row-minimum experiment; no converter changes."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from zipfile import ZipFile

from lxml import etree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from copied_contract_wrap_mechanism import W, measure  # noqa:E402
from html_docx_wps_matrix import color_pages, probe_wps  # noqa:E402
from measured_table_wps_validation import chars  # noqa:E402
from paragraph_mark_font_mechanism import sha, write  # noqa:E402
from table_width_environment import environment_gate, restore_snapshot, semantic_pass, semantic_snapshot  # noqa:E402

from wps_ai_agent_cli.wps_convert import wps_convert  # noqa:E402

BASE = ROOT / "artifacts/schema-table-width-20261121/A-contract-docx"
EXPECTED = "760bb182bf74f3b491ed103f8d56fc5089d99f1c22bf4ff6f8226fcd1d1dbab1"


def serialize(root):
    return ET.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True)


def patch_xml(source):
    root = ET.fromstring(source)
    tables = root.find(W + "body").findall(W + "tbl")
    if len(tables) != 3:
        raise ValueError("Wrong table topology")
    rows = tables[1].findall(W + "tr")
    if len(rows) != 5:
        raise ValueError("Wrong row count")
    heights = []
    for ri, row in enumerate(rows):
        height = row.find(W + "trPr/" + W + "trHeight")
        if height is None or dict(height.attrib) != {W + "val": "465", W + "hRule": "atLeast"}:
            raise ValueError("Wrong row height/rule")
        cells = row.findall(W + "tc")
        if len(cells) != (3 if ri == 0 else 4):
            raise ValueError("Wrong cell topology")
        for ci, cell in enumerate(cells):
            if ri == 1 and ci in (0, 3):
                continue
            p = cell.find(W + "p/" + W + "pPr/" + W + "spacing")
            line = "390" if ri == 0 and ci in (0, 2) else "330"
            expected = {W + k: v for k, v in {"line": line, "lineRule": "exact", "before": "60", "after": "45"}.items()}
            if p is None or dict(p.attrib) != expected:
                raise ValueError("Unexpected paragraph content constraint")
        heights.append(height)
    for height in heights:
        height.set(W + "val", "450")
    result = serialize(root)
    for height in heights:
        height.set(W + "val", "465")
    if serialize(root) != source:
        raise ValueError("Inverse does not restore full XML bytes")
    return result


def build(target):
    source = BASE / "candidate.docx"
    if sha(source) != EXPECTED:
        raise ValueError("Immutable current-contract hash mismatch")
    with ZipFile(source) as old, ZipFile(target, "w") as new:
        for info in old.infolist():
            data = old.read(info.filename)
            new.writestr(copy.copy(info), patch_xml(data) if info.filename == "word/document.xml" else data)
    with ZipFile(source) as old, ZipFile(target) as new:
        if any(old.read(n) != new.read(n) for n in old.namelist() if n != "word/document.xml"):
            raise ValueError("Other ZIP part changed")


def anchors(path):
    import pdfplumber

    with pdfplumber.open(path) as document:
        page = document.pages[0]
        result = {}
        for prefix in ("合同总价", "第三条", "双方对", "第四条", "任何一方"):
            hits = [line for line in page.extract_text_lines() if line["text"].startswith(prefix)]
            if len(hits) != 1:
                raise ValueError("Ambiguous downstream anchor")
            result[prefix] = page.height - hits[0]["chars"][0]["matrix"][5]
        return result


def row_prediction(new):
    expected_y = [347.81, 371.06, 394.31, 417.56, 440.81, 464.06]
    return {
        "row_centers": all(abs(a - b) <= 0.10 for a, b in zip(new["y"], expected_y, strict=True)),
        "row_pitches": all(abs(b - a - 23.25) <= 0.05 for a, b in zip(new["y"], new["y"][1:], strict=False)),
        "table_top_height": abs(new["y"][0] - 347.81) <= 0.05 and abs(new["height"] - 116.25) <= 0.10,
    }


def assess(pdf):
    import numpy as np
    from PIL import ImageChops

    from wps_ai_agent_cli.fidelity import _pdf_pages, ssim

    old, new = (measure(p, original=True) for p in (BASE / "wps.pdf", pdf))
    pairs = list(zip(chars(BASE / "wps.pdf"), chars(pdf), strict=True))
    gates = {
        **row_prediction(new),
        "rule_x": all(abs(a - b) <= 0.05 for a, b in zip(old["x"], new["x"], strict=True)),
        "all_text_page_font_x": all(
            a["text"] == b["text"]
            and a["page"] == b["page"]
            and a["font"] == b["font"]
            and abs(a["size"] - b["size"]) <= 0.005
            and abs(a["x"] - b["x"]) <= 0.05
            for a, b in pairs
        ),
        "before_flow": all(abs(a["y"] - b["y"]) <= 0.05 for a, b in pairs if a["y"] < old["y"][0]),
        "after_flow": all(abs(b["y"] - a["y"] + 3.75) <= 0.10 for a, b in pairs if a["y"] > old["y"][-1]),
    }
    shifts = []
    for a, b in zip(old["cells"], new["cells"], strict=True):
        r, lo, hi, end = a["polygon"]
        expected = -(r + end) / 2 * 0.75
        shift = b["baselines"][0] - a["baselines"][0]
        shifts.append({"polygon": a["polygon"], "expected": expected, "actual": shift})
    gates["cell_baselines"] = all(abs(s["actual"] - s["expected"]) <= 0.10 for s in shifts)
    gates["origin_text_font_singleline"] = all(
        a["text"] == b["text"] and a["fonts"] == b["fonts"] and len(b["baselines"]) == 1
        for a, b in zip(old["cells"], new["cells"], strict=True)
    )
    gates["ink_height_advances"] = all(
        abs((a["bottom"] - a["top"]) - (b["bottom"] - b["top"])) <= 0.005 and abs(a["adv"] - b["adv"]) <= 0.005
        for ca, cb in zip(old["cells"], new["cells"], strict=True)
        for a, b in zip(ca["chars"], cb["chars"], strict=True)
    )
    oldanchors, newanchors, sourceanchors = (anchors(p) for p in (BASE / "wps.pdf", pdf, BASE / "browser.pdf"))
    errors = {
        k: {"before": oldanchors[k] - sourceanchors[k], "after": newanchors[k] - sourceanchors[k]}
        for k in sourceanchors
    }
    keys = list(oldanchors)
    gates["downstream_intervals"] = all(
        abs((newanchors[b] - newanchors[a]) - (oldanchors[b] - oldanchors[a])) <= 0.05
        for a, b in zip(keys, keys[1:], strict=False)
    )
    gates["price_error"] = abs(errors["合同总价"]["before"]) - abs(errors["合同总价"]["after"]) >= 3
    source = _pdf_pages(BASE / "browser.pdf", 800)[0]
    oldimage, newimage = (_pdf_pages(p, 800)[0].resize(source.size) for p in (BASE / "wps.pdf", pdf))
    scores = {}
    for name, lo, hi in (("body", 395, 470), ("header", 348, 395), ("table", 348, 470), ("later", 470, 640)):
        box = (30, int(lo * 800 / 595.92), 770, int(hi * 800 / 595.92))
        scores[name] = [ssim(np.asarray(source.crop(box)), np.asarray(t.crop(box))) for t in (oldimage, newimage)]
    scores["whole"] = [ssim(np.asarray(source), np.asarray(t)) for t in (oldimage, newimage)]
    gates["body_table_gain"] = all(scores[k][1] > scores[k][0] for k in ("body", "table"))
    gates["header_later_no_regression"] = all(scores[k][1] >= scores[k][0] - 1e-9 for k in ("header", "later"))
    gates["whole_gain"] = round(scores["whole"][1], 4) > 0.8719
    zero = ImageChops.difference(oldimage, newimage).getbbox() is None and old == new
    return {
        "baseline": old,
        "candidate": new,
        "shifts": shifts,
        "anchors": errors,
        "scores": scores,
        "gates": gates,
        "outcome": "ZERO_INFLUENCE" if zero else "PASS_MECHANISM" if all(gates.values()) else "STOP",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--export-wps", action="store_true")
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    target = args.out / "candidate.docx"
    build(target)
    snapshot = json.loads((BASE / "browser-styles.json").read_text(encoding="utf-8"))
    active = -1
    source_rows = []
    for element in snapshot["elements"]:
        if element["tag"] == "table":
            active += 1
        if active == 1 and element["tag"] == "tr":
            source_rows.append(element["box"]["height"])
    if source_rows != [31] * 5:
        raise ValueError("Source natural row-box formula mismatch")
    write(
        args.out / "source-constraints.json",
        {
            "row_boxes_px": source_rows,
            "derived_min_twips": [(h - 1) * 15 for h in source_rows],
            "body_line_before_after_twips": [330, 60, 45],
            "rowspan_line_twips": 390,
            "content_minimum_uncertain": True,
        },
    )
    source = BASE / "input/contract.html"
    styled = restore_snapshot(source, snapshot)
    semantic = {
        name: semantic_snapshot(source, path, styled)
        for name, path in (("baseline", BASE / "candidate.docx"), ("candidate", target))
    }
    write(args.out / "semantic-preflight.json", semantic)
    if not all(semantic_pass(r) for r in semantic.values()):
        raise ValueError("Semantic preflight failed")
    env = environment_gate(ROOT)
    write(args.out / "environment.json", env)
    manifest = {
        "base": "551fe7fad79d6b96423caca73e816b4ab35aebc7",
        "input_sha256": EXPECTED,
        "candidate_sha256": sha(target),
        "offline_gate": "5attr inverse/parts and content constraints passed",
        "wps_exports": 0,
    }
    write(args.out / "manifest.json", manifest)
    if not args.export_wps:
        return
    raw, state = probe_wps()
    write(args.out / "probe.json", raw)
    if (
        state is None
        or state.get("processes")
        or not any(v.get("file_version") == "12,8,2,18913" for v in state.get("executables", []))
    ):
        manifest["stop"] = "UNSAFE_OR_VERSION"
        write(args.out / "manifest.json", manifest)
        return
    manifest["versions"] = state["executables"]
    pdf = args.out / "wps.pdf"
    result = wps_convert(target.resolve(), pdf.resolve(), timeout_seconds=120)
    write(args.out / "export.json", result)
    manifest["wps_exports"] = 1
    write(args.out / "manifest.json", manifest)
    if not result[0]:
        raise RuntimeError("Single export failed; STOP")
    color_pages(pdf, args.out, "wps-page")
    result = assess(pdf)
    result["semantic"] = semantic
    write(args.out / "acceptance.json", result)
    manifest["outcome"] = result["outcome"]
    manifest["hashes"] = {
        f.relative_to(args.out).as_posix(): sha(f)
        for f in sorted(args.out.rglob("*"))
        if f.is_file() and f.name != "manifest.json"
    }
    write(args.out / "manifest.json", manifest)
    print({k: result[k] for k in ("outcome", "gates", "scores", "anchors")})


if __name__ == "__main__":
    main()
