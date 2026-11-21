import importlib.util
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

SPEC = importlib.util.spec_from_file_location(
    "paddingexperiment", Path(__file__).resolve().parents[1] / "scripts/padding_distribution_mechanism.py"
)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class PaddingDistributionTests(unittest.TestCase):
    def test_prediction_and_stop_gates(self):
        r = {
            "shifts": [-0.35] * 3,
            "old_errors": [0.78] * 3,
            "new_errors": [0.43] * 3,
            "roi_ssim": [0.5516460049, 0.56],
            "layout": {"score": 0.865},
            "gates": {"conserved": True},
            "pixels_identical": False,
        }
        self.assertEqual(m.classify(r), "POSITIVE")
        r["shifts"] = [-0.2] * 3
        self.assertEqual(m.classify(r), "STOP")
        r["shifts"] = [-0.35] * 3
        r["gates"]["conserved"] = False
        self.assertEqual(m.classify(r), "STOP")

    def test_exact_twenty_four_attributes_inverse(self):
        from lxml import etree as ET

        with ZipFile(m.BASE / "converted.docx") as z:
            source = z.read("word/document.xml")
        root = ET.fromstring(m.patch_xml(source))
        count = 0
        for row in root.find(m.W + "body").findall(m.W + "tbl")[1].findall(m.W + "tr")[2:]:
            for cell in row.findall(m.W + "tc"):
                spacing = cell.find(m.W + "p/" + m.W + "pPr/" + m.W + "spacing")
                self.assertEqual([spacing.get(m.W + k) for k in ("before", "after")], ["53", "52"])
                self.assertEqual(sum(int(spacing.get(m.W + k)) for k in ("before", "after")), 105)
                spacing.set(m.W + "before", "60")
                spacing.set(m.W + "after", "45")
                count += 2
        self.assertEqual(count, 24)
        self.assertEqual(ET.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True), source)
        with self.assertRaises(ValueError):
            m.patch_xml(m.patch_xml(source))

    def test_deterministic_package(self):
        with tempfile.TemporaryDirectory() as folder:
            a, b = Path(folder) / "a.docx", Path(folder) / "b.docx"
            m.build(m.BASE / "converted.docx", a)
            m.build(m.BASE / "converted.docx", b)
            self.assertEqual(a.read_bytes(), b.read_bytes())

    def test_reject_extra_spacing_or_wrong_alignment(self):
        from lxml import etree as ET

        with ZipFile(m.BASE / "converted.docx") as z:
            source = z.read("word/document.xml")
        for mode in ("spacing", "alignment"):
            root = ET.fromstring(source)
            cell = root.find(m.W + "body").findall(m.W + "tbl")[1].findall(m.W + "tr")[2].find(m.W + "tc")
            if mode == "spacing":
                cell.find(m.W + "p/" + m.W + "pPr/" + m.W + "spacing").set(m.W + "beforeLines", "1")
            else:
                cell.find(m.W + "tcPr/" + m.W + "vAlign").set(m.W + "val", "top")
            with self.assertRaises(ValueError):
                m.patch_xml(ET.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True))


if __name__ == "__main__":
    unittest.main()
