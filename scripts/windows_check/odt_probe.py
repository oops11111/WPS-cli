"""Which ODT files WPS opens without its "文件损坏提示" prompt (B-odt-docx, Windows checks on c205851 and f8ed7bd).

    python scripts/windows_check/odt_probe.py --out DIR

WPS 12.8 asked whether to open LibreOffice's brief.odt, as ODF 1.3 and as ODF 1.2, as a damaged file, and the
conversion timed out waiting for the answer. This converts a few ODT variants to .docx through WPS, each with a
short timeout and WPS ended in between, and writes DIR/odt-probe.json:

- wps-written: brief.docx saved as .odt by WPS itself (the control: WPS reads it back in B-docx-odt)
- libreoffice: fixtures/fidelity/brief.odt (ODF 1.2 from LibreOffice)
- libreoffice-trimmed: the same without the thumbnail, settings, manifest.rdf and Configurations2
- minimal-ascii, minimal-cjk: a hand-written ODT with one paragraph (mimetype, manifest, content.xml)
- minimal-cjk-styles: the CJK one with a styles.xml and meta.xml as well

Run it with no WPS open; it ends the WPS it starts.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from fidelity_baselines import _release_wps, _wps_running  # noqa: E402

from wps_ai_agent_cli.wps_convert import wps_convert  # noqa: E402

MIMETYPE = "application/vnd.oasis.opendocument.text"
MANIFEST = """<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">
 <manifest:file-entry manifest:full-path="/" manifest:version="1.2" manifest:media-type="{mimetype}"/>
{entries}</manifest:manifest>
"""
OFFICE = (
    'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
    'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
    'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
    'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" '
    'xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0" office:version="1.2"'
)
CONTENT = (
    '<?xml version="1.0" encoding="UTF-8"?>\n<office:document-content {ns}><office:body><office:text>'
    "<text:p>{text}</text:p></office:text></office:body></office:document-content>\n"
)
STYLES = (
    '<?xml version="1.0" encoding="UTF-8"?>\n<office:document-styles {ns}><office:styles>'
    '<style:default-style style:family="paragraph"><style:text-properties fo:font-size="11pt"/>'
    "</style:default-style></office:styles></office:document-styles>\n"
)
META = (
    '<?xml version="1.0" encoding="UTF-8"?>\n<office:document-meta {ns}><office:meta>'
    "<meta:generator>wps-agent odt_probe</meta:generator></office:meta></office:document-meta>\n"
)


def _write_odt(path: Path, parts: dict[str, str]) -> None:
    """An ODT: the mimetype first and stored, then the parts, with a manifest that lists them."""
    entries = "".join(
        f' <manifest:file-entry manifest:full-path="{n}" manifest:media-type="text/xml"/>\n' for n in parts
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(zipfile.ZipInfo("mimetype"), MIMETYPE, compress_type=zipfile.ZIP_STORED)
        for name, text in parts.items():
            archive.writestr(name, text, compress_type=zipfile.ZIP_DEFLATED)
        archive.writestr(
            "META-INF/manifest.xml",
            MANIFEST.format(mimetype=MIMETYPE, entries=entries),
            compress_type=zipfile.ZIP_DEFLATED,
        )


def _trimmed(source: Path, target: Path) -> None:
    """The LibreOffice ODT without its thumbnail, settings, RDF metadata and UI configuration."""
    drop = ("Thumbnails/", "Configurations2/", "settings.xml", "manifest.rdf")
    with zipfile.ZipFile(source) as old, zipfile.ZipFile(target, "w") as new:
        for item in old.infolist():
            if item.filename.startswith(drop):
                continue
            data = old.read(item.filename)
            if item.filename == "META-INF/manifest.xml":
                lines = data.decode("utf-8").splitlines(keepends=True)
                data = "".join(line for line in lines if not any(f'full-path="{d}' in line for d in drop)).encode()
            kind = zipfile.ZIP_STORED if item.filename == "mimetype" else zipfile.ZIP_DEFLATED
            new.writestr(item, data, compress_type=kind)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=60, help="seconds for each conversion")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    ours = not _wps_running()
    fixtures = ROOT / "fixtures" / "fidelity"
    results = []
    with tempfile.TemporaryDirectory(prefix="wps-odt-probe-") as tmp:
        work = Path(tmp)
        variants: dict[str, Path] = {}
        shutil.copyfile(fixtures / "brief.docx", work / "brief.docx")
        _release_wps(ours)
        ok, _data, errors = wps_convert(work / "brief.docx", work / "wps-written.odt", timeout_seconds=args.timeout)
        if ok:
            variants["wps-written"] = work / "wps-written.odt"
        else:
            results.append({"variant": "wps-written", "step": "docx -> odt", "ok": False, "errors": errors})
        variants["libreoffice"] = work / "libreoffice.odt"
        shutil.copyfile(fixtures / "brief.odt", variants["libreoffice"])
        variants["libreoffice-trimmed"] = work / "libreoffice-trimmed.odt"
        _trimmed(fixtures / "brief.odt", variants["libreoffice-trimmed"])
        for name, text, extra in (
            ("minimal-ascii", "Hello from a minimal ODT", False),
            ("minimal-cjk", "技术服务合同", False),
            ("minimal-cjk-styles", "技术服务合同", True),
        ):
            parts = {"content.xml": CONTENT.format(ns=OFFICE, text=text)}
            if extra:
                parts["styles.xml"] = STYLES.format(ns=OFFICE)
                parts["meta.xml"] = META.format(ns=OFFICE)
            variants[name] = work / f"{name}.odt"
            _write_odt(variants[name], parts)
        for name, path in variants.items():
            shutil.copyfile(path, args.out / path.name)
            _release_wps(ours)
            started = time.monotonic()
            ok, data, errors = wps_convert(path, work / f"{name}.docx", timeout_seconds=args.timeout)
            results.append(
                {
                    "variant": name,
                    "ok": ok,
                    "seconds": round(time.monotonic() - started, 1),
                    "errors": errors,
                    "stage": data.get("stage"),
                    "wps_windows": data.get("wps_windows"),
                }
            )
            print(f"{name}: {'opens' if ok else errors[0]['code'] if errors else 'failed'}")
        _release_wps(ours)
    (args.out / "odt-probe.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
