"""Two-attribute fixed candidate package hard gate."""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

SPEC = importlib.util.spec_from_file_location(
    "mergedwidth", Path(__file__).resolve().parents[1] / "scripts/merged_continuation_width_mechanism.py"
)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class MergedWidthTests(unittest.TestCase):
    def test_exact_xml_inverse(self):
        with ZipFile(m.BASE / "converted.docx") as z:
            source = z.read("word/document.xml")
        changed, records = m.patch_xml(source)
        self.assertEqual(
            records, [{"column": 0, "before": 2633, "after": 710}, {"column": 3, "before": 2633, "after": 2729}]
        )
        self.assertNotEqual(source, changed)
        with self.assertRaises(ValueError):
            m.patch_xml(changed)

    def test_deterministic_other_parts_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d) / "a.docx", Path(d) / "b.docx"
            m.build(m.BASE / "converted.docx", a)
            m.build(m.BASE / "converted.docx", b)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            with ZipFile(a) as got, ZipFile(m.BASE / "converted.docx") as before:
                self.assertEqual(got.namelist(), before.namelist())
                for n in got.namelist():
                    if n != "word/document.xml":
                        self.assertEqual(got.read(n), before.read(n))


if __name__ == "__main__":
    unittest.main()
