"""Stage50 prepare-only by default; explicit one-shot five-case browser/package gate."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from contract_spacing_interaction import patch_xml  # noqa:E402
from html_docx_wps_matrix import CASES, copy_inputs  # noqa:E402
from natural_row_preflight import snapshot  # noqa:E402
from paragraph_mark_font_mechanism import sha, write  # noqa:E402
from table_width_environment import (  # noqa:E402
    audit_schemas,
    environment_gate,
    restore_snapshot,
    semantic_pass,
    semantic_snapshot,
)

from wps_ai_agent_cli import docx_styling, html_styles  # noqa:E402
from wps_ai_agent_cli.html_editable import convert_html_editable  # noqa:E402
from wps_ai_agent_cli.html_render import render_html  # noqa:E402

BASE = ROOT / "artifacts/schema-table-width-20261121"
SNAPSHOTS = ROOT / "artifacts/natural-merged-rows-20261121"
BREAKS = ("break-after", "page-break-after", "break-inside", "page-break-inside")
EXPECTED = "63a6dde9780ebc15dcc2b1c73c6cd25627ad550ad8f37384d8a0788192772738"


def baseline(case):
    return (SNAPSHOTS if case == "A-contract-docx" else BASE) / case / "candidate.docx"


def normalize_links(record, expected_input_suffix):
    """Relocate only known file:///.../input stylesheet links, preserving resource identity."""
    result = copy.deepcopy(record)
    from urllib.parse import unquote, urlsplit

    for link in result["print_context"]["cssom"]["links"]:
        parsed = urlsplit(link["href"])
        path = unquote(parsed.path).replace("\\", "/")
        suffix = expected_input_suffix.replace("\\", "/").rstrip("/") + "/"
        if parsed.scheme != "file" or suffix not in path or parsed.query or parsed.fragment:
            raise ValueError("Unexpected stylesheet source relocation")
        relative = path.split(suffix, 1)[1]
        if not relative or ".." in Path(relative).parts:
            raise ValueError("Unbounded stylesheet source relocation")
        link["href"] = "input/" + relative
    return result


def core_equal(old, new, case, out):
    stripped = copy.deepcopy(new)
    if len(old["elements"]) != len(new["elements"]):
        return False
    for old_node, new_node in zip(old["elements"], stripped["elements"], strict=True):
        if new_node["tag"] == "document":
            continue  # Parser-only wrapper has no computed DOM style.
        if set(new_node["style"]) != set(old_node["style"]) | set(BREAKS):
            return False
        for key in BREAKS:
            value = new_node["style"].pop(key)
            if not isinstance(value, str) or not value:
                return False
    old_suffix = f"artifacts/natural-merged-rows-20261121/{case}/input"
    new_suffix = (out / case / "input").resolve().as_posix()
    return normalize_links(old, old_suffix) == normalize_links(stripped, new_suffix)


def source_pixels_equal(before, after):
    import pypdfium2 as pdfium
    from PIL import ImageChops

    with pdfium.PdfDocument(str(before)) as a, pdfium.PdfDocument(str(after)) as b:
        if len(a) != len(b):
            return False
        for page_a, page_b in zip(a, b, strict=True):
            if page_a.get_size() != page_b.get_size():
                return False
            images = [page.render(scale=800 / page.get_width()).to_pil().convert("RGB") for page in (page_a, page_b)]
            if images[0].size != images[1].size or ImageChops.difference(*images).getbbox() is not None:
                return False
    return True


def prepare(out):
    out.mkdir(parents=True, exist_ok=False)
    write(out / "environment.json", environment_gate(ROOT))
    write(
        out / "schema.json",
        audit_schemas(ROOT / "artifacts/alignment-aware-print-margins-20261121", [c for c, _ in CASES]),
    )
    cases = {}
    for case, relative in CASES:
        folder = out / case
        folder.mkdir()
        source, assets = copy_inputs(ROOT / relative, folder / "input")
        write(folder / "input-manifest.json", assets)
        old_assets = json.loads((BASE / case / "input-manifest.json").read_text(encoding="utf-8"))
        if assets != old_assets:
            raise ValueError(f"Source/asset manifest changed: {case}")
        old = json.loads((SNAPSHOTS / case / "browser-styles.json").read_text(encoding="utf-8"))
        styled = restore_snapshot(source, old)
        semantic = semantic_snapshot(source, baseline(case), styled)
        write(folder / "archived-baseline-semantic.json", semantic)
        if not semantic_pass(semantic):
            raise ValueError(f"Archived baseline semantics not perfect: {case}")
        cases[case] = {
            "source_sha256": sha(source),
            "baseline_sha256": sha(baseline(case)),
            "snapshot_sha256": sha(SNAPSHOTS / case / "browser-styles.json"),
            "source_pdf_sha256": sha(BASE / case / "browser.pdf"),
        }
    write(
        out / "prepared.json",
        {"base": "c1d605ec0482b7d846ca9549c29114e43c29cad2", "outcome": "PREPARED_ZERO_BROWSER", "cases": cases},
    )


