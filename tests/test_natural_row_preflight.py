import importlib.util
import unittest
from pathlib import Path
from zipfile import ZipFile

SPEC = importlib.util.spec_from_file_location(
    "rowpreflight", Path(__file__).resolve().parents[1] / "scripts/natural_row_preflight.py"
)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class NaturalRowPackageTests(unittest.TestCase):
    def test_exact_current_contract_inverse_and_other_cases(self):
        from lxml import etree as ET

        for case, _ in m.CASES:
            with ZipFile(m.BASE / case / "candidate.docx") as z:
                before = z.read("word/document.xml")
            after = before
            if case == "A-contract-docx":
                root = ET.fromstring(before)
                for h in (
                    root.find(m.W + "body")
                    .findall(m.W + "tbl")[1]
                    .findall(m.W + "tr/" + m.W + "trPr/" + m.W + "trHeight")
                ):
                    h.set(m.W + "val", "450")
                after = ET.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True)
            self.assertEqual(m.inverse(before, after, case), 5 if case == "A-contract-docx" else 0)
            root = ET.fromstring(after)
            root.find(".//" + m.W + "pgMar").set(m.W + "left", "1")
            with self.assertRaises(ValueError):
                m.inverse(before, ET.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True), case)


if __name__ == "__main__":
    unittest.main()
