"""Capture the fixed direct-container regression fixture; never tune it to a score.

Run with the project's test/HTML/fidelity dependencies and Playwright installed:
python scripts/direct_container_evidence.py --out artifacts/direct-container-evidence
Existing output files are not overwritten. Running WPS instances block COM export.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wps_ai_agent_cli.fidelity import fidelity_check, score_layout, ssim  # noqa: E402
from wps_ai_agent_cli.html_editable import convert_html_editable  # noqa: E402
from wps_ai_agent_cli.html_render import render_html  # noqa: E402
from wps_ai_agent_cli.html_styles import _walk, load  # noqa: E402
from wps_ai_agent_cli.wps_convert import wps_convert  # noqa: E402


def write(path, value):
    # Repository-local paths are recorded relative to the checkout for review/replay.
    def portable(item):
        if isinstance(item, dict):
            return {key: portable(val) for key, val in item.items()}
        if isinstance(item, (list, tuple)):
            return [portable(val) for val in item]
        if isinstance(item, str) and item.startswith(str(ROOT) + "\\"):
            return Path(item).relative_to(ROOT).as_posix()
        return item

    path.write_text(json.dumps(portable(value), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    source = ROOT / "fixtures/fidelity/direct_container.html"
    target, reference, rendered = out / "converted.docx", out / "browser.pdf", out / "wps.pdf"
    report = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "fixture": str(source.relative_to(ROOT)),
        "thresholds": {"layout": 0.90, "text": 1.0, "structure": 1.0},
        "scope": "Fixed stage-1 regression input; no fixture tuning or conversion-direction changes.",
    }
    styled = load(source)
    write(
        out / "browser-styles.json",
        {
            "mode": styled.mode,
            "browser": styled.browser,
            "warnings": styled.warnings,
            "elements": [
                {"tag": n.tag, "attrs": n.attrs, "style": styled.style(n), "box": styled.box(n)}
                for n in _walk(styled.root)
                if n.tag in {"body", "div", "section", "p", "span", "a", "b", "em"}
            ],
        },
    )
    converted = convert_html_editable(source, target)
    write(out / "conversion.json", converted)
    browser = render_html(source, reference, "pdf", margin_mm=10)
    write(out / "browser-render.json", browser)
    report["conversion_ok"], report["browser_ok"] = converted[0], browser[0]
    if converted[0]:
        semantic = fidelity_check(source, target, layout=False)
        write(out / "semantic-fidelity.json", semantic)
        report["semantic"] = semantic[1]
    probe = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            "[pscustomobject]@{processes=@(Get-Process wps,et,wpp -ErrorAction SilentlyContinue | "
            "Select-Object Id,ProcessName,MainWindowTitle); executables=@("
            "'C:\\Program Files (x86)\\Kingsoft\\office6\\wps.exe',"
            "'C:\\Program Files (x86)\\WPS Office\\office6\\wps.exe',"
            "'C:\\Program Files (x86)\\Kingsoft\\WPS Office\\*\\office6\\wps.exe' | "
            "ForEach-Object {Get-Item -Path $_ -ErrorAction SilentlyContinue} | "
            "Select-Object -ExpandProperty FullName | "
            "Where-Object {Test-Path -LiteralPath $_} | ForEach-Object {"
            "$f=Get-Item -LiteralPath $_; [pscustomobject]@{path=$f.FullName;version=$f.VersionInfo.FileVersion}})"
            "} | ConvertTo-Json -Depth 6",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    write(out / "wps-probe.json", {"returncode": probe.returncode, "stdout": probe.stdout, "stderr": probe.stderr})
    state = json.loads(probe.stdout) if probe.returncode == 0 and probe.stdout.strip() else None
    report["wps_version"] = state.get("executables", []) if state else None
    # Refuse attachment to an interactive session: this evidence run only starts its own WPS.
    if state is None or state["processes"]:
        export = (
            False,
            {},
            [
                {
                    "code": "EVIDENCE_WPS_SESSION_NOT_ISOLATED",
                    "message": "WPS probe failed or an existing WPS process is running.",
                }
            ],
        )
    elif converted[0]:
        export = wps_convert(target, rendered, timeout_seconds=120)
    else:
        export = (False, {}, [{"code": "CONVERSION_FAILED", "message": "DOCX not available."}])
    write(out / "wps-export.json", export)
    report["wps_export_ok"] = export[0]
    if export[0] and browser[0]:
        report["layout"] = score_layout(reference, rendered, renderer="wps", images_dir=out / "pages")
        report["visual_diagnostic"] = render_diagnostic(reference, rendered, out)
    report["hashes"] = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (source, target, reference, rendered) if p.is_file()
    }
    aspects = report.get("semantic", {}).get("aspects", {})
    report["accepted"] = bool(
        export[0]
        and report.get("layout", {}).get("status") == "measured"
        and report["layout"].get("score", 0) >= 0.90
        and all(aspects.get(key, {}).get("score") == 1.0 for key in ("text", "structure"))
    )
    write(out / "result.json", report)
    print(json.dumps(report, indent=2, ensure_ascii=False))


def render_diagnostic(reference, rendered, out):
    """Fixed top-300px content diagnostic; does not replace the full-page F2 gate."""
    import numpy as np
    import pypdfium2 as pdfium
    from PIL import Image

    images = []
    for path, name in ((reference, "browser-page.png"), (rendered, "wps-page.png")):
        document = pdfium.PdfDocument(str(path))
        try:
            page = document[0]
            image = page.render(scale=800 / page.get_width()).to_pil().convert("RGB")
            image.save(out / name)
            images.append(image)
            page.close()
        finally:
            document.close()
    first, second = images
    second = second.resize(first.size)
    bounds = (0, 0, first.width, min(300, first.height))
    a, b = first.crop(bounds), second.crop(bounds)
    pair = Image.new("RGB", (a.width * 2 + 8, a.height), "gray")
    pair.paste(a, (0, 0))
    pair.paste(b, (a.width + 8, 0))
    pair.save(out / "content-top-300px.png")
    return {
        "region": list(bounds),
        "score": round(ssim(np.asarray(a.convert("L")), np.asarray(b.convert("L"))), 4),
        "purpose": "Fixed content-area diagnostic only; full-page F2 threshold is unchanged.",
    }


if __name__ == "__main__":
    main()
