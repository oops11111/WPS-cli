"""Measure only the original contract after a vertical-merge border repair."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from direct_container_evidence import write  # noqa: E402
from html_docx_wps_matrix import run_case  # noqa: E402

from wps_ai_agent_cli.fidelity import ssim  # noqa: E402

# Fixed from stage-4 browser geometry before the repair; no target-based alignment.
TABLE_REGION = (40, 460, 425, 640)


def physical_cells(path):
    from docx import Document
    from docx.oxml.ns import qn

    table = Document(path).tables[1]
    result = []
    for row_index, row in enumerate(table._tbl.tr_lst[:2]):
        for column, cell in enumerate(row.tc_lst):
            props = cell.tcPr
            result.append(
                {
                    "row": row_index,
                    "physical_cell": column,
                    "vMerge": props.vMerge.val if props.vMerge is not None else None,
                    "borders": [
                        {edge.tag.rsplit("}", 1)[-1]: dict(edge.attrib) for edge in borders}
                        for borders in props.findall(qn("w:tcBorders"))
                    ],
                    "shading": [dict(s.attrib) for s in props.findall(qn("w:shd"))],
                }
            )
    return result


def crop_pair(folder):
    import numpy as np
    from PIL import Image

    a = Image.open(folder / "browser-page-001.png").convert("RGB").crop(TABLE_REGION)
    b = Image.open(folder / "wps-page-001.png").convert("RGB").crop(TABLE_REGION)
    pair = Image.new("RGB", (a.width * 2 + 8, a.height), "gray")
    pair.paste(a, (0, 0))
    pair.paste(b, (a.width + 8, 0))
    return pair, round(ssim(np.asarray(a.convert("L")), np.asarray(b.convert("L"))), 4)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    base = ROOT / "artifacts/html-docx-wps-matrix-20261121/A-contract-docx"
    baseline = json.loads((ROOT / "config/fidelity_baselines.json").read_text(encoding="utf-8"))["cases"]
    report = run_case("A-contract-docx", "fixtures/fidelity/contract.html", out / "contract", baseline)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10)
    diff = subprocess.run(["git", "diff", "--", "src"], cwd=ROOT, capture_output=True, timeout=10)
    record = {
        "git_head": head.stdout.strip(),
        "product_diff_sha256": hashlib.sha256(diff.stdout).hexdigest(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "region": list(TABLE_REGION),
        "baseline": json.loads((base / "result.json").read_text(encoding="utf-8")),
        "current": report,
    }
    write(out / "before-physical-cells.json", physical_cells(base / "converted.docx"))
    if report["execution_ok"]:
        write(out / "after-physical-cells.json", physical_cells(out / "contract/converted.docx"))
        for label, folder in (("before", base), ("after", out / "contract")):
            pair, score = crop_pair(folder)
            pair.save(out / (label + "-fee-table.png"))
            record[label + "_table_region_ssim"] = score
    write(out / "comparison.json", record)
    print(
        json.dumps(
            {
                "execution_ok": report["execution_ok"],
                "layout": report.get("layout"),
                "strict_f2": report.get("strict_f2"),
                "before_table_region_ssim": record.get("before_table_region_ssim"),
                "after_table_region_ssim": record.get("after_table_region_ssim"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
