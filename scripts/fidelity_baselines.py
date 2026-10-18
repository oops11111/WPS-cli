"""Phase 13 conversion matrix: run every fixture conversion, score it, and record or check the baselines.

    python scripts/fidelity_baselines.py              # run the matrix, print the scores, compare with the baselines
    python scripts/fidelity_baselines.py --write      # record the scores in config/fidelity_baselines.json
    python scripts/fidelity_baselines.py --make-fixtures   # rebuild the binary fixtures (needs LibreOffice)
    python scripts/fidelity_baselines.py --renderer wps --wps   # on Windows: WPS layout scores and group B

Each case converts a fixture from fixtures/fidelity/ (or fixtures/html_complex/) with `convert` and scores it with
`fidelity-check`. Layout is measured with LibreOffice here (decision 1: the regression baseline); on Windows,
`--renderer wps` gives the official WPS scores. A case fails when a thresholded aspect is below its threshold, or
its LibreOffice layout falls more than 0.02 below the recorded baseline.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wps_ai_agent_cli.convert import convert  # noqa: E402
from wps_ai_agent_cli.fidelity import fidelity_check  # noqa: E402

FIXTURES = ROOT / "fixtures" / "fidelity"
COMPLEX = ROOT / "fixtures" / "html_complex"
BASELINES = ROOT / "config" / "fidelity_baselines.json"

# (case id, source fixture, target extension, convert options, measure layout)
CASES: list[tuple[str, Path, str, dict, bool]] = [
    ("A-report-docx", COMPLEX / "report.html", ".docx", {}, True),
    ("A-contract-docx", FIXTURES / "contract.html", ".docx", {}, True),
    ("A-newsletter-docx", FIXTURES / "newsletter.html", ".docx", {}, True),
    ("A-manual-docx", FIXTURES / "manual.html", ".docx", {}, True),
    ("A-pdfsource-docx", FIXTURES / "pdf_source.html", ".docx", {}, True),
    ("A-budget-xlsx", COMPLEX / "budget.html", ".xlsx", {}, False),
    ("A-launch-pptx", COMPLEX / "launch.html", ".pptx", {}, True),
    ("A-training-pptx", FIXTURES / "training.html", ".pptx", {"fidelity": "appearance"}, True),
    ("A-quarterly-pptx", FIXTURES / "quarterly.html", ".pptx", {}, True),
    ("A-brief-html", FIXTURES / "brief.docx", ".html", {}, False),
    ("A-deck-html", FIXTURES / "deck.pptx", ".html", {}, False),
    ("A-book-html", FIXTURES / "book.xlsx", ".html", {}, False),
    ("C-gbk-csv-xlsx", FIXTURES / "sales_gbk.csv", ".xlsx", {}, False),
    ("C-utf8-tsv-xlsx", FIXTURES / "staff_utf8.tsv", ".xlsx", {}, False),
    ("C-book-csv", FIXTURES / "book.xlsx", ".csv", {}, False),
    ("C-guide-docx", FIXTURES / "guide.md", ".docx", {}, False),
    ("C-api-html", FIXTURES / "api.md", ".html", {}, False),
    ("C-notes-docx", FIXTURES / "notes.md", ".docx", {}, False),
    ("C-brief-md", FIXTURES / "brief.docx", ".md", {}, False),
    ("D-brief-pptx", FIXTURES / "brief.docx", ".pptx", {}, False),
    ("D-deck-docx", FIXTURES / "deck.pptx", ".docx", {}, False),
    ("D-book-docx", FIXTURES / "book.xlsx", ".docx", {}, False),
    ("D-book-pptx", FIXTURES / "book.xlsx", ".pptx", {}, False),
    ("E-supplier-docx", FIXTURES / "supplier.pdf", ".docx", {}, True),
    ("E-supplier-xlsx", FIXTURES / "supplier.pdf", ".xlsx", {}, False),
    ("E-supplier-pptx", FIXTURES / "supplier.pdf", ".pptx", {}, False),
]


# Group B, through WPS on Windows (--wps): (case id, source, target extension, the file the source was made from).
# Legacy and ODF sources are compared with the OOXML file they were saved from; PNG pages are not scored.
WPS_CASES: list[tuple[str, Path, str, Path | None]] = [
    ("B-doc-docx", FIXTURES / "brief.doc", ".docx", FIXTURES / "brief.docx"),
    ("B-odt-docx", FIXTURES / "brief.odt", ".docx", FIXTURES / "brief.docx"),
    ("B-xls-xlsx", FIXTURES / "book.xls", ".xlsx", FIXTURES / "book.xlsx"),
    ("B-ppt-pptx", FIXTURES / "deck.ppt", ".pptx", FIXTURES / "deck.pptx"),
    ("B-docx-wps", FIXTURES / "brief.docx", ".wps", None),
    ("B-xlsx-et", FIXTURES / "book.xlsx", ".et", None),
    ("B-pptx-dps", FIXTURES / "deck.pptx", ".dps", None),
    ("B-docx-odt", FIXTURES / "brief.docx", ".odt", None),
    ("B-pptx-png", FIXTURES / "deck.pptx", ".png", None),
]


def run_wps(renderer: str) -> dict[str, dict]:
    """Group B with WPS: text, structure and the layout of WPS's PDFs before and after (F3)."""
    results: dict[str, dict] = {}
    with tempfile.TemporaryDirectory(prefix="wps-fidelity-b-", ignore_cleanup_errors=True) as tmp:
        work = Path(tmp)
        for item in FIXTURES.iterdir():
            if item.is_file():
                shutil.copyfile(item, work / item.name)
        for case, fixture, suffix, reference in WPS_CASES:
            source = work / fixture.name
            target = work / f"{case}{suffix}"
            ok, data, errors = convert(source, target)
            if not ok:
                results[case] = {"converted": False, "errors": errors}
                continue
            if suffix == ".png":
                results[case] = {"converted": True, "pages": len(data.get("pages", [])), "passed": True}
                continue
            original, converted = (work / reference.name if reference else source), target
            if suffix in {".wps", ".et", ".dps", ".odt"}:
                # Read the WPS-format copy back through WPS to compare it.
                back = work / f"{case}-back{source.suffix}"
                ok, _data, errors = convert(target, back)
                if not ok:
                    results[case] = {"converted": True, "errors": errors}
                    continue
                converted = back
            checked, report, check_errors = fidelity_check(original, converted, renderer=renderer)
            if not checked:
                results[case] = {"converted": True, "errors": check_errors}
                continue
            results[case] = {
                "converted": True,
                "group": "B",
                "route": data.get("route"),
                "scores": {n: a["score"] for n, a in report["aspects"].items() if "score" in a},
                "verdict": report["verdict"],
                "passed": report["passed"],
            }
    return results


