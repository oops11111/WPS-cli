"""Stage44 only new original-five native set after natural-row preflight."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from contract_row_minimum_mechanism import assess as assess_contract  # noqa:E402
from html_docx_wps_matrix import CASES, color_pages, probe_wps  # noqa:E402
from natural_row_preflight import BASE, SCHEMA_BASE  # noqa:E402
from paragraph_mark_font_mechanism import sha, write  # noqa:E402
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
    "A-contract-docx": [0.8950],
    "A-newsletter-docx": [0.9293],
    "A-manual-docx": [0.9060],
    "A-pdfsource-docx": [0.9237, 0.9258],
}
AGGREGATES = {
    "A-report-docx": 0.9398,
    "A-contract-docx": 0.8950,
    "A-newsletter-docx": 0.9293,
    "A-manual-docx": 0.9060,
    "A-pdfsource-docx": 0.9247,
}


def identical_pixels(before, after):
    import pypdfium2 as pdfium
    from PIL import ImageChops

    with pdfium.PdfDocument(str(before)) as a, pdfium.PdfDocument(str(after)) as b:
        return len(a) == len(b) and all(
            ImageChops.difference(
                a[i].render(scale=800 / a[i].get_width()).to_pil().convert("RGB"),
                b[i].render(scale=800 / b[i].get_width()).to_pil().convert("RGB"),
            ).getbbox()
            is None
            for i in range(len(a))
        )


def compare(case, folder, styled):
    semantic = semantic_snapshot(next((folder / "input").glob("*.html")), folder / "candidate.docx", styled)
    layout = score_layout(folder / "browser.pdf", folder / "wps.pdf", renderer="wps", images_dir=folder / "pages")
    gates = {
        "semantics": semantic_pass(semantic),
        "each_page": len(layout.get("page_scores", [])) == len(FLOORS[case])
        and all(a >= b for a, b in zip(layout.get("page_scores", []), FLOORS[case], strict=True)),
        "aggregate": layout.get("score", 0) >= AGGREGATES[case],
    }
    extra = None
    if case == "A-contract-docx":
        extra = assess_contract(folder / "wps.pdf")
        gates["stage43_all_geometry_flow"] = all(extra["gates"].values())
        gates["stage43_roi_floors"] = all(
            extra["scores"][k][1] >= v - 1e-9
            for k, v in {"body": 0.808045712, "header": 0.934692855, "table": 0.857345359, "later": 0.764176805}.items()
        )
    else:
        gates["all_rgb_page_pixels_identical"] = identical_pixels(BASE / case / "wps.pdf", folder / "wps.pdf")
    return {
        "gates": gates,
        "accepted": all(gates.values()),
        "semantic": semantic,
        "layout": layout,
        "stage43": extra,
        "strict_f2_layout": layout.get("score", 0) >= 0.90,
    }


def run(out):
    pre = json.loads((out / "preflight.json").read_text(encoding="utf-8"))
    if pre.get("outcome") != "BROWSER_PACKAGE_PASS_GEOMETRY_PENDING" or (out / "wps-manifest.json").exists():
        raise ValueError("Offline gate missing or native set already attempted")
    env = environment_gate(ROOT)
    schemas = audit_schemas(SCHEMA_BASE, [c for c, _ in CASES])
    snapshots = {}
    semantics = {}
    for case, _ in CASES:
        folder = out / case
        source = next((folder / "input").glob("*.html"))
        snapshots[case] = restore_snapshot(
            source, json.loads((folder / "browser-styles.json").read_text(encoding="utf-8"))
        )
        if sha(folder / "candidate.docx") != pre["cases"][case]["candidate_sha256"]:
            raise ValueError("Candidate changed since preflight")
        semantics[case] = {
            n: semantic_snapshot(source, folder / n, snapshots[case]) for n in ("baseline.docx", "candidate.docx")
        }
        if not all(semantic_pass(r) for r in semantics[case].values()):
            raise ValueError("Semantic preflight failed before WPS")
    write(
        out / "native-preflight.json",
        {"environment": env, "schemas": schemas, "semantics": semantics, "browser_recaptures": 0},
    )
    manifest = {
        "base": "1d48d868f440a930001d4517dcb7cc57d0e44a8e",
        "exports": [],
        "not_run": [c for c, _ in CASES],
        "results": {},
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
        exported = wps_convert(
            (folder / "candidate.docx").resolve(), (folder / "wps.pdf").resolve(), timeout_seconds=120
        )
        write(folder / "wps-export.json", exported)
        manifest["exports"].append(case)
        manifest["not_run"].remove(case)
        write(out / "wps-manifest.json", manifest)
        if not exported[0]:
            manifest["stop"] = "EXPORT_FAILED"
            break
        color_pages(folder / "wps.pdf", folder, "wps-page")
        try:
            result = compare(case, folder, snapshots[case])
            write(folder / "acceptance.json", result)
            manifest["results"][case] = {
                "accepted": result["accepted"],
                "gates": result["gates"],
                "layout": result["layout"],
            }
            print(case, manifest["results"][case], flush=True)
            if not result["accepted"]:
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
