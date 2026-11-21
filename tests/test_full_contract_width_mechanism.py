import importlib.util
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

SPEC = importlib.util.spec_from_file_location(
    "fullwidth", Path(__file__).resolve().parents[1] / "scripts/full_contract_width_mechanism.py"
)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class FullContractWidthTests(unittest.TestCase):
    def test_score_stop_predicates(self):
        scores = {"body": [0.54, 0.55], "table": [0.63, 0.64], "header": [0.81, 0.81], "whole": [0.864361, 0.865]}
        self.assertTrue(all(m.score_gates(scores).values()))
        scores["whole"][1] = 0.86441
        self.assertFalse(m.score_gates(scores)["whole"])
        scores["header"][1] = 0.809
        self.assertFalse(m.score_gates(scores)["roi_header"])
        scores["table"][1] = 0.63
        self.assertFalse(m.score_gates(scores)["roi_body_table"])

    def setUp(self):
        with ZipFile(m.BASE / "converted.docx") as z:
            self.source = z.read("word/document.xml")

    def test_exact_inverse_and_copied_table(self):
        from lxml import etree as ET

        old, new = ET.fromstring(self.source), ET.fromstring(m.patch_xml(self.source))
        count = 0
        for a, b in zip(old.iter(), new.iter(), strict=True):
            self.assertEqual(a.tag, b.tag)
            self.assertEqual(a.text, b.text)
            if a.attrib != b.attrib:
                self.assertEqual(a.get(m.W + "w"), str(int(b.get(m.W + "w")) + 15))
                b.attrib.update(a.attrib)
                count += 1
        self.assertEqual(count, 21)
        self.assertEqual(m.serialize(new), self.source)

    def test_determinism_and_parts(self):
        with tempfile.TemporaryDirectory() as folder:
            a, b = Path(folder) / "a.docx", Path(folder) / "b.docx"
            m.build(a)
            m.build(b)
            self.assertEqual(a.read_bytes(), b.read_bytes())

    def test_changed_topology_or_font_rejected(self):
        from lxml import etree as ET

        for change in ("span", "font"):
            root = ET.fromstring(self.source)
            table = root.find(m.W + "body").findall(m.W + "tbl")[1]
            if change == "span":
                table.find(".//" + m.W + "gridSpan").set(m.W + "val", "3")
            else:
                table.find(".//" + m.W + "rFonts").set(m.W + "ascii", "Arial")
            with self.assertRaises(ValueError):
                m.patch_xml(m.serialize(root))


if __name__ == "__main__":
    unittest.main()