def run(renderer: str, use_browser: bool) -> dict[str, dict]:
    results: dict[str, dict] = {}
    with tempfile.TemporaryDirectory(prefix="wps-fidelity-matrix-", ignore_cleanup_errors=True) as tmp:
        work = Path(tmp)
        for folder in (FIXTURES, COMPLEX):
            for item in folder.iterdir():
                if item.is_file() and not (work / item.name).exists():
                    shutil.copyfile(item, work / item.name)
        for case, fixture, suffix, options, layout in CASES:
            source = work / fixture.name
            target = work / f"{case}{suffix}"
            ok, data, errors = convert(source, target, use_browser=use_browser, **options)
            if not ok:
                results[case] = {"converted": False, "errors": errors}
                continue
            checked, report, check_errors = fidelity_check(
                source, target, renderer=renderer if layout else "none", layout=layout, use_browser=use_browser
            )
            if not checked:
                results[case] = {"converted": True, "errors": check_errors}
                continue
            scores = {name: aspect["score"] for name, aspect in report["aspects"].items() if "score" in aspect}
            results[case] = {
                "converted": True,
                "group": report["group"],
                "route": data.get("route"),
                "scores": scores,
                "verdict": report["verdict"],
                "passed": report["passed"],
                "layout_renderer": report["aspects"]["layout"].get("renderer"),
            }
    return results


def compare(results: dict[str, dict], baselines: dict[str, dict]) -> list[str]:
    problems = []
    for case, result in results.items():
        if result.get("converted") and result.get("passed") and "scores" not in result:
            continue  # PNG pages
        if not result.get("converted") or "scores" not in result:
            problems.append(f"{case}: {result.get('errors')}")
            continue
        if not result["passed"]:
            failed = [name for name, ok in result["verdict"].items() if not ok]
            problems.append(f"{case}: below threshold in {failed}: {result['scores']}")
        # The recorded baselines are LibreOffice's; with the official WPS renderer only the threshold applies.
        recorded = baselines.get(case, {}).get("scores", {}).get("layout")
        layout = result["scores"].get("layout")
        if (
            result.get("layout_renderer") == "libreoffice"
            and recorded is not None
            and layout is not None
            and layout < recorded - 0.02
        ):
            problems.append(f"{case}: layout {layout} fell below the baseline {recorded} - 0.02")
    return problems


