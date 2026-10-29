"""HTML conversion bugs found in the code review of 0.11.0: lost inline text, eaten spaces, broken annotation, line
breaks in slides, long digit strings, and image paths."""

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from docx import Document
from PIL import Image

from wps_ai_agent_cli.html_editable import collapse_space, convert_html_editable
from wps_ai_agent_cli.html_office import _cell_value
from wps_ai_agent_cli.html_slides import convert_html_to_pptx
from wps_ai_agent_cli.html_styles import annotate


class _Folder(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.folder = Path(self._tmp.name)

    def docx_paragraphs(self, html: str) -> list[str]:
        source = self.folder / "page.html"
        source.write_text(html, encoding="utf-8")
        output = self.folder / "page.docx"
        output.unlink(missing_ok=True)
        ok, data, errors = convert_html_editable(source, output, use_browser=False)
        self.assertTrue(ok, errors)
        self.data = data
        return [paragraph.text for paragraph in Document(output).paragraphs]


class InlineTextTests(_Folder):
    def test_inline_elements_directly_in_a_div_keep_their_text(self):
        paragraphs = self.docx_paragraphs(
            '<div>Contact <a href="https://example.com">us</a> today <b>bold</b> and <code>x</code></div>'
        )
        self.assertEqual(paragraphs, ["Contact us today bold and x"])

    def test_inline_text_between_blocks_stays_in_order(self):
        paragraphs = self.docx_paragraphs("<div>before <span>span</span><p>block</p>after <em>em</em></div>")
        self.assertEqual(paragraphs, ["before span", "block", "after em"])


class SpaceTests(_Folder):
    def test_nbsp_and_the_ideographic_space_are_text(self):
        paragraphs = self.docx_paragraphs("<p>　　中文缩进&nbsp;&nbsp;x</p>")
        self.assertEqual(paragraphs, ["　　中文缩进  x"])

    def test_ascii_whitespace_still_collapses(self):
        self.assertEqual(collapse_space("a \t\n\r\f b 　c"), "a b 　c")
        self.assertEqual(self.docx_paragraphs("<p>\n  one   two\n</p>"), ["one two"])


class AnnotateTests(unittest.TestCase):
    def test_line_separators_other_than_newline_do_not_shift_the_numbers(self):
        for html in ("<p>a b</p>\n<span>x</span>", "<p>a\rb</p>\r<span>x</span>", "<p>a</p>\r\n<span>x</span>"):
            with self.subTest(html=html):
                self.assertIn('<span data-wps-i="1">x</span>', annotate(html))


class SlideLineBreakTests(_Folder):
    def test_br_is_a_line_break_not_the_text_x000b(self):
        source = self.folder / "deck.html"
        source.write_text("<section><h1>Title<br>two</h1><p>one<br>two</p></section>", encoding="utf-8")
        output = self.folder / "deck.pptx"
        ok, _data, errors = convert_html_to_pptx(source, output, use_browser=False)
        self.assertTrue(ok, errors)
        with zipfile.ZipFile(output) as package:
            slide = package.read("ppt/slides/slide1.xml").decode("utf-8")
        self.assertNotIn("_x000B_", slide)
        self.assertEqual(slide.count("<a:br"), 2)


class LongNumberTests(unittest.TestCase):
    def test_more_than_fifteen_digits_stays_text(self):
        for text in ("110105199001011234", "6222021234567890123", "1234567890123456", "1,234,567,890,123,456"):
            with self.subTest(text=text):
                self.assertEqual(_cell_value(text), (text, False, None))

    def test_fifteen_digits_is_still_a_number(self):
        self.assertEqual(_cell_value("123456789012345"), (123456789012345, False, None))


class ImagePathTests(_Folder):
    def test_a_percent_encoded_path_finds_the_image(self):
        (self.folder / "图片").mkdir()
        Image.new("RGB", (8, 8), "red").save(self.folder / "图片" / "截图 1.png")
        self.docx_paragraphs('<p><img src="%E5%9B%BE%E7%89%87/%E6%88%AA%E5%9B%BE%201.png" alt="shot"></p>')
        self.assertFalse(any("unavailable" in warning for warning in self.data.get("warnings", [])))
        with zipfile.ZipFile(self.folder / "page.docx") as package:
            self.assertTrue(any(name.startswith("word/media/") for name in package.namelist()))

    def test_an_svg_is_skipped_with_a_warning_instead_of_failing_the_document(self):
        (self.folder / "logo.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
        paragraphs = self.docx_paragraphs('<p>before <img src="logo.svg"> after</p>')
        self.assertEqual([paragraph.split() for paragraph in paragraphs], [["before", "after"]])
        self.assertIn("Image format not supported in Word, omitted: logo.svg", self.data["warnings"])


if __name__ == "__main__":
    unittest.main()
