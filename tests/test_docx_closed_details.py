"""Retained text and explicit visibility at supported static details boundaries."""

import tempfile
import unittest
from pathlib import Path

from docx import Document

from wps_ai_agent_cli.fidelity import _docx_hidden, fidelity_check
from wps_ai_agent_cli.html_editable import convert_html_editable

ROOT = Path(__file__).resolve().parents[1]


class ClosedDetailsTests(unittest.TestCase):
    def convert(self, html):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        source = Path(temporary.name) / "input.html"
        source.write_text(html, encoding="utf-8")
        target = source.with_suffix(".docx")
        result = convert_html_editable(source, target, use_browser=False)
        self.assertTrue(result[0], result)
        return source, target, result

    def test_open_presence_stays_expanded_and_visible(self):
        for value in ("", '="false"', '="true"'):
            with self.subTest(value=value):
                source, target, result = self.convert(
                    f"<details open{value}><summary>Summary</summary><p>Body</p></details>"
                )
                doc = Document(target)
                self.assertEqual([p.text for p in doc.paragraphs], ["Summary", "Body"])
                self.assertFalse(any(r.font.hidden for p in doc.paragraphs for r in p.runs))
                self.assertFalse(any("closed details" in w for w in result[1]["warnings"]))
                self.assertTrue(fidelity_check(source, target, use_browser=False)[1]["passed"])

    def test_unsupported_keeps_content_and_warns(self):
        for inner in (
            "<p>Body</p>",
            "<summary>Summary</summary><p>Body</p><p>Extra</p>",
            "<summary><b>Summary</b></summary><p>Body</p>",
            "<summary>Summary</summary><summary>Extra</summary><p>Body</p>",
            '<summary>Summary</summary><p style="position:absolute">Body</p>',
            '<summary style="transform:translateY(2px)">Summary</summary><p>Body</p>',
            '<summary>Summary</summary><p><a href="https://example.com">Body</a></p>',
            "<summary>Summary</summary><p>Body</p><details><summary>Nested</summary><p>Extra</p></details>",
        ):
            with self.subTest(inner=inner):
                source, target, result = self.convert("<details>" + inner + "</details>")
                doc = Document(target)
                self.assertIn("Body", "".join(p.text for p in doc.paragraphs))
                self.assertFalse(any(r.font.hidden for p in doc.paragraphs for r in p.runs))
                warnings = [w for w in result[1]["warnings"] if "collapsed state was not preserved" in w]
                self.assertEqual(len(warnings), 2 if "Nested" in inner else 1)

    def test_missing_body_and_wrong_hidden_state_fail(self):
        source, target, _ = self.convert("<details><summary>Summary</summary><p>Unique body</p></details>")
        doc = Document(target)
        doc.paragraphs[0].runs[1].font.hidden = False
        doc.save(target)
        self.assertLess(fidelity_check(source, target, use_browser=False)[1]["aspects"]["formatting"]["score"], 1)
        doc.paragraphs[0].runs[1].text = ""
        doc.save(target)
        self.assertLess(fidelity_check(source, target, use_browser=False)[1]["aspects"]["text"]["score"], 1)

    def test_repeated_text_cannot_substitute_visible_summary(self):
        source, target, _ = self.convert("<details><summary>Repeat</summary><p>Repeat</p></details>")
        doc = Document(target)
        doc.paragraphs[0].runs[1].text = ""
        doc.save(target)
        self.assertLess(fidelity_check(source, target, use_browser=False)[1]["aspects"]["formatting"]["score"], 1)

    def test_hidden_style_toggle_and_direct_override(self):
        from docx.enum.style import WD_STYLE_TYPE

        doc = Document()
        paragraph = doc.add_paragraph()
        run = paragraph.add_run("Test")
        paragraph.style.font.hidden = True
        self.assertTrue(_docx_hidden(run))
        character = doc.styles.add_style("Hidden character", WD_STYLE_TYPE.CHARACTER)
        character.font.hidden = True
        run.style = character
        self.assertFalse(_docx_hidden(run))
        run.font.hidden = True
        self.assertTrue(_docx_hidden(run))
        run.font.hidden = False
        self.assertFalse(_docx_hidden(run))

    def test_old_expanded_report_fails_hidden_state_check(self):
        ok, result, errors = fidelity_check(
            ROOT / "fixtures/html_complex/report.html",
            ROOT / "artifacts/html-docx-wps-matrix-20261121/A-report-docx/converted.docx",
            use_browser=False,
        )
        self.assertTrue(ok, errors)
        self.assertLess(result["aspects"]["formatting"]["score"], 1)
        self.assertTrue(any("hidden True -> False" in p for p in result["aspects"]["formatting"]["problems"]))
        self.assertTrue(
            any(
                "收入按权责发生制确认" in p and "hidden True -> False" in p
                for p in result["aspects"]["formatting"]["problems"]
            )
        )

    def test_supported_closed_retains_body_without_flow_and_scores(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "input.html"
            source.write_text(
                '<details><summary>Summary</summary><p style="color:red">Retained body</p></details><p>Following</p>',
                encoding="utf-8",
            )
            target = Path(folder) / "output.docx"
            ok, data, errors = convert_html_editable(source, target, use_browser=False)
            self.assertTrue(ok, errors)
            document = Document(target)
            self.assertEqual([p.text for p in document.paragraphs], ["SummaryRetained body", "Following"])
            self.assertFalse(bool(document.paragraphs[0].runs[0].font.hidden))
            self.assertTrue(document.paragraphs[0].runs[1].font.hidden)
            self.assertEqual(str(document.paragraphs[0].runs[1].font.color.rgb), "FF0000")
            result = fidelity_check(source, target, use_browser=False)
            self.assertTrue(result[1]["passed"], result)
