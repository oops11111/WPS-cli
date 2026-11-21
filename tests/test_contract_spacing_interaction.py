import importlib.util
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

SPEC = importlib.util.spec_from_file_location(
    "spacinginteraction", Path(__file__).resolve().parents[1] / "scripts/contract_spacing_interaction.py"
)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class ContractSpacingInteractionTests(unittest.TestCase):
    def test_two_attributes_and_inverse(self):
        from lxml import etree as ET

        w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        with ZipFile(m.BASE / "candidate.docx") as z:
            source = z.read("word/document.xml")
        root = ET.fromstring(m.patch_xml(source))
        count = 0
        for p in root.find(w + "body").findall(w + "p"):
            if "".join(p.itertext()) in ("第三条 保密", "第四条 违约责任"):
                spacing = p.find(w + "pPr/" + w + "spacing")
                self.assertEqual(spacing.get(w + "before"), "274")
                spacing.set(w + "before", "54")
                count += 1
        self.assertEqual(count, 2)
        self.assertEqual(ET.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True), source)
        with self.assertRaises(ValueError):
            m.patch_xml(m.patch_xml(source))

    def test_deterministic_package(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory) / "a.docx", Path(directory) / "b.docx"
            m.build(a)
            m.build(b)
            self.assertEqual(a.read_bytes(), b.read_bytes())

    def test_extra_attribute_rejected(self):
        from lxml import etree as ET

        w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        with ZipFile(m.BASE / "candidate.docx") as z:
            root = ET.fromstring(z.read("word/document.xml"))
        p = next(p for p in root.find(w + "body").findall(w + "p") if "".join(p.itertext()) == "第三条 保密")
        p.find(w + "pPr/" + w + "spacing").set(w + "beforeLines", "1")
        with self.assertRaises(ValueError):
            m.patch_xml(ET.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True))

    def test_baseline_assessor_zero(self):
        result = m.assess(m.BASE / "wps.pdf")
        self.assertEqual(result["outcome"], "ZERO_INFLUENCE")
        self.assertFalse(result["strict_f2"])
        self.assertAlmostEqual(result["scores"]["whole"][0], 0.8950000618741911, places=9)

    def test_failed_score_or_gate_stops(self):
        scores = {k: [0.8, 0.81] for k in ("stage12_region", "later", "whole")}
        self.assertEqual(m.classify({"transfer": True, "conserved": True}, scores, False), "PASS_MECHANISM_ONLY")
        self.assertEqual(m.classify({"transfer": False, "conserved": True}, scores, False), "STOP")
        scores["whole"][1] = scores["whole"][0]
        self.assertEqual(m.classify({"transfer": True}, scores, False), "STOP")

    def test_retry_blocked_before_probe(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / "export-manifest.json").write_text("{}", encoding="utf-8")
            with patch("html_docx_wps_matrix.probe_wps") as probe:
                with self.assertRaises(ValueError):
                    m.export_once(out)
                probe.assert_not_called()
