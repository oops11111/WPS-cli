import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from lxml import etree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from paragraph_mark_font_mechanism import BASE, W, build, patch_xml


class ParagraphMarkFontTests(unittest.TestCase):
    def setUp(self):
        with ZipFile(BASE / "converted.docx") as archive:
            self.original = archive.read("word/document.xml")

    def test_exact_twelve_and_inverse(self):
        patched = patch_xml(self.original)
        old, new = ET.fromstring(self.original), ET.fromstring(patched)
        before = old.findall(".//" + W + "pPr/" + W + "rPr")
        after = new.findall(".//" + W + "pPr/" + W + "rPr")
        self.assertEqual(len(after) - len(before), 12)
        for row in new.find(W + "body").findall(W + "tbl")[1].findall(W + "tr")[2:]:
            for cell in row.findall(W + "tc"):
                props = cell.find(W + "p/" + W + "pPr")
                mark = props.find(W + "rPr")
                self.assertEqual(len(mark), 1)
                self.assertEqual(len(mark[0].attrib), 4)
                props.remove(mark)
        self.assertEqual(ET.tostring(new, encoding="UTF-8", xml_declaration=True, standalone=True), self.original)

    def test_reject_existing_mark(self):
        with self.assertRaises(ValueError):
            patch_xml(patch_xml(self.original))

    def test_deterministic_package(self):
        with tempfile.TemporaryDirectory() as folder:
            a, b = Path(folder) / "a.docx", Path(folder) / "b.docx"
            build(BASE / "converted.docx", a)
            build(BASE / "converted.docx", b)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            with ZipFile(a) as candidate, ZipFile(BASE / "converted.docx") as baseline:
                for name in baseline.namelist():
                    if name != "word/document.xml":
                        self.assertEqual(candidate.read(name), baseline.read(name))

    def test_reject_visible_font_or_topology_change(self):
        for tag in ("font", "merge"):
            root = ET.fromstring(self.original)
            cell = root.find(W + "body").findall(W + "tbl")[1].findall(W + "tr")[2].find(W + "tc")
            if tag == "font":
                cell.find(W + "p/" + W + "r/" + W + "rPr/" + W + "sz").set(W + "val", "24")
            else:
                ET.SubElement(cell.find(W + "tcPr"), W + "vMerge")
            with self.assertRaises(ValueError):
                patch_xml(ET.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True))


if __name__ == "__main__":
    unittest.main()
