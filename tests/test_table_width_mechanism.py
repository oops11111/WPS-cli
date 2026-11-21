"""Fixed width experiment package invariants."""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

SPEC = importlib.util.spec_from_file_location(
    "widths", Path(__file__).resolve().parents[1] / "scripts/table_width_mechanism.py"
)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class WidthMechanismTests(unittest.TestCase):
    def test_only_widths_differ(self):
        for family, source in m.SOURCES.items():
            with ZipFile(source) as package:
                xml = package.read("word/document.xml")
                variants = [m.variant_xml(xml, family + n) for n in ("0", "05", "1")]
            self.assertEqual(len({m.without_widths(v) for v in variants}), 1)
            for v in variants:
                root = m.ET.fromstring(v)
                cols = root.findall(".//" + m.W + "gridCol")
                self.assertEqual(len(cols), 3 if family == "M" else 4)
            widths = [
                [int(c.get(m.W + "w")) for c in m.ET.fromstring(v).findall(".//" + m.W + "gridCol")] for v in variants
            ]
            self.assertTrue(all(c - a == 15 and b - a in (7, 8) for a, b, c in zip(*widths, strict=True)))

    def test_deterministic_package_and_non_document_parts(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in m.VARIANTS:
                a, b = Path(tmp) / "a.docx", Path(tmp) / "b.docx"
                m.build(m.SOURCES[name[0]], a, name)
                m.build(m.SOURCES[name[0]], b, name)
                self.assertEqual(a.read_bytes(), b.read_bytes())
                with ZipFile(a) as got, ZipFile(m.SOURCES[name[0]]) as source:
                    for part in source.namelist():
                        if part != "word/document.xml":
                            self.assertEqual(got.read(part), source.read(part))


if __name__ == "__main__":
    unittest.main()
