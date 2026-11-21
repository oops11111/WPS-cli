"""Stage42 single original-five WPS set after completed offline preflight."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from zipfile import ZipFile

from lxml import etree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from copied_contract_wrap_mechanism import measure  # noqa:E402
from html_docx_wps_matrix import color_pages, probe_wps  # noqa:E402
from measured_table_geometry import geometry  # noqa:E402
from measured_table_width_preflight import BASE, CASES, W  # noqa:E402
from paragraph_mark_font_mechanism import sha, write  # noqa:E402
from table_width_environment import (  # noqa:E402
    audit_schemas,
    environment_gate,
    restore_snapshot,
    semantic_pass,
    semantic_snapshot,
)

from wps_ai_agent_cli.fidelity import _pdf_pages, score_layout, ssim  # noqa:E402
from wps_ai_agent_cli.wps_convert import wps_convert  # noqa:E402

AFFECTED = {"A-contract-docx": (1, 4, 5), "A-manual-docx": (0, 3, 4), "A-pdfsource-docx": (0, 5, 6)}
FLOORS = {
    "A-report-docx": [0.9007, 0.9789],
    "A-contract-docx": [0.8644],
    "A-newsletter-docx": [0.9293],
    "A-manual-docx": [0.9027],
    "A-pdfsource-docx": [0.9123, 0.9258],
}


def table_geometry(case, pdf):
    if case == "A-contract-docx":
        return measure(pdf, original=True)
    _, cols, rows = AFFECTED[case]
    return geometry(pdf, cols, rows)


def verify_origins(case, geo):
    with ZipFile(BASE / case / "converted.docx") as z:
        root = ET.fromstring(z.read("word/document.xml"))
    table = root.find(W + "body").findall(W + "tbl")[AFFECTED[case][0]]
    expected = []
    for cell in table.findall(".//" + W + "tc"):
        v = cell.find(W + "tcPr/" + W + "vMerge")
        if v is not None and v.get(W + "val") in (None, "continue"):
            continue
        expected.append("".join("".join(t.itertext()) for t in cell.findall(".//" + W + "t")))
    if ["".join(t.split()) for t in expected] != ["".join(c["text"].split()) for c in geo["cells"]]:
        raise ValueError("Original XML text vs geometrically assigned glyphs differs")


def chars(pdf):
    import pdfplumber

    with pdfplumber.open(pdf) as doc:
        return [
            {
                "text": c["text"],
                "page": i,
                "x": c["x0"],
                "y": c["top"],
                "font": c["fontname"].split("+")[-1],
                "size": c["size"],
            }
            for i, p in enumerate(doc.pages)
            for c in p.chars
        ]


def compare(case, folder, styled, old_geo=None):
    from PIL import ImageChops

    oldpdf = BASE / case / "wps.pdf"
    newpdf = folder / "wps.pdf"
    oldpages, newpages = _pdf_pages(oldpdf, 800), _pdf_pages(newpdf, 800)
    gates = {"page_count": len(oldpages) == len(newpages)}
    if case not in AFFECTED:
        gates["all_page_pixels_identical"] = len(oldpages) == len(newpages) and all(
            a.size == b.size and ImageChops.difference(a, b).getbbox() is None
            for a, b in zip(oldpages, newpages, strict=True)
        )
    oldchars, newchars = chars(oldpdf), chars(newpdf)
    gates["all_text_line_page_font_y"] = len(oldchars) == len(newchars) and all(
        a["text"] == b["text"]
        and a["page"] == b["page"]
        and a["font"] == b["font"]
        and abs(a["size"] - b["size"]) <= 0.005
        and abs(a["y"] - b["y"]) <= 0.05
        for a, b in zip(oldchars, newchars, strict=False)
    )
    new_geo = None
    if case in AFFECTED:
        new_geo = table_geometry(case, newpdf)
        verify_origins(case, new_geo)
        gates["rule_differential"] = all(
            abs((b - a) + i * 0.75) <= 0.1 for i, (a, b) in enumerate(zip(old_geo["x"], new_geo["x"], strict=True))
        )
        gates["rows_y"] = all(abs(a - b) <= 0.05 for a, b in zip(old_geo["y"], new_geo["y"], strict=True))
        gates["origins_lines_fonts"] = all(
            a["text"] == b["text"]
            and a["fonts"] == b["fonts"]
            and len(b["baselines"]) == 1
            and abs(a["baselines"][0] - b["baselines"][0]) <= 0.05
            for a, b in zip(old_geo["cells"], new_geo["cells"], strict=True)
        )
        gates["outside_table_x"] = all(
            abs(a["x"] - b["x"]) <= 0.05
            for a, b in zip(oldchars, newchars, strict=False)
            if not (
                a["page"] == 0
                and old_geo["y"][0] < a["y"] < old_geo["y"][-1]
                and old_geo["x"][0] < a["x"] < old_geo["x"][-1]
            )
        )
    semantic = semantic_snapshot(next((folder / "input").glob("*.html")), folder / "candidate.docx", styled)
    gates["semantics"] = semantic_pass(semantic)
    layout = score_layout(folder / "browser.pdf", newpdf, renderer="wps", images_dir=folder / "pages")
    gates["each_page_score"] = len(layout.get("page_scores", [])) == len(FLOORS[case]) and all(
        a >= b for a, b in zip(layout.get("page_scores", []), FLOORS[case], strict=True)
    )
    oldaggregate = {
        "A-report-docx": 0.9398,
        "A-contract-docx": 0.8644,
        "A-newsletter-docx": 0.9293,
        "A-manual-docx": 0.9027,
        "A-pdfsource-docx": 0.9190,
    }[case]
    gates["aggregate_score"] = layout.get("score", 0) >= oldaggregate
    extra = None
    if case == "A-contract-docx":
        import numpy as np

        source = _pdf_pages(folder / "browser.pdf", 800)[0]
        target = newpages[0].resize(source.size)
        scores = {}
        for name, lo, hi in (("body", 395, 470), ("header", 348, 395), ("table", 348, 470)):
            box = (30, int(lo * 800 / 595.92), 770, int(hi * 800 / 595.92))
            scores[name] = ssim(np.asarray(source.crop(box)), np.asarray(target.crop(box)))
        edge = [34.125, 68.625, 104.625, 172.125, 307.875]
        before = [abs(x - s) for x, s in zip(old_geo["x"], edge, strict=True)]
        after = [abs(x - s) for x, s in zip(new_geo["x"], edge, strict=True)]
        gates["stage38_source_edge_error"] = all(b <= a + 0.05 for a, b in zip(before, after, strict=True)) and sum(
            after
        ) < sum(before)
        gates["stage38_score_floors"] = layout.get("score", 0) >= 0.8719 and all(
            scores[k] >= floor - 1e-9
            for k, floor in {"body": 0.595552511, "header": 0.882552033, "table": 0.693273755}.items()
        )
        extra = {"scores": scores, "edge_errors": [before, after], "source_loader": "same verified browser snapshot"}
    return {
        "gates": gates,
        "accepted": all(gates.values()),
        "layout": layout,
        "semantic": semantic,
        "baseline_geometry": old_geo,
        "candidate_geometry": new_geo,
        "stage38": extra,
        "strict_f2_layout": layout.get("score", 0) >= 0.90,
    }


def run(out):
    preflight = json.loads((out / "preflight.json").read_text(encoding="utf-8"))
    if preflight.get("outcome") != "BROWSER_PACKAGE_PASS_GEOMETRY_PENDING" or (out / "wps-manifest.json").exists():
        raise ValueError("Missing offline gate or set already attempted")
    environment = environment_gate(ROOT)
    write(out / "native-schema-audit.json", audit_schemas(BASE, [case for case, _ in CASES]))
    snapshots = {}
    semantic_gate = {}
    for case, _ in CASES:
        folder = out / case
        source = next((folder / "input").glob("*.html"))
        snapshots[case] = restore_snapshot(
            source, json.loads((folder / "browser-styles.json").read_text(encoding="utf-8"))
        )
        if sha(folder / "candidate.docx") != preflight["cases"][case]["candidate_sha256"]:
            raise ValueError("Candidate changed since preflight")
        semantic_gate[case] = {
            name: semantic_snapshot(source, folder / name, snapshots[case])
            for name in ("baseline.docx", "candidate.docx")
        }
        if not all(semantic_pass(r) for r in semantic_gate[case].values()):
            raise ValueError("Semantic baseline/candidate not all1 before WPS")
    write(
        out / "native-environment-preflight.json",
        {"environment": environment, "semantics": semantic_gate, "browser_recaptures": 0},
    )
    original = {case: table_geometry(case, BASE / case / "wps.pdf") for case in AFFECTED}
    for case, geo in original.items():
        verify_origins(case, geo)
    write(out / "baseline-geometry.json", original)
    manifest = {
        "base": "b083ae7cb4a95648e9c01c972dd797fc4844689c",
        "results": {},
        "not_run": [case for case, _ in CASES],
        "exports": [],
    }
    write(out / "wps-manifest.json", manifest)
    for case, _ in CASES:
        folder = out / case
        raw, state = probe_wps()
        write(folder / "wps-probe.json", raw)
        if (
            state is None
            or state.get("processes")
            or not any(v.get("file_version") == "12,8,2,18913" for v in state.get("executables", []))
        ):
            manifest["stop"] = "UNSAFE_OR_VERSION"
            break
        manifest["versions"] = state["executables"]
        result = wps_convert((folder / "candidate.docx").resolve(), (folder / "wps.pdf").resolve(), timeout_seconds=120)
        write(folder / "wps-export.json", result)
        manifest["exports"].append(case)
        manifest["not_run"].remove(case)
        write(out / "wps-manifest.json", manifest)
        if not result[0]:
            manifest["stop"] = "EXPORT_FAILED"
            break
        color_pages(folder / "wps.pdf", folder, "wps-page")
        try:
            acceptance = compare(case, folder, snapshots[case], original.get(case))
            write(folder / "acceptance.json", acceptance)
            manifest["results"][case] = {
                "accepted": acceptance["accepted"],
                "layout": acceptance["layout"],
                "gates": acceptance["gates"],
            }
            print(case, manifest["results"][case], flush=True)
            if not acceptance["accepted"]:
                manifest["stop"] = "REGRESSION_GATE"
                break
        except Exception as error:
            manifest["stop"] = f"{type(error).__name__}: {error}"
            break
        write(out / "wps-manifest.json", manifest)
    manifest["outcome"] = "STOP" if manifest.get("stop") or manifest["not_run"] else "PASS_FIVE_CASE_GATE"
    manifest["hashes"] = {
        p.relative_to(out).as_posix(): sha(p)
        for p in sorted(out.rglob("*"))
        if p.is_file() and p.name != "wps-manifest.json"
    }
    write(out / "wps-manifest.json", manifest)
    print(manifest["outcome"], manifest.get("stop"), manifest["not_run"])


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    run(p.parse_args().out)