def capture_once(out):
    if (out / "browser-attempt.json").exists():
        raise ValueError("Browser set already attempted; no retry")
    prepared = json.loads((out / "prepared.json").read_text(encoding="utf-8"))
    if prepared["outcome"] != "PREPARED_ZERO_BROWSER":
        raise ValueError("Environment/schema/source preparation missing")
    environment_gate(ROOT)
    report = {"base": prepared["base"], "outcome": "BROWSER_STARTED", "started": [], "cases": {}, "wps_exports": 0}
    write(out / "browser-attempt.json", report)
    for case, _ in CASES:
        folder = out / case
        try:
            source = next((folder / "input").glob("*.html"))
            prior = prepared["cases"][case]
            if sha(source) != prior["source_sha256"] or sha(baseline(case)) != prior["baseline_sha256"]:
                raise ValueError("Source/baseline changed after preparation")
            if sha(SNAPSHOTS / case / "browser-styles.json") != prior["snapshot_sha256"]:
                raise ValueError("Archived source snapshot changed")
            if sha(BASE / case / "browser.pdf") != prior["source_pdf_sha256"]:
                raise ValueError("Archived source PDF changed")
            # Recheck every frozen asset byte/existence before the single source load.
            for item in json.loads((folder / "input-manifest.json").read_text(encoding="utf-8")):
                path = folder / "input" / item["reference"]
                if path.is_file() != item["exists"] or (item["exists"] and sha(path) != item["sha256"]):
                    raise ValueError("Copied input asset changed")
            report["started"].append(case)
            write(out / "browser-attempt.json", report)
            styled = html_styles.load(source)
            new = snapshot(styled)
            write(folder / "browser-styles.json", new)
            old = json.loads((SNAPSHOTS / case / "browser-styles.json").read_text(encoding="utf-8"))
            if new["mode"] != "browser" or new["browser"] != "157.0.4341.60" or not core_equal(old, new, case, out):
                raise ValueError("Four-field/core/runtime metadata gate failed")
            rendered = render_html(source, folder / "browser.pdf", "pdf", margin_mm=10)
            write(folder / "browser-render.json", rendered)
            if not rendered[0]:
                raise ValueError("Reference print failed")
            if not source_pixels_equal(BASE / case / "browser.pdf", folder / "browser.pdf"):
                raise ValueError("Source page pixels changed")
            with ZipFile(baseline(case)) as z:
                infos = {i.filename: copy.copy(i) for i in z.infolist()}
            original_write = ZipFile.writestr

            def fixed(self, info, data, *args, original_write=original_write, infos=infos, **kwargs):
                return original_write(
                    self, copy.copy(infos[info.filename if isinstance(info, ZipInfo) else info]), data, *args, **kwargs
                )

            original_boundary = docx_styling.qualified_margin_boundary
            hits, attempts = [], []

            def traced(
                context,
                previous,
                node,
                ancestors,
                after,
                original_boundary=original_boundary,
                attempts=attempts,
                hits=hits,
            ):
                accepted = original_boundary(context, previous, node, ancestors, after)
                entry = {
                    "previous": previous.attrs.get("data-wps-i"),
                    "node": node.attrs.get("data-wps-i"),
                    "accepted": accepted,
                }
                attempts.append(entry)
                if accepted:
                    hits.append(entry)
                return accepted

            for name, legacy in (("baseline.docx", True), ("candidate.docx", False)):
                callback = (lambda *args: False) if legacy else traced
                with (
                    patch.object(html_styles, "load", return_value=styled),
                    patch.object(ZipFile, "writestr", fixed),
                    patch.object(docx_styling, "qualified_margin_boundary", side_effect=callback),
                ):
                    converted = convert_html_editable(source, folder / name, use_browser=False)
                if not converted[0]:
                    raise ValueError(converted)
            write(folder / "qualification.json", {"attempts": attempts, "hits": hits})
            expected_hits = ["51", "55"] if case == "A-contract-docx" else []
            if [h["node"] for h in hits] != expected_hits:
                raise ValueError("Unexpected qualification hits")
            if (folder / "baseline.docx").read_bytes() != baseline(case).read_bytes():
                raise ValueError("Legacy control bytes differ")
            with ZipFile(baseline(case)) as a, ZipFile(folder / "candidate.docx") as b:
                if a.namelist() != b.namelist():
                    raise ValueError("Package members differ")
                for name in a.namelist():
                    before, after = a.read(name), b.read(name)
                    expected = (
                        patch_xml(before) if case == "A-contract-docx" and name == "word/document.xml" else before
                    )
                    if after != expected:
                        raise ValueError(f"Exact inverse/parts gate failed: {name}")
            if case == "A-contract-docx":
                if sha(folder / "candidate.docx") != EXPECTED:
                    raise ValueError("Not the exact Stage48 candidate")
            elif (folder / "candidate.docx").read_bytes() != baseline(case).read_bytes():
                raise ValueError("Unchanged case ZIP differs")
            replay = restore_snapshot(source, new)
            semantic = {
                name: semantic_snapshot(source, folder / name, replay) for name in ("baseline.docx", "candidate.docx")
            }
            write(folder / "semantic.json", semantic)
            if not all(semantic_pass(r) for r in semantic.values()):
                raise ValueError("Exact-snapshot baseline/candidate semantics failed")
            report["cases"][case] = {
                "hits": len(hits),
                "candidate_sha256": sha(folder / "candidate.docx"),
                "core_and_source_pixels_identical": True,
                "package_inverse": True,
                "semantics": True,
            }
        except Exception as error:
            report.update(outcome="STOP_BEFORE_WPS", stop_case=case, error=f"{type(error).__name__}: {error}")
            write(out / "browser-attempt.json", report)
            return
        write(out / "browser-attempt.json", report)
    report["outcome"] = "OFFLINE_PASS_AWAITING_NATIVE_REVIEW"
    write(out / "browser-attempt.json", report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--capture-browser", action="store_true")
    args = parser.parse_args()
    capture_once(args.out) if args.capture_browser else prepare(args.out)
