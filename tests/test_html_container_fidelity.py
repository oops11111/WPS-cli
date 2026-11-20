"""Direct container text keeps computed CSS without repeating container spacing."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

from wps_ai_agent_cli.html_editable import convert_html_editable


class ContainerFidelityTests(unittest.TestCase):
    def convert(self, html):
        with tempfile.TemporaryDirectory() as tmp:
            source, target = Path(tmp) / "source.html", Path(tmp) / "out.docx"
            source.write_text(html, encoding="utf-8")
            ok, _data, errors = convert_html_editable(source, target, use_browser=False)
            self.assertTrue(ok, errors)
            return Document(target)

    def test_direct_text_keeps_container_paragraph_and_character_styles(self):
        for tag in ("div", "body", "section"):
            with self.subTest(tag=tag):
                document = self.convert(
                    f'<{tag} style="text-align:center;margin-left:40px;margin-top:16px;'
                    "margin-bottom:12px;text-indent:8px;line-height:24px;"
                    "background-color:#ffeeaa;border:2px solid #123456;"
                    f'font-family:Arial;font-size:20px;color:#345678">Direct <b>bold</b> text</{tag}>'
                )
                paragraph = document.paragraphs[0]
                self.assertEqual(paragraph.text, "Direct bold text")
                form = paragraph.paragraph_format
                self.assertEqual(form.alignment, WD_ALIGN_PARAGRAPH.CENTER)
                # Body margins belong to the page; nested blocks have paragraph indents.
                self.assertEqual(form.left_indent.pt, 1.5 if tag == "body" else 31.5)
                self.assertEqual(form.first_line_indent.pt, 6)
                self.assertEqual(form.space_before.pt, 12)
                self.assertEqual(form.space_after.pt, 9)
                self.assertEqual(form.line_spacing.pt, 18)
                props = paragraph._p.pPr
                self.assertEqual(props.find(qn("w:shd")).get(qn("w:fill")), "FFEEAA")
                self.assertEqual(props.find(qn("w:pBdr"))[0].get(qn("w:color")), "123456")
                self.assertEqual(paragraph.runs[0].font.name, "Arial")
                self.assertEqual(paragraph.runs[0].font.size.pt, 15)
                self.assertEqual(str(paragraph.runs[0].font.color.rgb), "345678")
                self.assertTrue(paragraph.runs[1].bold)

    def test_mixed_blocks_do_not_repeat_container_margins_or_page_break(self):
        document = self.convert(
            '<div style="text-align:right;margin-top:20px;margin-bottom:28px;page-break-before:always;'
            'font-size:20px;color:#345678">before <span>span</span>'
            '<p style="margin:0">block</p>after <em>em</em></div>'
        )
        before, block, after = document.paragraphs
        self.assertEqual([p.text for p in document.paragraphs], ["before span", "block", "after em"])
        self.assertEqual(before.paragraph_format.space_before.pt, 15)
        self.assertEqual(before.paragraph_format.space_after.pt, 0)
        self.assertTrue(before.paragraph_format.page_break_before)
        self.assertEqual(after.paragraph_format.space_before.pt, 0)
        self.assertEqual(after.paragraph_format.space_after.pt, 21)
        self.assertFalse(after.paragraph_format.page_break_before)
        self.assertEqual(after.alignment, WD_ALIGN_PARAGRAPH.RIGHT)
        self.assertTrue(after.runs[-1].italic)
        self.assertEqual(str(after.runs[0].font.color.rgb), "345678")
        self.assertEqual(block.alignment, WD_ALIGN_PARAGRAPH.RIGHT)

    def test_direct_text_keeps_links_and_nested_container_styles(self):
        document = self.convert(
            '<div style="margin-left:24px;color:#112233"><section style="margin-left:16px;'
            'text-align:right">Contact <a href="https://example.com">us</a><br>today</section></div>'
        )
        paragraph = document.paragraphs[0]
        self.assertEqual(paragraph.text, "Contact us\ntoday")
        self.assertEqual(paragraph.paragraph_format.left_indent.pt, 30)
        self.assertEqual(paragraph.alignment, WD_ALIGN_PARAGRAPH.RIGHT)
        self.assertEqual(str(paragraph.runs[0].font.color.rgb), "112233")
        self.assertEqual(len(paragraph._p.findall(qn("w:hyperlink"))), 1)
