"""Single fixed merged-continuation-width DOCX mechanism; no converter edits."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from zipfile import ZipFile

from lxml import etree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from html_docx_wps_matrix import color_pages, probe_wps  # noqa:E402
from manual_row_mechanism import measure  # noqa:E402

from wps_ai_agent_cli.wps_convert import wps_convert  # noqa:E402

BASE = ROOT / "artifacts/figure-image-indent-20261121/A-contract-docx"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def patch_xml(source):
    root = ET.fromstring(source)
    table = root.find(W + "body").findall(W + "tbl")[1]
    grid = [int(c.get(W + "w")) for c in table.find(W + "tblGrid")]
    if grid != [710, 724, 1370, 2729]:
        raise ValueError(grid)
    cells = table.findall(W + "tr")[1].findall(W + "tc")
    changes = []
    for index, width in ((0, 710), (3, 2729)):
        props = cells[index].find(W + "tcPr")
        merge = props.find(W + "vMerge")
        tcw = props.find(W + "tcW")
        if merge is None or merge.get(W + "val") not in (None, "continue") or tcw.get(W + "w") != "2633":
            raise ValueError("Unexpected target")
        tcw.set(W + "w", str(width))
        changes.append({"column": index, "before": 2633, "after": width})
    result = ET.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True)
    for index, _ in ((0, 710), (3, 2729)):
        cells[index].find(W + "tcPr/" + W + "tcW").set(W + "w", "2633")
    if ET.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True) != source:
        raise ValueError("Other XML serialization difference")
    return result, changes


def build(source, target):
    with ZipFile(source) as original, ZipFile(target, "w") as output:
        for info in original.infolist():
            data = original.read(info.filename)
            if info.filename == "word/document.xml":
                data, changes = patch_xml(data)
            output.writestr(copy.copy(info), data)
    return changes


def assess(pdf):
    import pypdfium2 as pdfium
    from PIL import ImageChops

    from wps_ai_agent_cli.fidelity import fidelity_check, score_layout

    out = pdf.parent
    old = measure(BASE / "wps.pdf")
    new = measure(pdf)
    with pdfium.PdfDocument(str(BASE / "wps.pdf")) as a, pdfium.PdfDocument(str(pdf)) as b:
        pixels = len(a) == len(b) and all(
            ImageChops.difference(
                a[i].render(scale=800 / a[i].get_width()).to_pil().convert("RGB"),
                b[i].render(scale=800 / b[i].get_width()).to_pil().convert("RGB"),
            ).getbbox()
            is None
            for i in range(len(a))
        )
    semantic = fidelity_check(BASE / "input/contract.html", out / "candidate.docx", layout=False)
    layout = score_layout(BASE / "browser.pdf", pdf, renderer="wps", images_dir=out / "pages")
    gates = {
        "pixels_identical": pixels,
        "all_rules_identical": old["rules"] == new["rules"],
        "row_pitches_identical": old["row_pitches"] == new["row_pitches"],
        "all_text_bboxes_identical": old["chars"] == new["chars"],
        "pages": old["pages"] == new["pages"],
        "semantics": semantic[0] and all(semantic[1]["verdict"].values()),
        "ssim": layout.get("score", 0) >= 0.8492,
    }
    # Pixel equality is an observed negative-mechanism result, not a required positive gate.
    required = {k: v for k, v in gates.items() if k != "pixels_identical"}
    return {
        "baseline_geometry": old,
        "candidate_geometry": new,
        "layout": layout,
        "semantic": semantic,
        "gates": gates,
        "accepted": all(required.values()),
        "product_fix": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--export-wps", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    target = args.out / "candidate.docx"
    manifest = {
        "base": "3086f60def5fe46c4c353f0c6d5f766c23e8eeb2",
        "baseline": BASE.relative_to(ROOT).as_posix(),
        "source_sha256": sha(BASE / "converted.docx"),
        "changes": build(BASE / "converted.docx", target),
        "candidate_sha256": sha(target),
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
        manifest["stop"] = "UNSAFE_OR_VERSION_MISMATCH"
        write(args.out / "manifest.json", manifest)
        return
    manifest["versions"] = state["executables"]
    pdf = args.out / "wps.pdf"
    export = wps_convert(target.resolve(), pdf.resolve(), timeout_seconds=120)
    write(args.out / "export.json", export)
    if not export[0]:
        manifest["stop"] = "EXPORT_FAILED"
        write(args.out / "manifest.json", manifest)
        return
    manifest["wps_exports"] = 1
    manifest["pdf_sha256"] = sha(pdf)
    color_pages(pdf, args.out, "wps-page")
    result = assess(pdf)
    write(args.out / "acceptance.json", result)
    manifest["accepted"] = result["accepted"]
    manifest["pixels_identical"] = result["gates"]["pixels_identical"]
    write(args.out / "manifest.json", manifest)
    print(
        json.dumps(
            {"accepted": manifest["accepted"], "gates": result["gates"], "layout": result["layout"]}, ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
