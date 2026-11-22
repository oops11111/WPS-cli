"""Reproduce the three fixed HTML-to-PPTX baseline cases on Windows.

Run with PYTHONPATH=src and the repository's test dependencies installed. This
does not alter the source files or product implementation. ``--renderer none``
still checks semantic and package content, but does not prove visual fidelity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from wps_ai_agent_cli.convert import convert
from wps_ai_agent_cli.fidelity import fidelity_check

ROOT = Path(__file__).resolve().parents[1]
AUDIT_TEMP = ROOT / ".tmp" / "html-pptx-stage0"
CASES = (
    ("A-launch-pptx", ROOT / "fixtures/html_complex/launch.html", "editable"),
    ("A-training-pptx", ROOT / "fixtures/fidelity/training.html", "appearance"),
    ("A-quarterly-pptx", ROOT / "fixtures/fidelity/quarterly.html", "editable"),
)
LOCAL_ASSETS = {"A-launch-pptx": ("chart.png",)}
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _writable_mkdtemp(suffix: str = "", prefix: str = "tmp", dir: str | None = None) -> str:
    """Avoid restrictive tempfile Windows ACLs in managed sandbox processes."""
    root = Path(dir) if dir else AUDIT_TEMP
    root.mkdir(parents=True, exist_ok=True)
    for _ in range(10):
        path = root / f"{prefix}{uuid.uuid4().hex}{suffix}"
        try:
            path.mkdir()
        except FileExistsError:
            continue
        return str(path)
    raise FileExistsError("Could not create an audit temporary directory")


def _slides(path: Path) -> list[dict]:
    result = []
    with zipfile.ZipFile(path) as package:
        names = sorted(
            (name for name in package.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml")),
            key=lambda name: int(Path(name).stem[5:]),
        )
        for name in names:
            root = ET.fromstring(package.read(name))
            effects = []
            for node in root.iter(f"{P}cTn"):
                preset = node.get("presetClass")
                if not preset:
                    continue
                start = node.find(f"{P}stCondLst/{P}cond")
                targets = []
                for target in node.iter(f"{P}spTgt"):
                    paragraph = target.find(f"{P}txEl/{P}pRg")
                    targets.append(
                        {
                            "shape_id": target.get("spid"),
                            "paragraph": paragraph.get("st") if paragraph is not None else None,
                        }
                    )
                effects.append(
                    {
                        "class": preset,
                        "preset": node.get("presetID"),
                        "subtype": node.get("presetSubtype"),
                        "node_type": node.get("nodeType"),
                        "duration_ms": node.get("dur"),
                        "delay_ms": start.get("delay") if start is not None else None,
                        "targets": targets,
                    }
                )
            transition = root.find(f"{P}transition")
            result.append(
                {
                    "slide": len(result) + 1,
                    "transition": (
                        transition[0].tag.rsplit("}", 1)[-1] if transition is not None and len(transition) else None
                    ),
                    "effects": effects,
                }
            )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--renderer", choices=("none", "wps", "libreoffice"), default="none")
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    AUDIT_TEMP.mkdir(parents=True, exist_ok=True)
    # The managed Windows sandbox can create a tempfile directory but denies
    # writing inside it. Use ordinary directories, only in this audit process.
    tempfile.mkdtemp = _writable_mkdtemp
    manifest = {
        "baseline": "e6b7405b3602f4a0bf11ddf84d5442ce65c6c7d8",
        "renderer": args.renderer,
        "python": sys.version.split()[0],
        "cases": {},
    }
    for case, source, fidelity in CASES:
        folder = out / case
        folder.mkdir(exist_ok=True)
        shutil.copyfile(source, folder / source.name)
        for name in LOCAL_ASSETS.get(case, ()):
            shutil.copyfile(source.parent / name, folder / name)
        local = folder / source.name
        target = folder / "candidate.pptx"
        ok, data, errors = convert(local, target, fidelity=fidelity)
        entry = {
            "source": str(source.relative_to(ROOT)).replace("\\", "/"),
            "source_sha256": _sha(source),
            "mode": fidelity,
            "conversion": {"ok": ok, "data": data, "errors": errors},
        }
        if ok:
            entry["pptx_sha256"] = _sha(target)
            entry["slides"] = _slides(target)
            checked, report, check_errors = fidelity_check(
                local, target, renderer=args.renderer, layout=args.renderer != "none", images_dir=folder / "pages"
            )
            entry["fidelity"] = {"ok": checked, "report": report, "errors": check_errors}
        entry["files_sha256"] = {
            str(path.relative_to(folder)).replace("\\", "/"): _sha(path)
            for path in sorted(folder.rglob("*"))
            if path.is_file()
        }
        manifest["cases"][case] = entry
        (out / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        print(case, "converted=" + str(ok), "fidelity=" + str(entry.get("fidelity", {}).get("ok")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
