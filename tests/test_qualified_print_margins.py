"""Current identity and complete CSSOM gate for bounded horizontal margins."""

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from docx import Document

from wps_ai_agent_cli import html_styles
from wps_ai_agent_cli.docx_styling import apply_page, qualified_horizontal_print_margins

INFO = {
    "platform": "win32",
    "executable": r"C:\Edge\msedge.exe",
    "runtime": {"product": "Edg/157.0.4341.60"},
    "cssom": {"complete": True, "links": [], "page_rules": [], "imports": [], "errors": []},
}


class QualifiedMarginTests(unittest.TestCase):
    def styled(self, root):
        p = Path(root) / "input.html"
        p.write_text("<body>ANCHOR</body>", encoding="utf-8")
        s = html_styles.load(p, use_browser=False)
        s.mode = "browser"
        s.browser = "157.0.4341.60"
        s.print_context = copy.deepcopy(INFO)
        return s

    def test_only_horizontal_margins_change(self):
        with tempfile.TemporaryDirectory() as d, patch("platform.system", return_value="Windows"):
            s = self.styled(d)
            before, after = Document(), Document()
            apply_page(before, s, fidelity="appearance")
            apply_page(after, s)
            a, b = before.sections[0], after.sections[0]
            self.assertEqual((a.left_margin.twips, a.right_margin.twips), (687, 687))
            self.assertEqual((b.left_margin.twips, b.right_margin.twips), (675, 675))
            for k in ("top_margin", "bottom_margin", "header_distance", "footer_distance", "page_width", "page_height"):
                self.assertEqual(getattr(a, k), getattr(b, k))

    def test_fail_closed_contexts(self):
        changes = [
            {},
            {**INFO, "platform": "linux"},
            {**INFO, "executable": "chrome.exe"},
            {**INFO, "runtime": {"product": "Chrome/157.0.4341.60"}},
            {**INFO, "runtime": {"product": "Edg/158.0.0.0"}},
        ]
        for k, value in [
            ("complete", False),
            ("page_rules", ["@page {}"]),
            ("imports", ['@import "a.css"']),
            ("errors", ["SecurityError"]),
            ("links", [{"has_sheet": False}]),
        ]:
            c = copy.deepcopy(INFO)
            c["cssom"][k] = value
            changes.append(c)
        with tempfile.TemporaryDirectory() as d, patch("platform.system", return_value="Windows"):
            s = self.styled(d)
            for context in changes:
                s.print_context = context
                self.assertFalse(qualified_horizontal_print_margins(s, "editable"), context)
            s.print_context = copy.deepcopy(INFO)
            self.assertFalse(qualified_horizontal_print_margins(s, "appearance"))
            s.page = {"margin-left": "10mm"}
            self.assertFalse(qualified_horizontal_print_margins(s, "editable"))

    def test_actual_cssom_rejects_recursive_page_import_missing(self):
        for name, css, link in (
            ("nested", "@media print { @page {margin:12mm} }", False),
            ("import", "@import url(child.css);", False),
            ("missing", "", True),
        ):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                source = root / "input.html"
                (root / "child.css").write_text("body{color:black}", encoding="utf-8")
                source.write_text(
                    "<style>"
                    + css
                    + "</style>"
                    + ('<link rel="stylesheet" href="missing.css">' if link else "")
                    + "<body>ANCHOR</body>",
                    encoding="utf-8",
                )
                styled = html_styles.load(source)
                if styled.mode != "browser":
                    self.skipTest("Browser unavailable")
                self.assertFalse(qualified_horizontal_print_margins(styled, "editable"))
                context = styled.print_context["cssom"]
                if name == "nested":
                    self.assertTrue(context["page_rules"])
                if name == "import":
                    self.assertTrue(context["imports"])
                if name == "missing":
                    self.assertFalse(context["complete"])

    def test_package_allowlist_rejects_extra_or_wrong_derived_width(self):
        import importlib.util
        from zipfile import ZipFile

        spec = importlib.util.spec_from_file_location(
            "package_gate", Path(__file__).resolve().parents[1] / "scripts/qualified_margin_package_gate.py"
        )
        gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gate)
        folder = Path(__file__).resolve().parents[1]
        with ZipFile(folder / "artifacts/figure-image-indent-20261121/A-contract-docx/converted.docx") as z:
            old = z.read("word/document.xml")
        with ZipFile(folder / "artifacts/alignment-aware-margins-preflight-20261121/A-contract-docx.docx") as z:
            new = z.read("word/document.xml")
        self.assertEqual(len(gate.verify_document_xml(old, new, "A-contract-docx")), 4)
        with self.assertRaises(ValueError):
            gate.verify_document_xml(old, new.replace(b'w:w="2639"', b'w:w="2640"', 1), "A-contract-docx")
        with self.assertRaises(ValueError):
            gate.verify_document_xml(old, new.replace(b'w:top="567"', b'w:top="568"', 1), "A-contract-docx")


if __name__ == "__main__":
    unittest.main()
