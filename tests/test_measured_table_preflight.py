import importlib.util
import unittest
from pathlib import Path
from zipfile import ZipFile

SPEC = importlib.util.spec_from_file_location(
    "tablepreflight", Path(__file__).resolve().parents[1] / "scripts/measured_table_width_preflight.py"
)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class TablePreflightTests(unittest.TestCase):
    def test_exact_three_table_allowlists(self):
        from lxml import etree as ET

        for case, count in (("A-contract-docx", 21), ("A-manual-docx", 15), ("A-pdfsource-docx", 35)):
            with ZipFile(m.BASE / case / "converted.docx") as z:
                original = z.read("word/document.xml")
            root = ET.fromstring(original)
            t = root.find(m.W + "body").findall(m.W + "tbl")[m.EXPECTED[case][0]]
            nodes = list(t.find(m.W + "tblGrid"))
            for cell in t.findall(".//" + m.W + "tc"):
                merge = cell.find(m.W + "tcPr/" + m.W + "vMerge")
                if merge is None or merge.get(m.W + "val") == "restart":
                    nodes.append(cell.find(m.W + "tcPr/" + m.W + "tcW"))
            for n in nodes:
                n.set(m.W + "w", str(int(n.get(m.W + "w")) - 15))
            changed = ET.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True)
            self.assertEqual(m.inverse(original, changed, case), count)
            root.find(".//" + m.W + "pgMar").set(m.W + "left", "1")
            with self.assertRaises(ValueError):
                m.inverse(original, ET.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True), case)

    def test_geometry_duplicates_and_ambiguity(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock, patch

        import pdfplumber

        spec = importlib.util.spec_from_file_location(
            "geom", Path(__file__).resolve().parents[1] / "scripts/measured_table_geometry.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        lines = [dict(x0=x, x1=x, top=9.64, bottom=58.36, linewidth=0.72) for x in (10, 40, 70)]
        lines += [dict(x0=9.64, x1=70.36, top=y, bottom=y, linewidth=0.72) for y in (10, 34, 58)]
        chars = [
            dict(
                text="85",
                x0=x,
                x1=x + 8,
                top=y,
                bottom=y + 10,
                fontname="A+YaHei",
                size=10,
                matrix=(1, 0, 0, 1, x, 100 - y),
            )
            for y in (15, 39)
            for x in (15, 45)
        ]
        doc = MagicMock()
        doc.__enter__.return_value = SimpleNamespace(pages=[SimpleNamespace(lines=lines, chars=chars, height=100)])
        with patch.object(pdfplumber, "open", return_value=doc):
            result = module.geometry(Path("unused.pdf"), 2, 2)
            self.assertEqual([c["text"] for c in result["cells"]], ["85"] * 4)
            chars[0].update(x0=36, x1=44)
            with self.assertRaises(ValueError):
                module.geometry(Path("unused.pdf"), 2, 2)


if __name__ == "__main__":
    unittest.main()
