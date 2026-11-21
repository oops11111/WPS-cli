import importlib.util
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

SPEC = importlib.util.spec_from_file_location(
    "contractrows", Path(__file__).resolve().parents[1] / "scripts/contract_row_minimum_mechanism.py"
)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class ContractRowMinimumTests(unittest.TestCase):
    def test_declared_row_prediction_rejects_zero_or_anchor_shift(self):
        good = {"y": [347.81 + i * 23.25 for i in range(6)], "height": 116.25}
        self.assertTrue(all(m.row_prediction(good).values()))
        self.assertFalse(all(m.row_prediction({"y": [347.81 + i * 24 for i in range(6)], "height": 120}).values()))
        self.assertFalse(all(m.row_prediction({"y": [v + 0.12 for v in good["y"]], "height": 116.25}).values()))

    def setUp(self):
        with ZipFile(m.BASE / "candidate.docx") as z:
            self.source = z.read("word/document.xml")

    def test_exact_five_values_and_inverse(self):
        from lxml import etree as ET

        old, new = ET.fromstring(self.source), ET.fromstring(m.patch_xml(self.source))
        count = 0
        for a, b in zip(old.iter(), new.iter(), strict=True):
            self.assertEqual(a.tag, b.tag)
            self.assertEqual(a.text, b.text)
            if a.attrib != b.attrib:
                self.assertEqual(a.tag, m.W + "trHeight")
                self.assertEqual(a.get(m.W + "val"), "465")
                self.assertEqual(b.get(m.W + "val"), "450")
                self.assertEqual(b.get(m.W + "hRule"), "atLeast")
                b.attrib.update(a.attrib)
                count += 1
        self.assertEqual(count, 5)
        self.assertEqual(m.serialize(new), self.source)
        with self.assertRaises(ValueError):
            m.patch_xml(m.patch_xml(self.source))

    def test_no_other_package_changes_and_determinism(self):
        with tempfile.TemporaryDirectory() as folder:
            a, b = Path(folder) / "a.docx", Path(folder) / "b.docx"
            m.build(a)
            m.build(b)
            self.assertEqual(a.read_bytes(), b.read_bytes())

    def test_reject_wrong_rule_or_content_minimum(self):
        from lxml import etree as ET

        for kind in ("rule", "line"):
            root = ET.fromstring(self.source)
            table = root.find(m.W + "body").findall(m.W + "tbl")[1]
            if kind == "rule":
                table.find(".//" + m.W + "trHeight").set(m.W + "hRule", "exact")
            else:
                table.find(".//" + m.W + "spacing").set(m.W + "line", "331")
            with self.assertRaises(ValueError):
                m.patch_xml(m.serialize(root))


if __name__ == "__main__":
    unittest.main()
