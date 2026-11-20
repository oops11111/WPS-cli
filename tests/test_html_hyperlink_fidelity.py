"""Hyperlink styles survive conversion and cannot disappear from fidelity scoring."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor
from docx.text.run import Run

from wps_ai_agent_cli.fidelity import Block, Model, fidelity_check, read_model, score_formatting
from wps_ai_agent_cli.fidelity import Run as FidelityRun
from wps_ai_agent_cli.html_editable import convert_html_editable


class HyperlinkFidelityTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.source, self.target = self.root / "source.html", self.root / "out.docx"

    def convert(self, html):
        self.source.write_text(html, encoding="utf-8")
        ok, _data, errors = convert_html_editable(self.source, self.target, use_browser=False)
        self.assertTrue(ok, errors)
        return Document(self.target)

    def hyperlink_runs(self, paragraph):
        return [Run(r, paragraph) for link in paragraph._p.findall(qn("w:hyperlink")) for r in link.findall(qn("w:r"))]

    def test_link_keeps_computed_font_size_color_and_decoration(self):
        document = self.convert(
            '<p style="font-family:Arial;font-size:20px">Before '
            '<a href="https://example.com" style="color:#123456;text-decoration:none">linked</a> after</p>'
        )
        paragraph = document.paragraphs[0]
        run = self.hyperlink_runs(paragraph)[0]
        self.assertEqual(run.font.name, "Arial")
        self.assertEqual(run.font.size.pt, 15)
        self.assertEqual(str(run.font.color.rgb), "123456")
        self.assertFalse(run.underline)
        self.assertEqual(paragraph.text, "Before linked after")
        link = paragraph._p.find(qn("w:hyperlink"))
        relation = paragraph.part.rels[link.get(qn("r:id"))]
        self.assertTrue(relation.is_external)
        self.assertEqual(relation.target_ref, "https://example.com")

    def test_nested_inline_styles_and_order_remain_inside_the_link(self):
        document = self.convert(
            '<p style="font-size:20px">before <a href="https://example.com">plain '
            "<b>bold</b> <em>italic</em><br>end</a> after</p>"
        )
        runs = self.hyperlink_runs(document.paragraphs[0])
        self.assertEqual("".join(r.text for r in runs), "plain bold italic\nend")
        self.assertTrue(next(r for r in runs if r.text == "bold").bold)
        self.assertTrue(next(r for r in runs if r.text == "italic").italic)
        model = read_model(self.target)
        self.assertEqual("".join(r.text for r in model.blocks[0].runs), "before plain bold italic\nend after")

    def test_links_in_body_cells_header_and_footer_are_read_with_their_runs(self):
        self.convert(
            '<header data-page="header"><p><a href="https://example.com/h">Header</a></p></header>'
            '<p>Before <a href="https://example.com/b">Body</a> After</p>'
            '<table><tr><td><a href="https://example.com/c">Cell</a></td></tr></table>'
            '<footer data-page="footer"><p><a href="https://example.com/f">Footer</a></p></footer>'
        )
        model = read_model(self.target)
        self.assertEqual([r.text for r in model.blocks[0].runs], ["Before ", "Body", " After"])
        for label in ("Cell", "Header", "Footer"):
            self.assertEqual(sum(r.text == label for b in model.blocks for r in b.runs), 1)

    def test_wrong_or_missing_hyperlink_formatting_fails_the_verdict(self):
        original = self.convert(
            '<p style="font-size:20px"><a href="https://example.com" style="color:#123456">linked</a></p>'
        )
        ok, report, errors = fidelity_check(self.source, self.target, layout=False, use_browser=False)
        self.assertTrue(ok, errors)
        self.assertEqual(report["aspects"]["formatting"]["score"], 1.0)
        for mutation in ("size", "color", "missing"):
            with self.subTest(mutation=mutation):
                paragraph = original.paragraphs[0]
                run = self.hyperlink_runs(paragraph)[0]
                prior_size, prior_color = run.font.size, run.font.color.rgb
                link = paragraph._p.find(qn("w:hyperlink"))
                if mutation == "size":
                    run.font.size = Pt(8)
                elif mutation == "color":
                    run.font.color.rgb = RGBColor.from_string("FF0000")
                else:
                    link.remove(run._r)
                damaged = self.root / (mutation + ".docx")
                original.save(damaged)
                _ok, report, _errors = fidelity_check(self.source, damaged, layout=False, use_browser=False)
                self.assertLess(report["aspects"]["formatting"]["score"], 1.0, report)
                self.assertFalse(report["verdict"]["formatting"])
                if mutation == "missing":
                    link.append(run._r)
                run.font.size, run.font.color.rgb = prior_size, prior_color

    def test_missing_styled_run_is_not_skipped_but_plain_text_is_not_applicable(self):
        source = Model("html", [Block("paragraph", "Missing", runs=[FidelityRun("Missing", size=15)])])
        score, problems = score_formatting(source, Model("docx"))
        self.assertLess(score, 1.0)
        self.assertTrue(any("missing" in p.lower() for p in problems))
        plain = Model("text", [Block("paragraph", "plain", runs=[FidelityRun("plain")])])
        self.assertEqual(score_formatting(plain, Model("text")), (1.0, []))

    def test_unsafe_link_stays_plain_text_without_external_relationship(self):
        document = self.convert('<p><a href="javascript:alert(1)">Unsafe</a></p>')
        self.assertEqual(document.paragraphs[0].text, "Unsafe")
        self.assertFalse(document.paragraphs[0]._p.findall(qn("w:hyperlink")))
        self.assertFalse(any(rel.is_external for rel in document.part.rels.values()))