def make_fixtures() -> None:
    """Rebuild the binary fixtures from the text ones (LibreOffice makes the PDF and the legacy formats)."""
    import pypdfium2 as pdfium

    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise SystemExit("LibreOffice (soffice) is needed to rebuild the binary fixtures")
    with tempfile.TemporaryDirectory(prefix="wps-fixtures-") as tmp:
        work = Path(tmp)
        for item in list(FIXTURES.iterdir()) + [COMPLEX / "report.html"]:
            if item.is_file():
                shutil.copyfile(item, work / item.name)
        made = {
            "supplier.docx": ("pdf_source.html", ".docx"),
            "brief.docx": ("contract.html", ".docx"),
            "deck.pptx": ("quarterly.html", ".pptx"),
            "book.xlsx": ("sales_gbk.csv", ".xlsx"),
        }
        for name, (source, _suffix) in made.items():
            (work / name).unlink(missing_ok=True)
            ok, _data, errors = convert(work / source, work / name, use_browser=False)
            if not ok:
                raise SystemExit(f"{name}: {errors}")
        profile = Path(tempfile.mkdtemp(prefix="wps-lo-"))

        def office(target: str, *names: str) -> None:
            subprocess.run(
                [
                    soffice,
                    f"-env:UserInstallation={profile.as_uri()}",
                    "--headless",
                    "--convert-to",
                    target,
                    "--outdir",
                    str(work),
                    *[str(work / n) for n in names],
                ],
                check=True,
                capture_output=True,
                timeout=300,
            )

        office("pdf", "supplier.docx")
        office("doc", "brief.docx")
        office("xls", "book.xlsx")
        office("ppt", "deck.pptx")
        office("odt", "brief.docx")
        shutil.rmtree(profile, ignore_errors=True)
        # The scanned copy: each page as a 150 dpi greyscale image, without a text layer.
        document = pdfium.PdfDocument(str(work / "supplier.pdf"))
        pages = [document[i].render(scale=150 / 72).to_pil().convert("L") for i in range(len(document))]
        document.close()
        pages[0].save(work / "supplier_scanned.pdf", save_all=True, append_images=pages[1:], resolution=150)
        for name in (
            "supplier.pdf",
            "supplier_scanned.pdf",
            "brief.docx",
            "deck.pptx",
            "book.xlsx",
            "brief.doc",
            "book.xls",
            "deck.ppt",
            "brief.odt",
        ):
            shutil.copyfile(work / name, FIXTURES / name)
            print(f"wrote fixtures/fidelity/{name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write", action="store_true", help="record the scores as the new baselines")
    parser.add_argument("--make-fixtures", action="store_true", help="rebuild the binary fixtures")
    parser.add_argument("--renderer", default="libreoffice", choices=["libreoffice", "wps", "none"])
    parser.add_argument("--no-browser", action="store_true", help="use the built-in CSS cascade")
    parser.add_argument("--wps", action="store_true", help="also run group B through WPS (Windows)")
    args = parser.parse_args()
    if args.make_fixtures:
        make_fixtures()
        return 0
    results = run(args.renderer, not args.no_browser)
    if args.wps:
        results.update(run_wps(args.renderer))
    for case, result in results.items():
        print(case, json.dumps(result.get("scores") or result.get("errors"), ensure_ascii=False))
    baselines = json.loads(BASELINES.read_text(encoding="utf-8"))["cases"] if BASELINES.is_file() else {}
    if args.write:
        BASELINES.write_text(
            json.dumps(
                {
                    "description": "Phase 13 conversion matrix scores (scripts/fidelity_baselines.py). Layout is "
                    "the LibreOffice regression baseline; WPS is the official renderer (decision 1).",
                    "renderer": args.renderer,
                    "browser": not args.no_browser,
                    "cases": {
                        case: {k: v for k, v in result.items() if k in {"group", "route", "scores", "passed"}}
                        for case, result in results.items()
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"wrote {BASELINES.relative_to(ROOT)}")
    problems = compare(results, baselines)
    for problem in problems:
        print("FAIL", problem)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
