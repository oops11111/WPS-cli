"""Audit the fixed HTML slide animations against the existing PPTX packages.

This records package semantics, not WPS playback. Run with PYTHONPATH=src.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from wps_ai_agent_cli.html_editable import _Node, _text, _TreeParser
from wps_ai_agent_cli.html_slides import _animation_of, _transition_of, parse_css

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts/html-pptx-full-canvas-verified-20261122"
CASES = {
    "launch": (ROOT / "fixtures/html_complex/launch.html", BASE / "A-launch-pptx/candidate.pptx"),
    "training": (ROOT / "fixtures/fidelity/training.html", BASE / "A-training-pptx/candidate.pptx"),
    "quarterly": (ROOT / "fixtures/fidelity/quarterly.html", BASE / "A-quarterly-pptx/candidate.pptx"),
}
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
R = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def descendants(node: _Node):
    for child in node.children:
        if isinstance(child, _Node):
            yield child
            yield from descendants(child)


def source(path: Path) -> list[dict]:
    html = path.read_text(encoding="utf-8")
    parser = _TreeParser()
    parser.feed(html)
    css = parse_css(html)
    sections = [node for node in descendants(parser.root) if node.tag == "section"]
    result = []
    for number, section in enumerate(sections, 1):
        transition, speed = _transition_of(section, css)
        effects = []
        notes = []
        for node in descendants(section):
            if "notes" in node.attrs.get("class", "").split():
                notes.append(_text(node).strip())
            animation = _animation_of(node, css)
            if animation:
                effects.append({"tag": node.tag, "text": " ".join(_text(node).split()), **vars(animation)})
        result.append({"slide": number, "transition": transition, "speed": speed, "notes": notes, "effects": effects})
    return result


def package(path: Path) -> list[dict]:
    result = []
    with zipfile.ZipFile(path) as archive:
        names = sorted(
            (name for name in archive.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml")),
            key=lambda name: int(Path(name).stem[5:]),
        )
        for number, name in enumerate(names, 1):
            root = ET.fromstring(archive.read(name))
            shape_text = {}
            paragraph_text = {}
            for node in root.iter():
                if node.tag not in {f"{P}sp", f"{P}graphicFrame", f"{P}pic"}:
                    continue
                marker = node.find(f"{P}nvSpPr/{P}cNvPr")
                if marker is None:
                    marker = node.find(f"{P}nvGraphicFramePr/{P}cNvPr")
                if marker is None:
                    marker = node.find(f"{P}nvPicPr/{P}cNvPr")
                if marker is not None:
                    spid = marker.get("id")
                    shape_text[spid] = " ".join(t.text or "" for t in node.iter(f"{A}t"))
                    paragraph_text[spid] = [
                        " ".join(t.text or "" for t in paragraph.iter(f"{A}t")) for paragraph in node.iter(f"{A}p")
                    ]
            effects = []
            for node in root.iter(f"{P}cTn"):
                if not node.get("presetClass"):
                    continue
                condition = node.find(f"{P}stCondLst/{P}cond")
                targets = []
                for target in node.iter(f"{P}spTgt"):
                    paragraph = target.find(f"{P}txEl/{P}pRg")
                    spid = target.get("spid")
                    value = {"shape_id": spid, "shape_text": shape_text.get(spid, "")}
                    if paragraph is not None:
                        value["paragraph"] = paragraph.get("st")
                        index = int(paragraph.get("st", "0"))
                        value["paragraph_text"] = (
                            paragraph_text.get(spid, [])[index] if index < len(paragraph_text.get(spid, [])) else None
                        )
                    if value not in targets:
                        targets.append(value)
                behaviors = [
                    child
                    for child in node.iter(f"{P}cTn")
                    if child is not node and child.get("dur") and child.get("dur") != "1"
                ]
                attrs = [name.text for name in node.iter(f"{P}attrName")]
                effect = next(iter(node.iter(f"{P}animEffect")), None)
                effects.append(
                    {
                        "class": node.get("presetClass"),
                        "preset": node.get("presetID"),
                        "subtype": node.get("presetSubtype"),
                        "node_type": node.get("nodeType"),
                        "delay_ms": condition.get("delay") if condition is not None else None,
                        "behavior_duration_ms": behaviors[0].get("dur") if behaviors else None,
                        "attributes": attrs,
                        "filter": effect.get("filter") if effect is not None else None,
                        "targets": targets,
                    }
                )
            transition = root.find(f"{P}transition")
            notes = []
            rel_name = f"ppt/slides/_rels/slide{number}.xml.rels"
            if rel_name in archive.namelist():
                rel_root = ET.fromstring(archive.read(rel_name))
                for rel in rel_root.iter(f"{R}Relationship"):
                    if not rel.get("Type", "").endswith("/notesSlide"):
                        continue
                    note_name = "ppt/notesSlides/" + rel.get("Target", "").split("/")[-1]
                    note_root = ET.fromstring(archive.read(note_name))
                    notes = [t.text for t in note_root.iter(f"{A}t") if t.text]
            result.append(
                {
                    "slide": number,
                    "transition": transition[0].tag.rsplit("}", 1)[-1]
                    if transition is not None and len(transition)
                    else None,
                    "transition_speed": transition.get("spd") if transition is not None else None,
                    "effects": effects,
                    "notes_xml_text": notes,
                }
            )
    return result


def compare(source_slides: list[dict], pptx_slides: list[dict]) -> list[dict]:
    """Match the fixed source inventory to OOXML; never treat counts alone as a pass."""
    findings = []
    if len(source_slides) != len(pptx_slides):
        return [{"status": "fail", "reason": "slide count differs"}]
    preset = {
        ("entrance", "fly", "left"): ("entr", "2", "8"),
        ("entrance", "fade", ""): ("entr", "10", "0"),
        ("entrance", "zoom", ""): ("entr", "53", "16"),
        ("exit", "fade", ""): ("exit", "10", "0"),
        ("emphasis", "pulse", ""): ("emph", "6", "0"),
    }
    for source_slide, target_slide in zip(source_slides, pptx_slides, strict=True):
        number = source_slide["slide"]
        if source_slide["transition"] != target_slide["transition"]:
            findings.append({"slide": number, "status": "fail", "reason": "transition kind differs"})
        if source_slide["speed"] != target_slide["transition_speed"]:
            findings.append({"slide": number, "status": "fail", "reason": "transition speed differs"})
        for note in source_slide["notes"]:
            if note not in target_slide["notes_xml_text"]:
                findings.append({"slide": number, "status": "fail", "reason": "speaker note missing"})
        sources = source_slide["effects"]
        targets = target_slide["effects"]
        if len(sources) != len(targets):
            findings.append({"slide": number, "status": "fail", "reason": "effect count differs"})
            continue
        previous_start = previous_duration = 0
        for index, (effect, target) in enumerate(zip(sources, targets, strict=True), 1):
            key = (effect["kind"], effect["effect"], effect["direction"])
            reasons = []
            if key not in preset:
                reasons.append("source effect has no audited preset mapping")
            elif (target["class"], target["preset"], target["subtype"]) != preset[key]:
                reasons.append("effect class/preset/direction differs")
            expected_node_type = "clickEffect" if effect["trigger"] == "click" else "withEffect"
            if target["node_type"] != expected_node_type:
                reasons.append("trigger grouping differs")
            expected_delay = effect["delay"]
            if effect["trigger"] == "after":
                expected_delay += previous_start + previous_duration
            if target["delay_ms"] != str(expected_delay):
                reasons.append("effect delay/order differs")
            if target["behavior_duration_ms"] != str(effect["duration"]):
                reasons.append("effect duration differs")
            if len(target["targets"]) != 1:
                reasons.append("target is missing or ambiguous")
            else:
                shape = target["targets"][0]
                source_text = re.sub(r"\s+", "", effect["text"])
                target_text = re.sub(r"\s+", "", shape.get("paragraph_text") or shape["shape_text"])
                if not source_text or source_text not in target_text:
                    reasons.append("shape/paragraph text does not identify source element")
            findings.append(
                {
                    "slide": number,
                    "effect": index,
                    "source_text": effect["text"],
                    "target": target["targets"],
                    "status": "fail" if reasons else "ooxml_match",
                    "reasons": reasons,
                }
            )
            previous_start, previous_duration = expected_delay, effect["duration"]
    return findings


def audit() -> dict:
    cases = {}
    for name, (html, pptx) in CASES.items():
        source_slides = source(html)
        pptx_slides = package(pptx)
        cases[name] = {
            "source": str(html.relative_to(ROOT)),
            "source_sha256": sha(html),
            "pptx": str(pptx.relative_to(ROOT)),
            "pptx_sha256": sha(pptx),
            "source_slides": source_slides,
            "pptx_slides": pptx_slides,
            "findings": compare(source_slides, pptx_slides),
        }
    return {
        "base_commit": "5279bd35a625d190895d9484057047ebe7e30cfe",
        "converter_sha256": sha(ROOT / "src/wps_ai_agent_cli/html_slides.py"),
        "layout_renderer_sha256": sha(ROOT / "src/wps_ai_agent_cli/html_layout_playwright.cjs"),
        "limitations": [
            "launch slide 5 inline span animation targets its containing paragraph in the PPTX",
            "hover animation and missing teaser.mp4 are outside this OOXML animation match",
            "OOXML match does not establish WPS playback",
        ],
        "cases": cases,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    output = json.dumps(audit(), ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
    else:
        print(output)
