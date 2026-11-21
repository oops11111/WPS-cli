"""Control the synthetic experiment's package and XML scope offline."""

import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

spec = importlib.util.spec_from_file_location(
    "mechanism", Path(__file__).resolve().parents[1] / "scripts/manual_row_mechanism.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
W = module.W


class MechanismTests(unittest.TestCase):
    def test_only_declared_xml_changes(self):
        with ZipFile(module.SOURCE) as original:
            source = original.read("word/document.xml")
        baseline = ET.fromstring(module.variant_xml(source, "B"))
        for name in module.VARIANTS:
            root = ET.fromstring(module.variant_xml(source, name))
            for height in root.iter(W + "trHeight"):
                height.set(W + "val", "390")
                height.set(W + "hRule", "atLeast")
            for cell, old in zip(root.iter(W + "tc"), baseline.iter(W + "tc"), strict=True):
                if name in {"L", "LR"}:
                    cell[:] = copy.deepcopy(list(old))
                elif name in {"N", "NR"}:
                    props = cell.find(W + "tcPr")
                    props.remove(props.find(W + "tcBorders"))
                    old_border = copy.deepcopy(old.find(W + "tcPr/" + W + "tcBorders"))
                    props.insert(1, old_border)
            if name in {"N", "NR"}:
                props = root.find(W + "body/" + W + "tbl/" + W + "tblPr")
                old = baseline.find(W + "body/" + W + "tbl/" + W + "tblPr/" + W + "tblBorders")
                border = props.find(W + "tblBorders")
                index = list(props).index(border)
                props.remove(border)
                if old is not None:
                    props.insert(index, copy.deepcopy(old))
            self.assertEqual(ET.tostring(root), ET.tostring(baseline), name)

    def test_all_variants_deterministic_and_other_parts_identical(self):
        with tempfile.TemporaryDirectory() as directory, ZipFile(module.SOURCE) as original:
            for name in module.VARIANTS:
                with self.subTest(name=name):
                    a, b = Path(directory) / "a.docx", Path(directory) / "b.docx"
                    module.build(module.SOURCE, a, name)
                    module.build(module.SOURCE, b, name)
                    self.assertEqual(a.read_bytes(), b.read_bytes())
                    with ZipFile(a) as generated:
                        self.assertEqual(sorted(original.namelist()), sorted(generated.namelist()))
                        for part in original.namelist():
                            if part != "word/document.xml":
                                self.assertEqual(original.read(part), generated.read(part))

    def test_declared_controls(self):
        with ZipFile(module.SOURCE) as original:
            source = original.read("word/document.xml")
        original_table = ET.fromstring(source).find(W + "body/" + W + "tbl")
        for name in module.VARIANTS:
            with self.subTest(name=name):
                body = ET.fromstring(module.variant_xml(source, name)).find(W + "body")
                self.assertEqual([c.tag for c in body], [W + "tbl", W + "sectPr"])
                table = body[0]
                self.assertEqual(len(table.findall(W + "tr")), 4)
                self.assertEqual(len(list(table.iter(W + "tc"))), 12)
                for height in table.iter(W + "trHeight"):
                    self.assertEqual(height.get(W + "val"), "375" if name in {"R", "LR", "NR"} else "390")
                    self.assertEqual(height.get(W + "hRule"), "exact" if name == "E" else "atLeast")
                if name in {"L", "LR"}:
                    self.assertEqual([t.text for t in table.iter(W + "t")], ["X"] * 12)
                else:
                    self.assertEqual(
                        [t.text for t in table.iter(W + "t")], [t.text for t in original_table.iter(W + "t")]
                    )
                if name in {"N", "NR"}:
                    self.assertTrue(
                        all(
                            b.get(W + "val") == "nil"
                            for p in table.iter()
                            if p.tag in {W + "tcBorders", W + "tblBorders"}
                            for b in p
                        )
                    )

    def test_no_undeclared_variant(self):
        with self.assertRaises(ValueError):
            module.variant_xml(b"", "extra")
