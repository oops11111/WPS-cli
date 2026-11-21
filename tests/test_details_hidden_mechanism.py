"""Offline package controls for the fixed retained-text WPS experiment."""

import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

spec = importlib.util.spec_from_file_location(
    "details_mechanism", Path(__file__).resolve().parents[1] / "scripts/details_hidden_mechanism.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class HiddenMechanismTests(unittest.TestCase):
    def test_packages_deterministic_only_document_differs(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "V.docx"
            module.build(base, "V")
            with ZipFile(base) as reference:
                for name in module.VARIANTS:
                    first, second = Path(directory) / f"{name}1.docx", Path(directory) / f"{name}2.docx"
                    module.build(first, name)
                    module.build(second, name)
                    self.assertEqual(first.read_bytes(), second.read_bytes(), name)
                    with ZipFile(first) as package:
                        self.assertEqual(package.namelist(), reference.namelist())
                        for part in package.namelist():
                            if part != "word/document.xml":
                                self.assertEqual(package.read(part), reference.read(part), part)

    def test_exact_xml_controls_and_page_properties(self):
        with tempfile.TemporaryDirectory() as directory:
            roots = {}
            for name in module.VARIANTS:
                path = Path(directory) / f"{name}.docx"
                module.build(path, name)
                with ZipFile(path) as package:
                    roots[name] = ET.fromstring(package.read("word/document.xml"))
            for name, root in roots.items():
                paragraphs = root.find(W + "body").findall(W + "p")
                self.assertEqual(len(paragraphs), 2 if name in {"H", "C"} else 3)
                texts = [t.text for t in root.iter(W + "t")]
                self.assertEqual(texts, ["SUMMARY", "FOLLOWING"] if name == "C" else list(module.SENTINELS))
                self.assertEqual(len(list(root.iter(W + "vanish"))), {"V": 0, "H": 1, "P": 2, "C": 0}[name])
                for spacing in root.iter(W + "spacing"):
                    self.assertEqual(
                        spacing.attrib,
                        {W + "before": "0", W + "after": "0", W + "line": "360", W + "lineRule": "exact"},
                    )
                for size in root.iter(W + "sz"):
                    self.assertEqual(size.get(W + "val"), "24")
                margins = root.find(".//" + W + "pgMar")
                for side in ("top", "bottom", "left", "right"):
                    self.assertEqual(margins.get(W + side), "1440")
                body = root.find(W + "body")
                if name == "H":
                    body[0].remove(body[0].findall(W + "r")[1])
                    body.insert(1, copy.deepcopy(roots["V"].find(W + "body")[1]))
                elif name == "P":
                    props = body[1].find(W + "pPr")
                    props.remove(props.find(W + "rPr"))
                    props = body[1].find(W + "r/" + W + "rPr")
                    props.remove(props.find(W + "vanish"))
                elif name == "C":
                    body.insert(1, copy.deepcopy(roots["V"].find(W + "body")[1]))
                self.assertEqual(ET.tostring(root), ET.tostring(roots["V"]), name)

    def test_gate_requires_H_not_P_layout(self):
        def case(words):
            return {
                "retained": list(module.SENTINELS),
                "pdf": {"pages": 1, "words": [{"text": text, "top": top} for text, top in words]},
            }

        cases = {
            "V": case([("SUMMARY", 72), ("RETAINED-BODY", 90), ("FOLLOWING", 108)]),
            "H": case([("SUMMARY", 72), ("FOLLOWING", 90)]),
            "P": case([("SUMMARY", 72), ("FOLLOWING", 108)]),
            "C": case([("SUMMARY", 72), ("FOLLOWING", 90)]),
        }
        self.assertTrue(module.gates(cases)["passed"])
        self.assertEqual(module.gates(cases)["P_diagnostic"]["following_delta_pt"], 18)
        cases["H"]["pdf"]["words"][-1]["top"] = 90.1
        self.assertFalse(module.gates(cases)["passed"])
