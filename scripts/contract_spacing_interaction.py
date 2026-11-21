"""Stage48 two-spacing-attribute contract interaction experiment; no product changes."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from paragraph_mark_font_mechanism import sha, write  # noqa:E402
from table_width_environment import environment_gate, restore_snapshot, semantic_pass, semantic_snapshot  # noqa:E402

BASE = ROOT / "artifacts/natural-merged-rows-20261121/A-contract-docx"
SOURCE = ROOT / "artifacts/schema-table-width-20261121/A-contract-docx/input/contract.html"
EXPECTED = "2b5e206fb74d5a73b036ab8a8e4b01b6dc98d5818599cfbabdb28579bdd0aefa"
SOURCE_PDF = SOURCE.parents[1] / "browser.pdf"


def patch_xml(source):
    from lxml import etree as ET

    w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    root = ET.fromstring(source)
    targets = []
    for paragraph in root.find(w + "body").findall(w + "p"):
        text = "".join(paragraph.itertext())
        if text not in ("第三条 保密", "第四条 违约责任"):
            continue
        prop = paragraph.find(w + "pPr")
        if prop.find(w + "pStyle").get(w + "val") != "Heading2":
            raise ValueError("Unexpected heading style")
        spacing = prop.find(w + "spacing")
        expected = {w + k: v for k, v in {"lineRule": "exact", "line": "495", "before": "54", "after": "274"}.items()}
        if spacing is None or dict(spacing.attrib) != expected:
            raise ValueError("Unexpected heading spacing")
        targets.append(spacing)
    if len(targets) != 2:
        raise ValueError("Wrong target count")
    for target in targets:
        target.set(w + "before", "274")
    result = ET.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True)
    for target in targets:
        target.set(w + "before", "54")
    if ET.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True) != source:
        raise ValueError("Inverse does not restore original XML")
    return result


def pdf_measure(path):
    import numpy as np
    import pdfplumber

    from wps_ai_agent_cli.fidelity import _pdf_pages

    image = np.asarray(_pdf_pages(path, 800)[0])
    scale = 800 / 595.92
    with pdfplumber.open(path) as document:
        if len(document.pages) != 1:
            raise ValueError("Page count changed")
        page = document.pages[0]
        anchors = {}
        for prefix in ("合同总价", "第三条", "双方对", "第四条", "任何一方", "甲方（盖章）", "日期："):
            lines = [line for line in page.extract_text_lines() if line["text"].startswith(prefix)]
            if len(lines) != 1:
                raise ValueError(f"Ambiguous anchor {prefix}")
            line = lines[0]
            char = line["chars"][0]
            x0, x1 = int(char["x0"] * scale), int((char["x0"] + char["size"]) * scale) + 1
            y0, y1 = int((line["top"] - 2) * scale), int((line["bottom"] + 2) * scale) + 1
            ink = np.flatnonzero((image[y0:y1, x0:x1] < 160).any(axis=1))
            if not len(ink):
                raise ValueError("Missing anchor ink")
            anchors[prefix] = {
                "top": line["top"],
                "baseline": page.height - char["matrix"][5],
                "ink": [int(ink.min() + y0), int(ink.max() + y0)],
            }
        chars = [
            {
                "text": c["text"],
                "x": c["x0"],
                "top": c["top"],
                "baseline": page.height - c["matrix"][5],
                "size": c["size"],
                "advance": c["adv"],
                "font": c["fontname"].split("+")[-1],
            }
            for c in page.chars
        ]
        return {"anchors": anchors, "chars": chars, "lines": [line["text"] for line in page.extract_text_lines()]}


def classify(gates, scores, zero):
    conserved = all(
        v
        for k, v in gates.items()
        if k not in ("transfer", "all_stream_flow", "ink_improvement", "raster_changed", "heading_interval")
    )
    if zero and conserved:
        return "ZERO_INFLUENCE"
    score_gate = all(scores[k][1] > scores[k][0] for k in ("stage12_region", "later", "whole"))
    return "PASS_MECHANISM_ONLY" if all(gates.values()) and score_gate else "STOP"


def assess(pdf):
    import numpy as np
    import pypdfium2 as pdfium
    from copied_contract_wrap_mechanism import measure
    from PIL import ImageChops

    from wps_ai_agent_cli.fidelity import _pdf_pages, ssim

    old, new, source = (pdf_measure(p) for p in (BASE / "wps.pdf", pdf, SOURCE_PDF))
    oldtable, newtable = (measure(p, original=True) for p in (BASE / "wps.pdf", pdf))
    pairs = list(zip(old["chars"], new["chars"], strict=True))
    shifts = {}
    predictions = {
        "合同总价": 0,
        "第三条": 2.76,
        "双方对": 2.76,
        "第四条": 5.4,
        "任何一方": 5.4,
        "甲方（盖章）": 5.4,
        "日期：": 5.4,
    }
    for key in predictions:
        shifts[key] = {field: new["anchors"][key][field] - old["anchors"][key][field] for field in ("top", "baseline")}
    gates = {
        "transfer": all(
            abs(v - predictions[key]) <= (0.05 if predictions[key] == 0 else 0.15)
            for key, values in shifts.items()
            for v in values.values()
        ),
        "heading_interval": abs(new["anchors"]["第四条"]["top"] - new["anchors"]["第三条"]["top"] - 68.64) <= 0.15,
        "text_lines_font_x": old["lines"] == new["lines"]
        and all(
            a["text"] == b["text"]
            and a["font"] == b["font"]
            and abs(a["size"] - b["size"]) <= 0.005
            and abs(a["x"] - b["x"]) <= 0.05
            and abs(a["advance"] - b["advance"]) <= 0.05
            for a, b in pairs
        ),
        "table_complete": oldtable == newtable,
        "all_stream_flow": all(
            abs(
                b["baseline"]
                - a["baseline"]
                - (
                    0
                    if a["baseline"] < old["anchors"]["第三条"]["baseline"] - 0.05
                    else 2.76
                    if a["baseline"] < old["anchors"]["第四条"]["baseline"] - 0.05
                    else 5.4
                )
            )
            <= (0.05 if a["baseline"] < old["anchors"]["第三条"]["baseline"] - 0.05 else 0.15)
            for a, b in pairs
        ),
    }
    reference = _pdf_pages(SOURCE_PDF, 800)[0]
    images = [_pdf_pages(p, 800)[0].resize(reference.size) for p in (BASE / "wps.pdf", pdf)]
    scores = {}
    boxes = {"stage12_region": (40, 640, 765, 825)}
    for name, lo, hi in (("header", 348, 395), ("body", 395, 470), ("table", 348, 470), ("later", 470, 640)):
        boxes[name] = (30, int(lo * 800 / 595.92), 770, int(hi * 800 / 595.92))
    for name, box in boxes.items():
        scores[name] = [float(ssim(np.asarray(reference.crop(box)), np.asarray(im.crop(box)))) for im in images]
    scores["whole"] = [float(ssim(np.asarray(reference), np.asarray(im))) for im in images]
    gates["fixed_baseline_scores"] = (
        abs(scores["whole"][0] - 0.8950000618741911) <= 1e-9 and abs(scores["later"][0] - 0.7641768045298025) <= 1e-9
    )
    gates["table_pixels"] = all(
        ImageChops.difference(*(im.crop(boxes[k]) for im in images)).getbbox() is None
        for k in ("header", "body", "table")
    )
    before_box = (0, 0, reference.width, int(510 * 800 / 595.92))
    gates["before_pixels"] = ImageChops.difference(*(im.crop(before_box) for im in images)).getbbox() is None
    gates["price_ink"] = new["anchors"]["合同总价"]["ink"] == old["anchors"]["合同总价"]["ink"] == [645, 658]
    ink_errors = {
        k: {
            label: sum(record["anchors"][k]["ink"]) / 2 - sum(source["anchors"][k]["ink"]) / 2
            for label, record in (("before", old), ("after", new))
        }
        for k in predictions
    }
    gates["ink_improvement"] = all(
        abs(ink_errors[k]["after"]) < abs(ink_errors[k]["before"]) for k in ("双方对", "第四条", "任何一方")
    )
    rgb = []
    for path in (BASE / "wps.pdf", pdf):
        with pdfium.PdfDocument(str(path)) as document:
            rgb.append(document[0].render(scale=800 / document[0].get_width()).to_pil().convert("RGB"))
    zero = ImageChops.difference(*rgb).getbbox() is None and old == new
    gates["table_pixels"] &= all(
        ImageChops.difference(*(im.crop(boxes[k]) for im in rgb)).getbbox() is None for k in ("header", "body", "table")
    )
    gates["before_pixels"] &= ImageChops.difference(*(im.crop(before_box) for im in rgb)).getbbox() is None
    gates["raster_changed"] = ImageChops.difference(*rgb).getbbox() is not None
    return {
        "baseline": old,
        "candidate": new,
        "source": source,
        "shifts": shifts,
        "ink_errors": ink_errors,
        "scores": scores,
        "gates": gates,
        "outcome": classify(gates, scores, zero),
        "strict_f2": scores["whole"][1] >= 0.9,
    }


def build(target):
    source = BASE / "candidate.docx"
    if sha(source) != EXPECTED:
        raise ValueError("Immutable Stage44 contract mismatch")
    with ZipFile(source) as old, ZipFile(target, "w") as new:
        for info in old.infolist():
            data = old.read(info.filename)
            new.writestr(copy.copy(info), patch_xml(data) if info.filename == "word/document.xml" else data)
    with ZipFile(source) as old, ZipFile(target) as new:
        if old.namelist() != new.namelist() or old.comment != new.comment:
            raise ValueError("Package members/comment changed")
        for a, b in zip(old.infolist(), new.infolist(), strict=True):
            if (a.filename, a.date_time, a.compress_type, a.external_attr, a.extra, a.comment) != (
                b.filename,
                b.date_time,
                b.compress_type,
                b.external_attr,
                b.extra,
                b.comment,
            ):
                raise ValueError("Package metadata changed")
        if any(old.read(n) != new.read(n) for n in old.namelist() if n != "word/document.xml"):
            raise ValueError("Other package payload changed")


def preflight(out):
    out.mkdir(parents=True, exist_ok=False)
    write(out / "environment.json", environment_gate(ROOT))
    target = out / "candidate.docx"
    build(target)
    second = out / "determinism.docx"
    build(second)
    if target.read_bytes() != second.read_bytes():
        raise ValueError("Nondeterministic candidate")
    second.unlink()
    snapshot = json.loads((BASE / "browser-styles.json").read_text(encoding="utf-8"))
    styled = restore_snapshot(SOURCE, snapshot)
    semantic = {"baseline": semantic_snapshot(SOURCE, BASE / "candidate.docx", styled)}
    semantic["candidate"] = semantic_snapshot(SOURCE, target, styled)
    write(out / "semantics.json", semantic)
    if not all(semantic_pass(value) for value in semantic.values()):
        raise ValueError("Snapshot semantics not perfect")
    control = assess(BASE / "wps.pdf")
    if control["outcome"] != "ZERO_INFLUENCE":
        raise ValueError("Baseline read-only control failed")
    write(out / "baseline-control.json", {"scores": control["scores"], "anchors": control["baseline"]["anchors"]})
    write(
        out / "preflight.json",
        {
            "base": "dfebac646eb75ab4219c281032dd6ce6641c6f1c",
            "outcome": "OFFLINE_PASS_AWAITING_PRIMARY_REVIEW",
            "baseline_sha256": sha(BASE / "candidate.docx"),
            "candidate_sha256": sha(target),
            "source_sha256": sha(SOURCE),
            "snapshot_sha256": sha(BASE / "browser-styles.json"),
            "baseline_pdf_sha256": sha(BASE / "wps.pdf"),
            "source_pdf_sha256": sha(SOURCE_PDF),
            "allowlist": "two Heading2 before54->274; exact2 attributes inverse",
            "deterministic": True,
            "other_parts_and_metadata_identical": True,
            "baseline_candidate_semantics": True,
            "wps_exports": 0,
        },
    )


def export_once(out):
    from html_docx_wps_matrix import color_pages, probe_wps

    from wps_ai_agent_cli.wps_convert import wps_convert

    manifest_path = out / "export-manifest.json"
    if manifest_path.exists():
        raise ValueError("This experiment was already attempted; no retry")
    pre = json.loads((out / "preflight.json").read_text(encoding="utf-8"))
    if pre["outcome"] != "OFFLINE_PASS_AWAITING_PRIMARY_REVIEW" or pre["wps_exports"] != 0:
        raise ValueError("Offline preflight not accepted")
    if sha(BASE / "candidate.docx") != EXPECTED or sha(out / "candidate.docx") != pre["candidate_sha256"]:
        raise ValueError("WPS input changed")
    if sha(SOURCE) != pre["source_sha256"] or sha(BASE / "browser-styles.json") != pre["snapshot_sha256"]:
        raise ValueError("Source/snapshot changed")
    if sha(BASE / "wps.pdf") != pre["baseline_pdf_sha256"] or sha(SOURCE_PDF) != pre["source_pdf_sha256"]:
        raise ValueError("Immutable source/baseline PDF changed")
    manifest = {"wps_exports": 0, "candidate_sha256": pre["candidate_sha256"], "outcome": "ATTEMPT_STARTED"}
    write(manifest_path, manifest)
    try:
        write(out / "export-environment.json", environment_gate(ROOT))
        styled = restore_snapshot(SOURCE, json.loads((BASE / "browser-styles.json").read_text(encoding="utf-8")))
        semantic = {
            k: semantic_snapshot(SOURCE, p, styled)
            for k, p in (("baseline", BASE / "candidate.docx"), ("candidate", out / "candidate.docx"))
        }
        write(out / "export-semantics.json", semantic)
        if not all(semantic_pass(r) for r in semantic.values()):
            raise ValueError("Semantic pre-export gate failed")
        raw, state = probe_wps()
        write(out / "probe.json", raw)
        if (
            state is None
            or state.get("processes") != []
            or not any(v.get("file_version") == "12,8,2,18913" for v in state.get("executables", []))
        ):
            raise ValueError("Unsafe process state or WPS version")
        manifest["versions"] = state["executables"]
        manifest["wps_exports"] = 1
        write(manifest_path, manifest)
        result = wps_convert((out / "candidate.docx").resolve(), (out / "wps.pdf").resolve(), timeout_seconds=120)
        write(out / "export.json", result)
        if not result[0]:
            raise ValueError("Single export failed")
        color_pages(out / "wps.pdf", out, "wps-page")
        assessed = assess(out / "wps.pdf")
        assessed["semantic"] = semantic
        write(out / "acceptance.json", assessed)
        manifest["outcome"] = assessed["outcome"]
    except Exception as error:
        manifest.update(outcome="STOP", error=f"{type(error).__name__}: {error}")
    manifest["hashes"] = {
        p.relative_to(out).as_posix(): sha(p) for p in sorted(out.rglob("*")) if p.is_file() and p != manifest_path
    }
    write(manifest_path, manifest)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--export-wps", action="store_true")
    args = parser.parse_args()
    export_once(args.out) if args.export_wps else preflight(args.out)
