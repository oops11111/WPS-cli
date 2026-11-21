"""Rule spacing must not be collapsed twice at the next block boundary."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from docx import Document

from wps_ai_agent_cli.html_editable import convert_html_editable

ROOT = Path(__file__).resolve().parents[1]


class RuleSpacingTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)

    def convert(self, html=None, source=None):
        if source is None:
            source = self.folder / "source.html"
            source.write_text(html, encoding="utf-8")
        target = self.folder / "out.docx"
        target.unlink(missing_ok=True)
        ok, _data, errors = convert_html_editable(source, target, use_browser=False)
        self.assertTrue(ok, errors)
        return Document(target)

    def test_original_manual_heading_after_rule_keeps_full_top_margin(self):
        document = self.convert(source=ROOT / "fixtures/fidelity/manual.html")
        heading = next(p for p in document.paragraphs if p.text == "3 常见问题")
        # 21px h2 * .83em top margin * .75 pt/px; native twip quantization.
        self.assertAlmostEqual(heading.paragraph_format.space_before.pt, 21 * 0.83 * 0.75, delta=0.05)

    def test_rule_to_paragraph_preserves_native_margin_requests_in_both_orders(self):
        for after, before in ((8, 20), (20, 8), (8, 0), (0, 20)):
            with self.subTest(after=after, before=before):
                document = self.convert(
                    f'<hr style="margin:0;margin-bottom:{after}px"><p style="margin:0;margin-top:{before}px">After</p>'
                )
                rule, paragraph = document.paragraphs
                self.assertEqual(rule.paragraph_format.space_after.pt, after * 0.75)
                self.assertEqual(paragraph.paragraph_format.space_before.pt, before * 0.75)

    def test_rule_boundary_is_consumed_only_once(self):
        document = self.convert(
            '<hr style="margin:0;margin-bottom:8px">'
            '<p style="margin:0;margin-top:20px;margin-bottom:12px">First</p>'
            '<p style="margin:0;margin-top:20px">Second</p>'
        )
        _rule, first, second = document.paragraphs
        self.assertEqual(first.paragraph_format.space_before.pt, 15)
        # Preserve the existing non-hr mapping, outside this narrow repair.
        self.assertEqual(second.paragraph_format.space_before.pt, 6)

    def test_intervening_table_keeps_its_existing_spacing_boundary(self):
        document = self.convert(
            '<hr style="margin:0;margin-bottom:8px">'
            '<table style="margin-bottom:12px"><tr><td>Cell</td></tr></table>'
            '<p style="margin:0;margin-top:20px">After table</p>'
        )
        self.assertEqual(document.tables[0].cell(0, 0).text, "Cell")
        self.assertEqual(document.paragraphs[-1].paragraph_format.space_before.pt, 15)

    def test_nonrule_spacing_behavior_is_unchanged(self):
        document = self.convert(
            '<p style="margin:0;margin-bottom:8px">First</p><p style="margin:0;margin-top:20px">Second</p>'
        )
        self.assertEqual(document.paragraphs[1].paragraph_format.space_before.pt, 9)
