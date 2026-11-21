"""Stage38 single full-contract width candidate; no product edits."""

from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path
from zipfile import ZipFile

from lxml import etree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from copied_contract_wrap_mechanism import BASE, EXPECTED, W, measure, sha, write  # noqa:E402
from copied_contract_wrap_mechanism import patch_xml as patch_control  # noqa:E402
from html_docx_wps_matrix import color_pages, probe_wps  # noqa:E402

from wps_ai_agent_cli.wps_convert import wps_convert  # noqa:E402

COPIED = ROOT / "artifacts/copied-contract-wrap-20261121/C0/input.docx"


def serialize(root):
    return ET.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True)


def patch_xml(source):
    root = ET.fromstring(source)
    body = root.find(W + "body")
    tables = body.findall(W + "tbl")
    if len(tables) != 3:
        raise ValueError("Unexpected complete-document topology")
    scratch = copy.deepcopy(root)
    sb = scratch.find(W + "body")
    st = sb.findall(W + "tbl")
    sb.remove(st[0])
    sb.remove(st[2])
    candidate = ET.fromstring(patch_control(serialize(scratch))).find(W + "body/" + W + "tbl")
    body.replace(tables[1], copy.deepcopy(candidate))
    result = serialize(root)
    old = ET.fromstring(source)
    count = 0
    for a, b in zip(old.iter(), root.iter(), strict=True):
        if a.tag != b.tag or a.text != b.text or a.tail != b.tail:
            raise ValueError("Non-attribute difference")
        if a.attrib != b.attrib:
            if set(a.attrib) != set(b.attrib) or a.get(W + "w") != str(int(b.get(W + "w")) + 15):
                raise ValueError("Unexpected attribute difference")
            b.attrib.update(a.attrib)
            count += 1
    if count != 21 or serialize(root) != source:
        raise ValueError("Exact inverse failed")
    with ZipFile(COPIED) as z:
        copied = ET.fromstring(z.read("word/document.xml")).find(W + "body/" + W + "tbl")
    if ET.tostring(candidate, method="c14n") != ET.tostring(copied, method="c14n"):
        raise ValueError("Not the verified Stage37 C0 table")
    return result


def build(target):
    source = BASE / "converted.docx"
    if sha(source) != EXPECTED:
        raise ValueError("Immutable source mismatch")
    with ZipFile(source) as old, ZipFile(target, "w") as new:
        for info in old.infolist():
            data = old.read(info.filename)
            new.writestr(copy.copy(info), patch_xml(data) if info.filename == "word/document.xml" else data)
    with ZipFile(source) as old, ZipFile(target) as new:
        if old.namelist() != new.namelist() or any(
            old.read(n) != new.read(n) for n in old.namelist() if n != "word/document.xml"
        ):
            raise ValueError("Other package difference")


def all_chars(path):
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != 1:
            raise ValueError("Changed page count")
        return [
            {"text": c["text"], "x": c["x0"], "y": c["top"], "font": c["fontname"].split("+")[-1], "size": c["size"]}
            for c in pdf.pages[0].chars
        ]


def score_gates(scores):
    return {
        "roi_body_table": all(scores[k][1] > scores[k][0] for k in ("body", "table")),
        "roi_header": scores["header"][1] >= scores["header"][0] - 1e-9,
        "whole": round(scores["whole"][1], 4) > 0.8644,
    }


