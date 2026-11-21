"""Synthetic inline marker package controls; never starts WPS."""

import importlib.util
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

spec = importlib.util.spec_from_file_location(
    "inline_marker", Path(__file__).resolve().parents[1] / "scripts/inline_summary_marker_mechanism.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
}


class InlineMarkerTests(unittest.TestCase):
    def test_positive_geometry_and_advance_y_counterexamples(self):
        cases = {}
        for name in module.VARIANTS:
            size = int(name[1:])
            mode = name[0]
            advance = 0 if mode == "C" else (0.66 if mode == "I" else 1.06) * size
            height, width = 0.66 * size, 0.5676 * size
            vector = {
                "x0": 72,
                "x1": 72 + width,
                "top": 90 - height,
                "bottom": 90,
                "fill": True,
                "stroke": False,
                "pts": [(72, 90 - height), (72 + width, 90 - height / 2), (72, 90)],
            }
            cases[name] = {
                "retained": list(module.TEXT),
                "hidden_xml": True,
                "pdf": {
                    "pages": 1,
                    "vectors": [] if mode == "C" else [vector],
                    "summary_baseline": 90,
                    "words": [
                        {"text": "SUMMARY", "x0": 72 + advance, "top": 78},
                        {"text": "FOLLOWING", "x0": 72, "top": 96},
                    ],
                },
            }
        self.assertTrue(module.gates(cases)["passed"])
        wrong = deepcopy(cases)
        wrong["G12"]["pdf"]["words"][0]["x0"] += 0.2
        self.assertFalse(module.gates(wrong)["required"]["G12"]["advance"])
        wrong = deepcopy(cases)
        wrong["I18"]["pdf"]["words"][1]["top"] += 0.1
        self.assertFalse(module.gates(wrong)["required"]["I18"]["y"])
        wrong = deepcopy(cases)
        wrong["G18"]["pdf"]["vectors"][0]["pts"] = [(72, 90), (80, 90)]
        self.assertFalse(module.gates(wrong)["required"]["G18"]["triangle"])

    def test_deterministic_packages_only_document_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "base.docx"
            module.build(base, "C12")
            with ZipFile(base) as original:
                for name in module.VARIANTS:
                    a, b = Path(directory) / "a.docx", Path(directory) / "b.docx"
                    module.build(a, name)
                    module.build(b, name)
                    self.assertEqual(a.read_bytes(), b.read_bytes(), name)
                    with ZipFile(a) as current:
                        self.assertEqual(current.namelist(), original.namelist())
                        for part in current.namelist():
                            if part != "word/document.xml":
                                self.assertEqual(current.read(part), original.read(part), part)

    def test_exact_xml_text_and_geometry(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in module.VARIANTS:
                with self.subTest(name=name):
                    path = Path(directory) / "input.docx"
                    module.build(path, name)
                    with ZipFile(path) as package:
                        root = ET.fromstring(package.read("word/document.xml"))
                    self.assertEqual([t.text for t in root.findall(".//w:t", NS)], list(module.TEXT))
                    self.assertEqual(len(root.findall(".//w:vanish", NS)), 1)
                    self.assertFalse(root.findall(".//w:numPr", NS))
                    self.assertFalse(root.findall(".//w:tab", NS))
                    self.assertFalse(root.findall(".//mc:Fallback", NS))
                    drawings = root.findall(".//wp:inline", NS)
                    self.assertEqual(len(drawings), 0 if name[0] == "C" else 1)
                    if not drawings:
                        continue
                    size = int(name[1:])
                    inline = drawings[0]
                    extent = inline.find("wp:extent", NS)
                    self.assertEqual(int(extent.get("cx")), round((0.66 if name[0] == "I" else 1.06) * size * 12700))
                    self.assertEqual(int(extent.get("cy")), round(0.66 * size * 12700))
                    self.assertEqual(root.find(".//mc:Choice", NS).get("Requires"), "wps")
                    geom = root.find(".//a:path", NS)
                    self.assertEqual(geom.get("w"), "6600" if name[0] == "I" else "10600")
                    self.assertEqual(geom.get("h"), "6600")
                    self.assertEqual(
                        [(p.get("x"), p.get("y")) for p in geom.findall(".//a:pt", NS)],
                        [("0", "0"), ("5676", "3300"), ("0", "6600")],
                    )
                    self.assertEqual(inline.find("wp:effectExtent", NS).attrib, dict(l="0", t="0", r="0", b="0"))
                    self.assertEqual(root.find(".//a:off", NS).attrib, dict(x="0", y="0"))

    def test_missing_shape_and_body_leak_fail_gates(self):
        cases = {
            name: {
                "retained": list(module.TEXT),
                "hidden_xml": True,
                "pdf": {
                    "pages": 1,
                    "vectors": [],
                    "summary_baseline": 90,
                    "words": [{"text": "SUMMARY", "x0": 72, "top": 78}, {"text": "FOLLOWING", "x0": 72, "top": 96}],
                },
            }
            for name in module.VARIANTS
        }
        self.assertFalse(module.gates(cases)["passed"])
        cases["G12"]["pdf"]["words"].append({"text": "RETAINED-BODY", "x0": 72, "top": 110})
        self.assertFalse(module.gates(cases)["common"]["G12"]["visible"])
