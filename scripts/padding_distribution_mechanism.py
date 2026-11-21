"""Stage32 fixed-total paragraph-padding distribution, evidence only."""

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
from paragraph_mark_font_mechanism import BASE, EXPECTED, W, assess, sha, write  # noqa:E402

from wps_ai_agent_cli.wps_convert import wps_convert  # noqa:E402


def patch_xml(source):
    root = ET.fromstring(source)
    rows = root.find(W + "body").findall(W + "tbl")[1].findall(W + "tr")
    if len(rows) != 5:
        raise ValueError("Unexpected rows")
    changes = []
    for row in rows[2:]:
        cells = row.findall(W + "tc")
        if len(cells) != 4:
            raise ValueError("Unexpected cells")
        for cell in cells:
            if cell.findall(".//" + W + "vMerge") or cell.findall(".//" + W + "gridSpan"):
                raise ValueError("Merged target")
            ps = cell.findall(W + "p")
            align = cell.find(W + "tcPr/" + W + "vAlign")
            if len(ps) != 1 or align is None or align.get(W + "val") != "center":
                raise ValueError("Unexpected target layout")
            spacing = ps[0].find(W + "pPr/" + W + "spacing")
            expected = {
                W + k: v for k, v in {"before": "60", "after": "45", "line": "330", "lineRule": "exact"}.items()
            }
            if spacing is None or dict(spacing.attrib) != expected:
                raise ValueError("Unexpected spacing")
            spacing.set(W + "before", "53")
            spacing.set(W + "after", "52")
            changes.append(spacing)
    if len(changes) != 12:
        raise ValueError("Wrong target count")
    result = ET.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True)
    for spacing in changes:
        spacing.set(W + "before", "60")
        spacing.set(W + "after", "45")
    if ET.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True) != source:
        raise ValueError("Inverse mismatch")
    return result


def build(source, target):
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


def classify(result):
    shifts = result["shifts"]
    prediction = all(abs(s + 0.35) <= 0.05 for s in shifts) and max(shifts) - min(shifts) <= 0.05
    gain = all(abs(a) - abs(b) >= 0.25 for a, b in zip(result["old_errors"], result["new_errors"], strict=True))
    scores = result["roi_ssim"][1] > 0.5516460049 and result["layout"]["score"] > 0.8644
    conserved = all(result["gates"].values())
    if result["pixels_identical"] and result["baseline"] == result["candidate"] and conserved:
        return "ZERO_INFLUENCE"
    return "POSITIVE" if prediction and gain and scores and conserved else "STOP"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--export-wps", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    target = args.out / "candidate.docx"
    build(BASE / "converted.docx", target)
    manifest = {
        "base": "9bdc71078dabc7178040740483277154b4ab5ff5",
        "baseline": BASE.relative_to(ROOT).as_posix(),
        "sources": {n: sha(BASE / n) for n in ("converted.docx", "browser.pdf", "wps.pdf")},
        "candidate_sha256": sha(target),
        "preflight": "24 attributes, exact inverse, other parts identical",
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
        raise RuntimeError("Single export failed; STOP, no retry")
    color_pages(pdf, args.out, "wps-page")
    measured = assess(pdf)
    measured["outcome"] = classify(measured)
    write(args.out / "acceptance.json", measured)
    manifest.update(outcome=measured["outcome"], pdf_sha256=sha(pdf))
    manifest["outputs"] = {
        p.relative_to(args.out).as_posix(): {"sha256": sha(p), "bytes": p.stat().st_size}
        for p in sorted(args.out.rglob("*"))
        if p.is_file() and p.name != "manifest.json"
    }
    write(args.out / "manifest.json", manifest)
    print({k: measured[k] for k in ("outcome", "shifts", "new_errors", "roi_ssim", "gates")})


if __name__ == "__main__":
    main()
