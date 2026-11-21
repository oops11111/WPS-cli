"""Fixed image indentation mechanism invariants."""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

SPEC = importlib.util.spec_from_file_location(
    "indents", Path(__file__).resolve().parents[1] / "scripts/image_indent_mechanism.py"
)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class ImageIndentTests(unittest.TestCase):
    def test_only_indent_differs(self):
        with ZipFile(m.SOURCE) as p:
            source = p.read("word/document.xml")
        variants = [m.variant_xml(source, n) for n in m.VARIANTS]
        self.assertEqual(len({m.without_indent(v) for v in variants}), 1)
        for n, v in zip(m.VARIANTS, variants, strict=True):
            root = m.ET.fromstring(v)
            ind = root.find(".//" + m.W + "ind")
            if n.startswith("N"):
                self.assertEqual(ind.get(m.W + "left"), str(int(n[1:]) * 15))
            else:
                self.assertIsNone(ind)
            self.assertEqual(["BEFORE", "FOLLOWING"], [e.text for e in root.iter(m.W + "t")])

    def test_deterministic_unchanged_other_parts(self):
        with tempfile.TemporaryDirectory() as tmp:
            for n in m.VARIANTS:
                a, b = Path(tmp) / "a.docx", Path(tmp) / "b.docx"
                m.build(m.SOURCE, a, n)
                m.build(m.SOURCE, b, n)
                self.assertEqual(a.read_bytes(), b.read_bytes())
                with ZipFile(a) as got, ZipFile(m.SOURCE) as source:
                    for part in source.namelist():
                        if part != "word/document.xml":
                            self.assertEqual(got.read(part), source.read(part))

    def test_gate_rejects_position_size_page_changes(self):
        b = {
            "pages": 1,
            "image": {"top": 100, "width": 240, "height": 120},
            "before": {"top": 30},
            "following": {"top": 250},
            "relative_x": 0,
        }
        self.assertTrue(all(m.gates(b, b, "C0").values()))
        for changed in ({**b, "relative_x": 1}, {**b, "pages": 2}, {**b, "image": {**b["image"], "height": 121}}):
            self.assertFalse(all(m.gates(changed, b, "C0").values()))


if __name__ == "__main__":
    unittest.main()
