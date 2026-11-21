"""Stage44 one browser-reference set and exact original-five package gate; no WPS."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile, ZipInfo

from lxml import etree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from html_docx_wps_matrix import CASES, copy_inputs  # noqa:E402
from paragraph_mark_font_mechanism import sha, write  # noqa:E402
from table_width_environment import (  # noqa:E402
    audit_schemas,
    environment_gate,
    restore_snapshot,
    semantic_assessment,
    semantic_pass,
    semantic_snapshot,
)

from wps_ai_agent_cli import docx_styling, html_styles  # noqa:E402
from wps_ai_agent_cli.fidelity import _pdf_pages  # noqa:E402
from wps_ai_agent_cli.html_editable import convert_html_editable, table_grid, table_rows  # noqa:E402
from wps_ai_agent_cli.html_render import render_html  # noqa:E402

BASE = ROOT / "artifacts/schema-table-width-20261121"
SCHEMA_BASE = ROOT / "artifacts/alignment-aware-print-margins-20261121"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
EXPECTED = {
    "A-report-docx": [],
    "A-newsletter-docx": [],
    "A-contract-docx": [1],
    "A-manual-docx": [],
    "A-pdfsource-docx": [],
}


def inverse(before, after, case):
    a, b = ET.fromstring(before), ET.fromstring(after)
    allowed = set()
    if case == "A-contract-docx":
        table = b.find(W + "body").findall(W + "tbl")[1]
        allowed = set(table.findall(W + "tr/" + W + "trPr/" + W + "trHeight"))
    count = 0
    for old, new in zip(a.iter(), b.iter(), strict=True):
        if old.tag != new.tag or old.text != new.text or old.tail != new.tail:
            raise ValueError("Non-row XML change")
        if old.attrib != new.attrib:
            if (
                new not in allowed
                or dict(old.attrib) != {W + "val": "465", W + "hRule": "atLeast"}
                or dict(new.attrib) != {W + "val": "450", W + "hRule": "atLeast"}
            ):
                raise ValueError("Unexpected row attribute")
            new.attrib.update(old.attrib)
            count += 1
    if (
        count != (5 if case == "A-contract-docx" else 0)
        or ET.tostring(b, encoding="UTF-8", xml_declaration=True, standalone=True) != before
    ):
        raise ValueError("Inverse/count mismatch")
    return count


def snapshot(styled):
    return {
        "mode": styled.mode,
        "browser": styled.browser,
        "print_context": styled.print_context,
        "warnings": styled.warnings,
        "source_sha256": sha(styled.source),
        "page": styled.page,
        "elements": [
            {
                "tag": n.tag,
                "attrs": n.attrs,
                "style": styled.style(n),
                "box": styled.box(n),
                "pseudo": styled.pseudo_elements(n),
                **({"summary_marker": styled.summary_markers.get(id(n))} if n.tag == "summary" else {}),
            }
            for n in html_styles._walk(styled.root)
        ],
    }


def run(out):
    from PIL import ImageChops

    out.mkdir(parents=True, exist_ok=False)
    report = {"base": "b083ae7cb4a95648e9c01c972dd797fc4844689c", "wps_exports": 0, "cases": {}}
    try:
        write(out / "semantic-schema-audit.json", audit_schemas(SCHEMA_BASE, [case for case, _ in CASES]))
        write(out / "environment-preflight.json", environment_gate(ROOT))
    except Exception as error:
        report.update(outcome="STOP_BEFORE_BROWSER", error=str(error))
        write(out / "preflight.json", report)
        return
    for case, relative in CASES:
        folder = out / case
        folder.mkdir()
        try:
            source, assets = copy_inputs(ROOT / relative, folder / "input")
            write(folder / "input-manifest.json", assets)
            reference = BASE / case
            if source.read_bytes() != (reference / "input" / source.name).read_bytes():
                raise ValueError("Source bytes differ")
            styled = html_styles.load(source)
            new = snapshot(styled)
            write(folder / "browser-styles.json", new)
            old = json.loads((reference / "browser-styles.json").read_text(encoding="utf-8"))
            if (
                new["mode"] != "browser"
                or new["browser"] != "157.0.4341.60"
                or len(new["elements"]) != len(old["elements"])
            ):
                raise ValueError("Browser/version/nodes changed")
            changes = []
            for index, (a, b) in enumerate(zip(old["elements"], new["elements"], strict=True)):
                if (
                    a["tag"] != b["tag"]
                    or a["attrs"] != b["attrs"]
                    or a["box"] != b["box"]
                    or a.get("summary_marker") != b.get("summary_marker")
                    or any(b["style"].get(k) != v for k, v in a["style"].items())
                ):
                    changes.append({"index": index, "before": a, "after": b})
            write(folder / "metadata-changes.json", changes)
            if changes:
                raise ValueError("Existing CSS/box/marker changed")
            rendered = render_html(source, folder / "browser.pdf", "pdf", margin_mm=10)
            write(folder / "browser-render.json", rendered)
            if not rendered[0]:
                raise ValueError("Browser reference failed")
            a, b = _pdf_pages(reference / "browser.pdf", 800), _pdf_pages(folder / "browser.pdf", 800)
            if len(a) != len(b) or any(
                x.size != y.size or ImageChops.difference(x, y).getbbox() is not None for x, y in zip(a, b, strict=True)
            ):
                raise ValueError("Source browser page pixels/size changed")
            tables = [n for n in html_styles._walk(styled.root) if n.tag == "table"]
            from docx import Document

            page_width = docx_styling.apply_page(Document(), styled)
            eligible = [
                i
                for i, n in enumerate(tables)
                if docx_styling.measured_merged_row_minima(styled, n, table_grid(n)[0], table_rows(n), page_width)
                is not None
            ]
            if eligible != EXPECTED[case]:
                raise ValueError(f"Unexpected eligibility {eligible}")
            with ZipFile(reference / "candidate.docx") as z:
                infos = {i.filename: copy.copy(i) for i in z.infolist()}
            original_write = ZipFile.writestr

            def fixed(self, info, data, *args, original_write=original_write, infos=infos, **kwargs):
                name = info.filename if isinstance(info, ZipInfo) else info
                return original_write(self, copy.copy(infos[name]), data, *args, **kwargs)

            for name, legacy in (("baseline.docx", True), ("candidate.docx", False)):
                with patch.object(html_styles, "load", return_value=styled), patch.object(ZipFile, "writestr", fixed):
                    if legacy:
                        with patch.object(docx_styling, "measured_merged_row_minima", return_value=None):
                            converted = convert_html_editable(source, folder / name, use_browser=False)
                    else:
                        converted = convert_html_editable(source, folder / name, use_browser=False)
                if not converted[0]:
                    raise ValueError(converted)
            if (folder / "baseline.docx").read_bytes() != (reference / "candidate.docx").read_bytes():
                raise ValueError("Old code path full package changed")
            with ZipFile(reference / "candidate.docx") as oldzip, ZipFile(folder / "candidate.docx") as candidate:
                if oldzip.namelist() != candidate.namelist():
                    raise ValueError("Package members changed")
                count = 0
                for name in oldzip.namelist():
                    if name == "word/document.xml":
                        count = inverse(oldzip.read(name), candidate.read(name), case)
                    elif oldzip.read(name) != candidate.read(name):
                        raise ValueError("Other package part differs")
            if (
                not EXPECTED[case]
                and (folder / "candidate.docx").read_bytes() != (reference / "candidate.docx").read_bytes()
            ):
                raise ValueError("Unchanged case bytes differ")
            if (
                case == "A-contract-docx"
                and sha(folder / "candidate.docx") != "2b5e206fb74d5a73b036ab8a8e4b01b6dc98d5818599cfbabdb28579bdd0aefa"
            ):
                raise ValueError("Not the Stage43 package")
            replay = restore_snapshot(source, new)
            semantic = {
                name: semantic_snapshot(source, folder / name, replay) for name in ("baseline.docx", "candidate.docx")
            }
            write(folder / "semantic-preflight.json", semantic)
            write(folder / "semantic-assessments.json", {name: semantic_assessment(r) for name, r in semantic.items()})
            if not all(semantic_pass(r) for r in semantic.values()):
                raise ValueError("Browser snapshot baseline/candidate semantics not all1")
            report["cases"][case] = {
                "eligible_tables": eligible,
                "allowed_row_attributes": count,
                "candidate_sha256": sha(folder / "candidate.docx"),
                "browser_pixels_identical": True,
                "metadata_unchanged": True,
                "baseline_bytes_identical": True,
                "semantics_baseline_candidate_all1": True,
            }
            write(out / "preflight.json", report)
            print(case, report["cases"][case], flush=True)
        except Exception as error:
            report.update(outcome="STOP_BEFORE_WPS", stop_case=case, error=f"{type(error).__name__}: {error}")
            write(out / "preflight.json", report)
            print(report, flush=True)
            return
    report["outcome"] = "BROWSER_PACKAGE_PASS_GEOMETRY_PENDING"
    write(out / "preflight.json", report)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    run(p.parse_args().out)
