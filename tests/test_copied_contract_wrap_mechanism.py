import importlib.util
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

SPEC = importlib.util.spec_from_file_location(
    "copiedwrap", Path(__file__).resolve().parents[1] / "scripts/copied_contract_wrap_mechanism.py"
)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class CopiedWrapTests(unittest.TestCase):
    def test_reject_changed_font_and_topology(self):
        from lxml import etree as ET

        with ZipFile(m.BASE / "converted.docx") as z:
            original = z.read("word/document.xml")
        root = ET.fromstring(original)
        table = root.find(m.W + "body").findall(m.W + "tbl")[1]
        table.find(".//" + m.W + "rFonts").set(m.W + "ascii", "Arial")
        with self.assertRaises(ValueError):
            m.control_xml(m.serialize(root))
        root = ET.fromstring(m.control_xml(original))
        root.find(".//" + m.W + "gridSpan").set(m.W + "val", "3")
        with self.assertRaises(ValueError):
            m.patch_xml(m.serialize(root))

    def test_table_identity_and_exact_width_inverse(self):
        from lxml import etree as ET

        with ZipFile(m.BASE / "converted.docx") as z:
            original = z.read("word/document.xml")
        control = m.control_xml(original)
        old, new = ET.fromstring(original), ET.fromstring(control)
        self.assertEqual(
            ET.tostring(old.find(m.W + "body").findall(m.W + "tbl")[1]),
            ET.tostring(new.find(m.W + "body").find(m.W + "tbl")),
        )
        patched = ET.fromstring(m.patch_xml(control))
        count = 0
        for a, b in zip(new.iter(), patched.iter(), strict=True):
            self.assertEqual(a.tag, b.tag)
            self.assertEqual(a.text, b.text)
            if a.attrib != b.attrib:
                self.assertEqual(a.get(m.W + "w"), str(int(b.get(m.W + "w")) + 15))
                b.attrib.update(a.attrib)
                count += 1
        self.assertEqual(count, 21)
        self.assertEqual(m.serialize(patched), control)
        with self.assertRaises(ValueError):
            m.patch_xml(m.patch_xml(control))

    def test_package_determinism(self):
        with tempfile.TemporaryDirectory() as folder:
            for zero in (False, True):
                a, b = Path(folder) / "a.docx", Path(folder) / "b.docx"
                m.build(a, zero)
                m.build(b, zero)
                self.assertEqual(a.read_bytes(), b.read_bytes())

    def test_control_mismatch_stops(self):
        a = {
            "pitches": [24] * 5,
            "cells": [{"text": "金额（元）", "fonts": [["MicrosoftYaHei-Bold", 11.05]], "baselines": [33]}],
        }
        self.assertTrue(m.baseline_gate(a, a))
        b = {
            "pitches": [24] * 5,
            "cells": [{"text": "金额（元）", "fonts": [["MicrosoftYaHei-Bold", 11.05]], "baselines": [33, 49]}],
        }
        self.assertFalse(m.baseline_gate(a, b))


if __name__ == "__main__":
    unittest.main()
