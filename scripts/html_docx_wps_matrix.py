"""Record exactly five existing HTML-to-DOCX cases, without changing inputs or tolerances.

Requires existing HTML/fidelity dependencies, Playwright, Edge and WPS on Windows.
Use a writable TEMP; refuses existing output directories and running WPS processes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from direct_container_evidence import write  # noqa: E402
from fidelity_baselines import KNOWN_DEVIATIONS  # noqa: E402

from wps_ai_agent_cli.fidelity import fidelity_check, missing_fonts, score_layout  # noqa: E402
from wps_ai_agent_cli.html_editable import convert_html_editable  # noqa: E402
from wps_ai_agent_cli.html_render import render_html  # noqa: E402
from wps_ai_agent_cli.html_styles import _walk, load  # noqa: E402
from wps_ai_agent_cli.wps_convert import wps_convert  # noqa: E402

CASES = (
    ("A-report-docx", "fixtures/html_complex/report.html"),
    ("A-contract-docx", "fixtures/fidelity/contract.html"),
    ("A-newsletter-docx", "fixtures/fidelity/newsletter.html"),
    ("A-manual-docx", "fixtures/fidelity/manual.html"),
    ("A-pdfsource-docx", "fixtures/fidelity/pdf_source.html"),
)
HISTORICAL_WPS = dict(zip((case for case, _path in CASES), (0.9236, 0.8491, 0.9170, 0.8873, 0.9123), strict=True))


def probe_wps():
    done = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            "[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false); "
            "[pscustomobject]@{processes=@(Get-Process wps,et,wpp -ErrorAction SilentlyContinue | "
            "Select-Object Id,ProcessName,MainWindowTitle); executables=@(Get-Item -Path "
            "'C:\\Program Files (x86)\\Kingsoft\\WPS Office\\*\\office6\\wps.exe' "
            "-ErrorAction SilentlyContinue | ForEach-Object { [pscustomobject]@{"
            "path=$_.FullName;file_version=$_.VersionInfo.FileVersion;product_version=$_.VersionInfo.ProductVersion}})"
            "} | ConvertTo-Json -Depth 6",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    record = {"returncode": done.returncode, "stdout": done.stdout, "stderr": done.stderr}
    try:
        state = json.loads(done.stdout) if done.returncode == 0 else None
    except json.JSONDecodeError:
        state = None
    return record, state


def acceptance(case, semantic, layout):
    """Keep strict F2 and decision 10 distinct; unavailable layout is never a pass."""
    verdict = dict(semantic.get("verdict", {}))
    measured = layout.get("status") == "measured" and layout.get("renderer") == "wps"
    verdict["layout"] = bool(measured and layout.get("score", 0) >= 0.90)
    semantic_ok = semantic.get("group") == "A" and all(
        semantic.get("aspects", {}).get(name, {}).get("score") == 1.0 for name in ("text", "structure", "formatting")
    )
    strict = bool(semantic_ok and all(verdict.values()))
    failed = [name for name, passed in verdict.items() if not passed]
    deviation = KNOWN_DEVIATIONS.get(case)
    known = bool(
        semantic_ok
        and measured
        and layout.get("renderer") == "wps"
        and failed == ["layout"]
        and deviation
        and layout.get("score", 0) >= deviation[0]
    )
    return {
        "strict_f2": {"passed": strict, "verdict": verdict, "layout_minimum": 0.90},
        "decision10": {
            "status": "strict_pass" if strict else "known_deviation" if known else "not_accepted",
            "floor": deviation[0] if deviation else None,
            "historical_reason": deviation[1] if known else None,
        },
    }


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "img" and attrs.get("src"):
            self.refs.append(attrs["src"])
        if tag == "link" and attrs.get("rel", "").lower() == "stylesheet" and attrs.get("href"):
            self.refs.append(attrs["href"])


def copy_inputs(source, folder):
    folder.mkdir()
    parser = Assets()
    parser.feed(source.read_text(encoding="utf-8"))
    manifest = []
    for ref in [source.name, *dict.fromkeys(parser.refs)]:
        path = (source.parent / ref).resolve()
        local = path == source or source.parent.resolve() in path.parents
        exists = local and path.is_file()
        entry = {
            "reference": ref,
            "exists": exists,
            "repository_path": path.relative_to(ROOT).as_posix() if local else None,
        }
        if exists:
            entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            target = folder / path.relative_to(source.parent)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        manifest.append(entry)
    return folder / source.name, manifest


def color_pages(pdf, folder, prefix):
    import pypdfium2 as pdfium

    paths = []
    document = pdfium.PdfDocument(str(pdf))
    try:
        for i in range(len(document)):
            page = document[i]
            path = folder / f"{prefix}-{i + 1:03d}.png"
            page.render(scale=800 / page.get_width()).to_pil().convert("RGB").save(path)
            page.close()
            paths.append(str(path))
    finally:
        document.close()
    return paths


def run_case(case, relative, folder, baselines):
    folder.mkdir()
    source, manifest = copy_inputs(ROOT / relative, folder / "input")
    write(folder / "input-manifest.json", manifest)
    report = {"case": case, "original_source": relative, "input_manifest": manifest}
    styled = load(source)
    write(
        folder / "browser-styles.json",
        {
            "mode": styled.mode,
            "browser": styled.browser,
            "warnings": styled.warnings,
            "elements": [
                {
                    "tag": n.tag,
                    "attrs": n.attrs,
                    "style": styled.style(n),
                    "box": styled.box(n),
                    **({"summary_marker": styled.summary_markers.get(id(n))} if n.tag == "summary" else {}),
                }
                for n in _walk(styled.root)
            ],
        },
    )
    report["browser_version"] = styled.browser
    target, browser_pdf, wps_pdf = folder / "converted.docx", folder / "browser.pdf", folder / "wps.pdf"
    converted = convert_html_editable(source, target)
    write(folder / "conversion.json", converted)
    rendered = render_html(source, browser_pdf, "pdf", margin_mm=10)
    write(folder / "browser-render.json", rendered)
    semantic = fidelity_check(source, target, layout=False) if converted[0] else (False, {}, converted[2])
    write(folder / "semantic-fidelity.json", semantic)
    report["semantic"] = semantic[1]
    raw_probe, state = probe_wps()
    write(folder / "wps-probe.json", raw_probe)
    isolated = state is not None and not state.get("processes")
    report["wps_executables"] = state.get("executables", []) if state else []
    if not isolated:
        exported = (
            False,
            {},
            [
                {
                    "code": "WPS_SESSION_NOT_ISOLATED",
                    "message": "Existing WPS processes or failed probe; no COM operation attempted.",
                }
            ],
        )
    elif converted[0] and rendered[0]:
        exported = wps_convert(target, wps_pdf, timeout_seconds=120)
    else:
        exported = (False, {}, [{"code": "REFERENCE_NOT_AVAILABLE", "message": "Conversion or browser render failed."}])
    write(folder / "wps-export.json", exported)
    report["execution_ok"] = bool(
        styled.mode == "browser" and converted[0] and rendered[0] and semantic[0] and exported[0]
    )
    layout = (
        score_layout(browser_pdf, wps_pdf, renderer="wps", images_dir=folder / "pages")
        if exported[0] and rendered[0]
        else {"status": "unavailable"}
    )
    report["layout"] = layout
    report["execution_ok"] = bool(report["execution_ok"] and layout.get("status") == "measured")
    if exported[0] and rendered[0]:
        report["color_pages"] = {
            "browser": color_pages(browser_pdf, folder, "browser-page"),
            "wps": color_pages(wps_pdf, folder, "wps-page"),
        }
    report.update(acceptance(case, semantic[1], layout))
    report["environment"] = {
        "missing_fonts": missing_fonts(),
        "missing_input_assets": [e["reference"] for e in manifest if not e["exists"]],
        "limit": "Missing fallback does not establish missing effective font. Glyph-vs-layout attribution requires page review.",
    }
    report["historical"] = {
        "libreoffice": baselines.get(case),
        "libreoffice_comparable_to_wps": False,
        "prior_wps_layout": HISTORICAL_WPS[case],
        "source": "docs/PHASE13_PLAN.md, tenth Windows check",
        "limit": "Historical host/version conditions are not revalidated; no cross-renderer baseline-minus-0.02 rule applied.",
    }
    report["hashes"] = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (source, target, browser_pdf, wps_pdf)
        if p.is_file()
    }
    write(folder / "result.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    raw, state = probe_wps()
    write(out / "initial-wps-probe.json", raw)
    summary = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "git_head": "unavailable",
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cases": {},
        "not_run": [],
    }
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10)
        if head.returncode == 0:
            summary["git_head"] = head.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    baselines = json.loads((ROOT / "config/fidelity_baselines.json").read_text(encoding="utf-8"))["cases"]
    blocked = state is None or bool(state.get("processes"))
    for case, source in CASES:
        if blocked:
            summary["not_run"].append(case)
            continue
        try:
            result = run_case(case, source, out / case, baselines)
        except Exception as exc:
            result = {"execution_ok": False, "error_type": type(exc).__name__, "error": str(exc)}
            (out / case).mkdir(exist_ok=True)
            write(out / case / "error.json", result)
        summary["cases"][case] = result
        blocked = not result["execution_ok"]
        write(out / "matrix.json", summary)
        print(
            json.dumps(
                {
                    "case": case,
                    "execution_ok": result["execution_ok"],
                    "strict_f2": result.get("strict_f2"),
                    "decision10": result.get("decision10"),
                    "layout": result.get("layout"),
                }
            ),
            flush=True,
        )
    write(out / "matrix.json", summary)
    if summary["not_run"]:
        print("Stopped without modifying WPS installation or terminating processes; see probe/error JSON.", flush=True)


if __name__ == "__main__":
    main()
