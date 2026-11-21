"""Plain pre preserves authored boundary whitespace with HTML's single initial LF rule."""

import tempfile
import unittest
from pathlib import Path

from docx import Document

from wps_ai_agent_cli.html_editable import convert_html_editable

ROOT = Path(__file__).resolve().parents[1]


class PlainPreTests(unittest.TestCase):
    def test_boundary_and_internal_whitespace_across_line_endings(self):
        for newline in ("\n", "\r\n", "\r"):
            for text, expected in (
                ("\nCode\n    ", "Code\n    "),
                ("\n\nCode\n\t ", "\nCode\n\t "),
                ("Code\n\n  Indent", "Code\n\n  Indent"),
                (" Code ", " Code "),
                ("Code", "Code"),
            ):
                with self.subTest(newline=repr(newline), text=repr(text)):
                    raw = ("<pre>" + text.replace("\n", newline) + "</pre>").encode()
                    paragraph = self.convert(raw).paragraphs[0]
                    self.assertEqual(paragraph.text, expected)
                    if expected.endswith(" "):
                        texts = paragraph._p.findall(
                            ".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"
                        )
                        self.assertEqual(texts[-1].get("{http://www.w3.org/XML/1998/namespace}space"), "preserve")

    def test_nested_code_and_override_retain_legacy_trimming(self):
        for html in ("<pre><code>\n\nCode\n  </code></pre>", '<pre style="white-space:normal">\n\nCode\n  </pre>'):
            self.assertEqual(self.convert(html.encode()).paragraphs[0].text, "Code")

    def test_ordinary_empty_and_whitespace_only_controls(self):
        doc = self.convert(b"<pre></pre><pre> \r\n </pre><p>  Following  text  </p>")
        self.assertEqual([p.text for p in doc.paragraphs], ["Following text"])

    def test_comment_first_or_terminal_retains_legacy_behavior(self):
        for text in ("<!--comment-->\n\nCode\n  ", "\n\nCode\n  <!--comment-->"):
            with self.subTest(text=text):
                self.assertEqual(self.convert(("<pre>" + text + "</pre>").encode()).paragraphs[0].text, "Code")

    def test_original_manual_nested_code_unchanged(self):
        doc = self.convert(source=ROOT / "fixtures/fidelity/manual.html")
        paragraph = next(p for p in doc.paragraphs if "wps-agent doctor" in p.text)
        self.assertEqual(paragraph.text, "wps-agent doctor\nwps-agent capabilities --json")

    def convert(self, raw=None, source=None):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        folder = Path(temporary.name)
        if source is None:
            source = folder / "source.html"
            source.write_bytes(raw)
        target = folder / "out.docx"
        result = convert_html_editable(source, target, use_browser=False)
        self.assertTrue(result[0], result)
        return Document(target)

    def test_original_report_retains_terminal_indented_line(self):
        paragraph = next(
            p for p in self.convert(source=ROOT / "fixtures/html_complex/report.html").paragraphs if "SELECT" in p.text
        )
        self.assertTrue(paragraph.text.endswith("GROUP BY region;\n    "), repr(paragraph.text))
        self.assertEqual(
            len(paragraph._p.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}br")), 4
        )
