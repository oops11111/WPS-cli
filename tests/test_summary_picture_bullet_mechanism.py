"""Deterministic synthetic vector-numbering controls, without WPS in tests."""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

spec = importlib.util.spec_from_file_location(
    "picture_mechanism", Path(__file__).resolve().parents[1] / "scripts/summary_picture_bullet_mechanism.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
W = module.W
V = "{urn:schemas-microsoft-com:vml}"


class PictureMechanismTests(unittest.TestCase):
    def test_shape_gate_rejects_rectangle_and_wrong_orientation(self):
        base = {"x0": 0, "x1": 6.8, "top": 0, "bottom": 7.9, "fill": True, "stroke": False}
        self.assertTrue(module.right_triangle({**base, "pts": [(0, 0), (6.8, 3.95), (0, 7.9), (0, 0)]}))
        self.assertFalse(module.right_triangle({**base, "pts": [(0, 0), (6.8, 0), (6.8, 7.9), (0, 7.9)]}))
        self.assertFalse(module.right_triangle({**base, "pts": [(6.8, 0), (0, 3.95), (6.8, 7.9)]}))

    def test_deterministic_packages_and_unrelated_parts(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "base.docx"
            module.build(base, "C12")
            with ZipFile(base) as original:
                for name in module.VARIANTS:
                    with self.subTest(name=name):
                        a, b = Path(directory) / "a.docx", Path(directory) / "b.docx"
                        module.build(a, name)
                        module.build(b, name)
                        self.assertEqual(a.read_bytes(), b.read_bytes())
                        with ZipFile(a) as current:
                            self.assertEqual(current.namelist(), original.namelist())
                            for part in current.namelist():
                                if part not in {"word/document.xml", "word/numbering.xml"}:
                                    self.assertEqual(current.read(part), original.read(part), part)

    def test_text_hidden_and_exact_numbering_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in module.VARIANTS:
                with self.subTest(name=name):
                    path = Path(directory) / "input.docx"
                    module.build(path, name)
                    with ZipFile(path) as package:
                        doc = ET.fromstring(package.read("word/document.xml"))
                        nums = ET.fromstring(package.read("word/numbering.xml"))
                    self.assertEqual([t.text for t in doc.iter(W + "t")], list(module.TEXT))
                    self.assertEqual(len(list(doc.iter(W + "vanish"))), 1)
                    self.assertEqual(len(doc.find(W + "body").findall(W + "p")), 2)
                    self.assertFalse(list(doc.iter(W + "tab")))
                    pictures = list(nums.findall(W + "numPicBullet"))
                    if name.startswith("C"):
                        self.assertFalse(pictures)
                        self.assertFalse(list(doc.iter(W + "numPr")))
                        continue
                    self.assertEqual(len(pictures), 1)
                    shape = pictures[0].find(W + "pict/" + V + "shape")
                    self.assertEqual(shape.get("path"), "m 0,0 l 860,500 0,1000 x e")
                    self.assertEqual(shape.get("fillcolor"), "#000000")
                    self.assertEqual(shape.get("stroked"), "f")
                    size = int(name[1:])
                    p = module.prediction(size)
                    self.assertEqual(shape.get("style"), f"width:{p['square_pt']:g}pt;height:{p['square_pt']:g}pt")
                    abstract = nums.findall(W + "abstractNum")[-1]
                    level = abstract.find(W + "lvl")
                    self.assertEqual(
                        level.find(W + "lvlPicBulletId").get(W + "val"), pictures[0].get(W + "numPicBulletId")
                    )
                    self.assertEqual(level.find(W + "lvlText").get(W + "val"), "X")
                    self.assertEqual(level.find(W + "suff").get(W + "val"), "tab" if name[0] == "N" else "nothing")
                    advance = p["advance_twips"] if name[0] == "N" else 0
                    indent = level.find(W + "pPr/" + W + "ind")
                    self.assertEqual(indent.attrib, {W + "left": str(advance), W + "hanging": str(advance)})
                    for tag, attribute in (
                        ("num", "numId"),
                        ("abstractNum", "abstractNumId"),
                        ("numPicBullet", "numPicBulletId"),
                    ):
                        ids = [n.get(W + attribute) for n in nums.findall(W + tag)]
                        self.assertEqual(len(ids), len(set(ids)))

    def test_predictions_scale_without_offsets(self):
        self.assertEqual(module.prediction(12)["advance_twips"], 254)
        self.assertEqual(module.prediction(18)["advance_twips"], 382)
        self.assertAlmostEqual(module.prediction(18)["square_pt"] / module.prediction(12)["square_pt"], 1.5)

    def test_unknown_variant_rejected(self):
        with self.assertRaises(ValueError):
            module.build(Path("unused.docx"), "extra")
