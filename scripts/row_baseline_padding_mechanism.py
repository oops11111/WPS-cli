"""Stage45 offline fixed-total padding candidate on the accepted natural-row baseline."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from padding_distribution_mechanism import patch_xml  # noqa:E402
from paragraph_mark_font_mechanism import geometry, sha, write  # noqa:E402
from table_width_environment import environment_gate, restore_snapshot, semantic_pass, semantic_snapshot  # noqa:E402

BASE = ROOT / "artifacts/natural-merged-rows-20261121/A-contract-docx"
SOURCE = ROOT / "artifacts/schema-table-width-20261121/A-contract-docx/input/contract.html"
EXPECTED = "2b5e206fb74d5a73b036ab8a8e4b01b6dc98d5818599cfbabdb28579bdd0aefa"
SOURCE_PDF = SOURCE.parents[1] / "browser.pdf"


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


def classify(shifts, old_errors, new_errors, scores, conserved, zero=False):
    if zero and conserved:
        return "ZERO_INFLUENCE"
    predicted = len(shifts) == 3 and all(abs(s + 0.35) <= 0.05 for s in shifts)
    uniform = bool(shifts) and max(shifts) - min(shifts) <= 0.05
    gain = len(old_errors) == len(new_errors) == 3 and all(
        abs(a) - abs(b) >= 0.25 for a, b in zip(old_errors, new_errors, strict=True)
    )
    score_gate = scores["body"][1] > scores["body"][0] and scores["whole"][1] > scores["whole"][0]
    score_gate &= all(scores[k][1] >= scores[k][0] for k in ("header", "table", "later"))
    return "PASS_MECHANISM_ONLY" if conserved and predicted and uniform and gain and score_gate else "STOP"


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
    write(
        out / "preflight.json",
        {
            "base": "1ac049f87a286342e1162af59e69c0a00d9c5d2f",
            "outcome": "OFFLINE_PASS_AWAITING_PRIMARY_REVIEW",
            "baseline_sha256": sha(BASE / "candidate.docx"),
            "candidate_sha256": sha(target),
            "source_sha256": sha(SOURCE),
            "snapshot_sha256": sha(BASE / "browser-styles.json"),
            "allowlist": "12 body paragraphs: before60->53 and after45->52, sum105; exact24 attributes inverse",
            "deterministic": True,
            "other_parts_and_metadata_identical": True,
            "baseline_candidate_semantics": True,
            "wps_exports": 0,
        },
    )


def assess(pdf):
    import numpy as np
    from contract_row_minimum_mechanism import anchors
    from copied_contract_wrap_mechanism import measure
    from PIL import ImageChops

    from wps_ai_agent_cli.fidelity import _pdf_pages, ssim

    old, new, source = (geometry(p) for p in (BASE / "wps.pdf", pdf, SOURCE_PDF))
    oldtable, newtable = (measure(p, original=True) for p in (BASE / "wps.pdf", pdf))
    pairs = list(zip(old["chars"], new["chars"], strict=True))
    gates = {
        "text_font_size_x": all(
            a["text"] == b["text"]
            and a["font"] == b["font"]
            and abs(a["size"] - b["size"]) <= 0.005
            and abs(a["x"] - b["x"]) <= 0.05
            for a, b in pairs
        ),
        "rules_unchanged": old["rules"] == new["rules"],
        "row_centers_pitches": all(
            abs(a - b) <= 0.05
            for key in ("x", "y", "pitches")
            for a, b in zip(oldtable[key], newtable[key], strict=True)
        ),
        "outside_body_baselines": all(
            abs(a["baseline"] - b["baseline"]) <= 0.05
            for a, b in pairs
            if not oldtable["y"][2] < a["baseline"] < oldtable["y"][-1]
        ),
        "all_origin_singlelines": all(
            a["text"] == b["text"] and a["fonts"] == b["fonts"] and len(b["baselines"]) == 1
            for a, b in zip(oldtable["cells"], newtable["cells"], strict=True)
        ),
        "glyph_advance_ink_height": all(
            a["text"] == b["text"]
            and abs(a["adv"] - b["adv"]) <= 0.05
            and abs(a["bottom"] - a["top"] - b["bottom"] + b["top"]) <= 0.05
            for ca, cb in zip(oldtable["cells"], newtable["cells"], strict=True)
            for a, b in zip(ca["chars"], cb["chars"], strict=True)
        ),
        # measure() fails closed on any glyph crossing its assigned polygon/rule.
        "polygon_glyph_clearance": True,
    }
    oldanchors, newanchors, sourceanchors = (anchors(p) for p in (BASE / "wps.pdf", pdf, SOURCE_PDF))
    gates["downstream_anchors"] = all(abs(oldanchors[k] - newanchors[k]) <= 0.05 for k in oldanchors)

    def errors(g):
        offsets = [
            v - (lo + hi) / 2
            for v, lo, hi in zip(g["baselines"], g["boundaries"][:-1], g["boundaries"][1:], strict=True)
        ]
        source_offsets = [
            v - (lo + hi) / 2
            for v, lo, hi in zip(source["baselines"], source["boundaries"][:-1], source["boundaries"][1:], strict=True)
        ]
        return [a - b for a, b in zip(offsets, source_offsets, strict=True)]

    shifts = [b - a for a, b in zip(old["baselines"], new["baselines"], strict=True)]
    reference = _pdf_pages(SOURCE_PDF, 800)[0]
    images = [_pdf_pages(p, 800)[0].resize(reference.size) for p in (BASE / "wps.pdf", pdf)]
    scores = {}
    for name, lo, hi in (("body", 395, 470), ("header", 348, 395), ("table", 348, 470), ("later", 470, 640)):
        box = (30, int(lo * 800 / 595.92), 770, int(hi * 800 / 595.92))
        scores[name] = [float(ssim(np.asarray(reference.crop(box)), np.asarray(im.crop(box)))) for im in images]
    scores["whole"] = [float(ssim(np.asarray(reference), np.asarray(im))) for im in images]
    # A mismatching cached baseline is not a license to change a registered floor.
    floors = {"body": 0.808045712, "whole": 0.895000062}
    gates["baseline_score_identity"] = all(abs(scores[k][0] - v) <= 1e-9 for k, v in floors.items())
    zero = ImageChops.difference(*images).getbbox() is None and old == new and oldtable == newtable
    return {
        "baseline": old,
        "candidate": new,
        "source": source,
        "baseline_table": oldtable,
        "candidate_table": newtable,
        "old_errors": errors(old),
        "new_errors": errors(new),
        "shifts": shifts,
        "scores": scores,
        "gates": gates,
        "pixels_identical": zero,
        "anchors": {
            k: {"before": oldanchors[k] - sourceanchors[k], "after": newanchors[k] - sourceanchors[k]}
            for k in sourceanchors
        },
        "outcome": classify(shifts, errors(old), errors(new), scores, all(gates.values()), zero),
    }


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
