"""Stage50 one native set only after the sealed original-five browser/package gate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from contract_spacing_interaction import assess as assess_contract  # noqa:E402
from html_docx_wps_matrix import CASES, color_pages, probe_wps  # noqa:E402
from paragraph_mark_font_mechanism import sha, write  # noqa:E402
from qualified_flow_preflight import BASE, EXPECTED, SNAPSHOTS, baseline, source_pixels_equal  # noqa:E402
from table_width_environment import (  # noqa:E402
    audit_schemas,
    environment_gate,
    restore_snapshot,
    semantic_pass,
    semantic_snapshot,
)

from wps_ai_agent_cli.fidelity import score_layout  # noqa:E402
from wps_ai_agent_cli.wps_convert import wps_convert  # noqa:E402

FLOORS = {
    "A-report-docx": [0.9007, 0.9789],
    "A-contract-docx": [0.90],
    "A-newsletter-docx": [0.9293],
    "A-manual-docx": [0.9060],
    "A-pdfsource-docx": [0.9237, 0.9258],
}
AGGREGATES = {
    "A-report-docx": 0.9398,
    "A-contract-docx": 0.90,
    "A-newsletter-docx": 0.9293,
    "A-manual-docx": 0.9060,
    "A-pdfsource-docx": 0.9247,
}


def seal(out):
    target = out / "offline-hashes.json"
    if target.exists() or (out / "wps-manifest.json").exists():
        raise ValueError("Offline seal/native attempt already exists")
    pre = json.loads((out / "browser-attempt.json").read_text(encoding="utf-8"))
    if (
        pre["outcome"] != "OFFLINE_PASS_AWAITING_NATIVE_REVIEW"
        or pre["started"] != [c for c, _ in CASES]
        or set(pre["cases"]) != {c for c, _ in CASES}
    ):
        raise ValueError("Incomplete browser/package set")
    references = [SNAPSHOTS / "A-contract-docx/wps.pdf"]
    for case, _ in CASES:
        if pre["cases"][case]["hits"] != (2 if case == "A-contract-docx" else 0):
            raise ValueError("Unexpected qualification count")
        if sha(out / case / "candidate.docx") != pre["cases"][case]["candidate_sha256"]:
            raise ValueError("Offline input changed before sealing")
        references.extend(
            [
                BASE / case / "wps.pdf",
                BASE / case / "browser.pdf",
                baseline(case),
                SNAPSHOTS / case / "browser-styles.json",
            ]
        )
    write(
        target,
        {
            "files": {p.relative_to(out).as_posix(): sha(p) for p in sorted(out.rglob("*")) if p.is_file()},
            "references": {p.relative_to(ROOT).as_posix(): sha(p) for p in references},
        },
    )


def text_signature(path):
    import pdfplumber

    with pdfplumber.open(path) as document:
        return [
            {
                "lines": [line["text"] for line in page.extract_text_lines()],
                "chars": [
                    {
                        "text": c["text"],
                        "font": c["fontname"].split("+")[-1],
                        "size": c["size"],
                        "x": c["x0"],
                        "baseline": page.height - c["matrix"][5],
                    }
                    for c in page.chars
                ],
            }
            for page in document.pages
        ]


def unchanged_text(before, after):
    a, b = text_signature(before), text_signature(after)
    if len(a) != len(b):
        return False
    for old, new in zip(a, b, strict=True):
        if old["lines"] != new["lines"] or len(old["chars"]) != len(new["chars"]):
            return False
        for x, y in zip(old["chars"], new["chars"], strict=True):
            if x["text"] != y["text"] or x["font"] != y["font"]:
                return False
            if any(abs(x[k] - y[k]) > tol for k, tol in (("size", 0.005), ("x", 0.05), ("baseline", 0.05))):
                return False
    return True


def compare(case, folder, styled):
    semantic = semantic_snapshot(next((folder / "input").glob("*.html")), folder / "candidate.docx", styled)
    layout = score_layout(folder / "browser.pdf", folder / "wps.pdf", renderer="wps", images_dir=folder / "pages")
    pages = layout.get("page_scores", [])
    gates = {
        "semantics": semantic_pass(semantic),
        "per_page": len(pages) == len(FLOORS[case]) and all(a >= b for a, b in zip(pages, FLOORS[case], strict=True)),
        "aggregate": layout.get("score", 0) >= AGGREGATES[case],
    }
    detail = None
    if case == "A-contract-docx":
        detail = assess_contract(folder / "wps.pdf")
        gates["stage48_all_eleven_gates"] = len(detail["gates"]) == 11 and all(detail["gates"].values())
        gates["stage48_positive"] = detail["outcome"] == "PASS_MECHANISM_ONLY"
        gates["contract_strict_f2"] = detail["strict_f2"] is True
    else:
        control = BASE / case / "wps.pdf"
        gates["all_page_rgb_identical"] = source_pixels_equal(control, folder / "wps.pdf")
        gates["all_text_lines_positions_identical"] = unchanged_text(control, folder / "wps.pdf")
    return {
        "accepted": all(gates.values()),
        "gates": gates,
        "layout": layout,
        "semantic": semantic,
        "stage48": detail,
        "strict_f2_layout": layout.get("score", 0) >= 0.90,
    }


def run(out):
    path = out / "wps-manifest.json"
    if path.exists():
        raise ValueError("Native set already attempted; no retry")
    manifest = {
        "base": "c1d605ec0482b7d846ca9549c29114e43c29cad2",
        "attempted_exports": [],
        "exports": [],
        "not_run": [c for c, _ in CASES],
        "results": {},
        "outcome": "ATTEMPT_STARTED",
    }
    write(path, manifest)
    try:
        sealed = json.loads((out / "offline-hashes.json").read_text(encoding="utf-8"))
        for name, digest in sealed["files"].items():
            if sha(out / name) != digest:
                raise ValueError(f"Sealed offline bytes changed: {name}")
        for name, digest in sealed["references"].items():
            if sha(ROOT / name) != digest:
                raise ValueError(f"Immutable reference changed: {name}")
        pre = json.loads((out / "browser-attempt.json").read_text(encoding="utf-8"))
        if pre["outcome"] != "OFFLINE_PASS_AWAITING_NATIVE_REVIEW" or pre["started"] != [c for c, _ in CASES]:
            raise ValueError("Browser/package gate incomplete")
        env = environment_gate(ROOT)
        schemas = audit_schemas(ROOT / "artifacts/alignment-aware-print-margins-20261121", [c for c, _ in CASES])
        snapshots, semantics = {}, {}
        for case, _ in CASES:
            folder = out / case
            source = next((folder / "input").glob("*.html"))
            snapshots[case] = restore_snapshot(
                source, json.loads((folder / "browser-styles.json").read_text(encoding="utf-8"))
            )
            if sha(folder / "candidate.docx") != pre["cases"][case]["candidate_sha256"]:
                raise ValueError("Candidate differs from exact offline gate")
            if case == "A-contract-docx" and sha(folder / "candidate.docx") != EXPECTED:
                raise ValueError("Not the Stage48 input")
            semantics[case] = {
                n: semantic_snapshot(source, folder / n, snapshots[case]) for n in ("baseline.docx", "candidate.docx")
            }
            if not all(semantic_pass(r) for r in semantics[case].values()):
                raise ValueError("Fresh-snapshot pre-native semantics failed")
        write(
            out / "native-preflight.json",
            {"environment": env, "schemas": schemas, "semantics": semantics, "browser_recaptures": 0},
        )
        for case, _ in CASES:
            folder = out / case
            raw, state = probe_wps()
            write(folder / "wps-probe.json", raw)
            if (
                state is None
                or state.get("processes") != []
                or not any(v.get("file_version") == "12,8,2,18913" for v in state.get("executables", []))
            ):
                raise ValueError("Unsafe process state or WPS version")
            manifest["versions"] = state["executables"]
            if sha(folder / "candidate.docx") != pre["cases"][case]["candidate_sha256"]:
                raise ValueError("WPS input changed immediately before export")
            manifest["attempted_exports"].append(case)
            manifest["not_run"].remove(case)
            write(path, manifest)
            exported = wps_convert(
                (folder / "candidate.docx").resolve(), (folder / "wps.pdf").resolve(), timeout_seconds=120
            )
            write(folder / "wps-export.json", exported)
            manifest["exports"].append(case)
            write(path, manifest)
            if not exported[0]:
                raise ValueError("Single export failed")
            color_pages(folder / "wps.pdf", folder, "wps-page")
            result = compare(case, folder, snapshots[case])
            write(folder / "acceptance.json", result)
            manifest["results"][case] = {k: result[k] for k in ("accepted", "gates", "layout")}
            write(path, manifest)
            print(case, manifest["results"][case], flush=True)
            if not result["accepted"]:
                raise ValueError(f"Native regression gate failed: {case}")
        manifest["outcome"] = "PASS_FIVE_CASE_GATE"
    except Exception as error:
        manifest.update(outcome="STOP", error=f"{type(error).__name__}: {error}")
    manifest["hashes"] = {
        p.relative_to(out).as_posix(): sha(p) for p in sorted(out.rglob("*")) if p.is_file() and p != path
    }
    write(path, manifest)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seal-only", action="store_true")
    args = parser.parse_args()
    seal(args.out) if args.seal_only else run(args.out)
