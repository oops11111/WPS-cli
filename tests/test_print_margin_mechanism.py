"""Predeclared source/transform controls, before any browser evidence."""

import importlib.util
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "margins", Path(__file__).resolve().parents[1] / "scripts/print_margin_mechanism.py"
)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class PrintMarginTests(unittest.TestCase):
    def test_fixed_sources(self):
        self.assertEqual(len(m.REFERENCES), 4)
        for _, size, margin, explicit in m.REFERENCES:
            a = m.source_html(size, margin, explicit)
            self.assertEqual(a, m.source_html(size, margin, explicit))
            self.assertEqual(a.count("LINE-"), 45)
            self.assertEqual("@page" in a, explicit)
            self.assertIn("margin:8px", a)

    def test_transform_measurement_not_text_bounds(self):
        self.assertAlmostEqual(
            m.stream_origin(b".24 0 0 -.24 0 842 cm\n3.125 0 0 3.125 115.625 115.625 cm")["content_left"], 27.75
        )
        with self.assertRaises(ValueError):
            m.stream_origin(b"1 0 0 1 0 0 cm")

    def test_native_pairs_only_margin_and_deterministic(self):
        import tempfile
        from xml.etree import ElementTree as ET
        from zipfile import ZipFile

        w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        with tempfile.TemporaryDirectory() as tmp:
            for _, size, margin, _ in m.REFERENCES:
                a, b, c = Path(tmp) / "a.docx", Path(tmp) / "b.docx", Path(tmp) / "c.docx"
                m.build_docx(a, size, margin, False)
                m.build_docx(b, size, margin, True)
                m.build_docx(c, size, margin, False)
                self.assertEqual(a.read_bytes(), c.read_bytes())
                with ZipFile(a) as x, ZipFile(b) as y:
                    self.assertEqual(x.namelist(), y.namelist())
                    for name in x.namelist():
                        if name != "word/document.xml":
                            self.assertEqual(x.read(name), y.read(name))
                    rx, ry = ET.fromstring(x.read("word/document.xml")), ET.fromstring(y.read("word/document.xml"))
                    for r in (rx, ry):
                        e = r.find(".//" + w + "pgMar")
                        for side in ("left", "right", "top", "bottom"):
                            e.set(w + side, "MARGIN")
                    self.assertEqual(ET.tostring(rx), ET.tostring(ry))


if __name__ == "__main__":
    unittest.main()
