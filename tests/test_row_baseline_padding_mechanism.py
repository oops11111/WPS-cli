import importlib.util
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

SPEC = importlib.util.spec_from_file_location(
    "rowpaddingexperiment", Path(__file__).resolve().parents[1] / "scripts/row_baseline_padding_mechanism.py"
)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class RowBaselinePaddingTests(unittest.TestCase):
    def test_exact_inverse_and_fixed_total(self):
        from lxml import etree as ET

        w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        with ZipFile(m.BASE / "candidate.docx") as z:
            source = z.read("word/document.xml")
        root = ET.fromstring(m.patch_xml(source))
        rows = root.find(w + "body").findall(w + "tbl")[1].findall(w + "tr")
        self.assertTrue(all(r.find(w + "trPr/" + w + "trHeight").get(w + "val") == "450" for r in rows))
        count = 0
        for row in rows[2:]:
            for cell in row.findall(w + "tc"):
                spacing = cell.find(w + "p/" + w + "pPr/" + w + "spacing")
                self.assertEqual([spacing.get(w + k) for k in ("before", "after")], ["53", "52"])
                self.assertEqual(sum(int(spacing.get(w + k)) for k in ("before", "after")), 105)
                spacing.set(w + "before", "60")
                spacing.set(w + "after", "45")
                count += 2
        self.assertEqual(count, 24)
        self.assertEqual(ET.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True), source)
        with self.assertRaises(ValueError):
            m.patch_xml(m.patch_xml(source))

    def test_deterministic_package_and_payloads(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory) / "a.docx", Path(directory) / "b.docx"
            m.build(a)
            m.build(b)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            with ZipFile(a) as new, ZipFile(m.BASE / "candidate.docx") as old:
                self.assertTrue(all(new.read(n) == old.read(n) for n in old.namelist() if n != "word/document.xml"))

    def test_wrong_spacing_alignment_rejected(self):
        from lxml import etree as ET

        w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        with ZipFile(m.BASE / "candidate.docx") as z:
            source = z.read("word/document.xml")
        for mode in ("spacing", "alignment"):
            root = ET.fromstring(source)
            cell = root.find(w + "body").findall(w + "tbl")[1].findall(w + "tr")[2].find(w + "tc")
            if mode == "spacing":
                cell.find(w + "p/" + w + "pPr/" + w + "spacing").set(w + "beforeLines", "1")
            else:
                cell.find(w + "tcPr/" + w + "vAlign").set(w + "val", "top")
            with self.assertRaises(ValueError):
                m.patch_xml(ET.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True))

    def test_old_failure_stays_stop_and_zero_is_distinct(self):
        scores = {k: [0.8, 0.81] for k in ("body", "header", "table", "later", "whole")}
        args = ([0.855, 0.765, 0.795], [0.505, 0.415, 0.445], scores, True)
        self.assertEqual(m.classify([-0.35] * 3, *args), "PASS_MECHANISM_ONLY")
        self.assertEqual(m.classify([-0.24] * 3, *args), "STOP")
        self.assertEqual(m.classify([0] * 3, *args, zero=True), "ZERO_INFLUENCE")
        self.assertEqual(m.classify([-0.35] * 3, *args[:-1], False), "STOP")

    def test_retry_is_rejected_before_probe(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / "export-manifest.json").write_text("{}", encoding="utf-8")
            with patch("html_docx_wps_matrix.probe_wps") as probe:
                with self.assertRaisesRegex(ValueError, "already attempted"):
                    m.export_once(out)
                probe.assert_not_called()

    def test_assessor_read_only_baseline_is_zero(self):
        result = m.assess(m.BASE / "wps.pdf")
        self.assertEqual(result["outcome"], "ZERO_INFLUENCE")
        self.assertTrue(all(result["gates"].values()))
        self.assertEqual(result["shifts"], [0, 0, 0])