def assess(pdf):
    import numpy as np

    from wps_ai_agent_cli.fidelity import _pdf_pages, _save_pairs, fidelity_check, ssim

    old, new = (measure(p, original=True) for p in (BASE / "wps.pdf", pdf))
    source_edges = [34.125, 68.625, 104.625, 172.125, 307.875]
    predictions = [33.75, 68.50, 103.95, 171.70, 307.40]
    before_errors = [abs(a - s) for a, s in zip(old["x"], source_edges, strict=True)]
    after_errors = [abs(a - s) for a, s in zip(new["x"], source_edges, strict=True)]
    chars = list(zip(all_chars(BASE / "wps.pdf"), all_chars(pdf), strict=True))
    gates = {
        "rule_prediction": all(abs(a - b) <= 0.10 for a, b in zip(new["x"], predictions, strict=True)),
        "source_edge_error": all(b <= a + 0.05 for a, b in zip(before_errors, after_errors, strict=True))
        and sum(after_errors) < sum(before_errors),
        "row_geometry": all(abs(a - b) <= 0.05 for a, b in zip(old["y"], new["y"], strict=True)),
        "origins_text_font_line": all(
            a["text"] == b["text"]
            and a["fonts"] == b["fonts"]
            and len(b["baselines"]) == 1
            and abs(a["baselines"][0] - b["baselines"][0]) <= 0.05
            for a, b in zip(old["cells"], new["cells"], strict=True)
        ),
        "all_text_font_y": all(
            a["text"] == b["text"]
            and a["font"] == b["font"]
            and abs(a["size"] - b["size"]) <= 0.005
            and abs(a["y"] - b["y"]) <= 0.05
            for a, b in chars
        ),
        "outside_table_x": all(
            abs(a["x"] - b["x"]) <= 0.05 for a, b in chars if not (347.81 < a["y"] < 467.81 and 33.75 < a["x"] < 310.4)
        ),
    }
    source = _pdf_pages(BASE / "browser.pdf", 800)[0]
    targets = [_pdf_pages(p, 800)[0].resize(source.size) for p in (BASE / "wps.pdf", pdf)]
    scores = {}
    for name, lo, hi in (("body", 395, 470), ("header", 348, 395), ("table", 348, 470)):
        box = (30, int(lo * 800 / 595.92), 770, int(hi * 800 / 595.92))
        scores[name] = [ssim(np.asarray(source.crop(box)), np.asarray(t.crop(box))) for t in targets]
    scores["whole"] = [ssim(np.asarray(source), np.asarray(t)) for t in targets]
    _save_pairs([source], [targets[1]], pdf.parent / "pages", [scores["whole"][1]])
    gates.update(score_gates(scores))
    semantic = fidelity_check(BASE / "input/contract.html", pdf.parent / "candidate.docx", layout=False)
    gates["semantics"] = semantic[0] and all(semantic[1]["verdict"].values())
    return {
        "baseline": old,
        "candidate": new,
        "source_edge_errors": [before_errors, after_errors],
        "scores": scores,
        "semantic": semantic,
        "gates": gates,
        "accepted": all(gates.values()),
        "product_safety": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--export-wps", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    target = args.out / "candidate.docx"
    build(target)
    manifest = {
        "base": "3ddbc9197753f53d8e1101ef93bdfefc42bcb4ce",
        "sources": {n: sha(BASE / n) for n in ("converted.docx", "wps.pdf", "browser.pdf")},
        "candidate_sha256": sha(target),
        "offline_gate": "21 attrs, full inverse/parts, Stage37 C0 subtree identical",
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
    exported = wps_convert(target.resolve(), pdf.resolve(), timeout_seconds=120)
    write(args.out / "export.json", exported)
    manifest["wps_exports"] = 1
    write(args.out / "manifest.json", manifest)
    if not exported[0]:
        raise RuntimeError("Export failure: STOP, no retry")
    color_pages(pdf, args.out, "wps-page")
    result = assess(pdf)
    write(args.out / "acceptance.json", result)
    manifest["outcome"] = "PASS_FULL_CONTRACT_ONLY" if result["accepted"] else "STOP"
    manifest["hashes"] = {
        p.relative_to(args.out).as_posix(): sha(p)
        for p in sorted(args.out.rglob("*"))
        if p.is_file() and p.name != "manifest.json"
    }
    write(args.out / "manifest.json", manifest)
    print({"outcome": manifest["outcome"], "gates": result["gates"], "scores": result["scores"]})


if __name__ == "__main__":
    main()
