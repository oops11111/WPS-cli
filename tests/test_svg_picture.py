"""Native SVG pictures in a presentation (svgBlip + raster fallback), and the parser keeping an <svg> as a leaf."""

from __future__ import annotations

import io
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from pptx import Presentation
from pptx.util import Inches

from wps_ai_agent_cli.html_editable import _text, _TreeParser, _walk
from wps_ai_agent_cli.svg_picture import SVG_BLIP_EXTENSION_URI, add_svg_picture

ROOT = Path(__file__).resolve().parents[1]

SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10" fill="red"/></svg>'


def _png_bytes() -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGBA", (4, 4), (255, 0, 0, 0)).save(buffer, "PNG")
    return buffer.getvalue()


class AddSvgPictureTests(unittest.TestCase):
    def test_svg_picture_has_an_svg_part_and_a_fallback_blip(self):
        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        add_svg_picture(slide, SVG.encode(), io.BytesIO(_png_bytes()), Inches(1), Inches(1), Inches(2), Inches(2))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "svg.pptx"
            prs.save(path)
            with zipfile.ZipFile(path) as archive:
                svg_parts = [name for name in archive.namelist() if name.endswith(".svg")]
                self.assertEqual(len(svg_parts), 1)
                self.assertEqual(archive.read(svg_parts[0]), SVG.encode())
                xml = archive.read("ppt/slides/slide1.xml").decode()
                self.assertIn("svgBlip", xml)
                self.assertIn(SVG_BLIP_EXTENSION_URI, xml)
                rels = archive.read("ppt/slides/_rels/slide1.xml.rels").decode()
                self.assertIn(svg_parts[0].replace("ppt/", "../"), rels)
                self.assertIn("[Content_Types].xml", archive.namelist())
                self.assertIn("image/svg+xml", archive.read("[Content_Types].xml").decode())


class ParserSvgTests(unittest.TestCase):
    def test_svg_stays_a_leaf_and_its_text_does_not_leak(self):
        parser = _TreeParser()
        parser.feed('<p>Hi</p><svg viewBox="0 0 10 10"><rect width="5" height="5"/><text>label</text></svg><p>Bye</p>')
        parser.close()
        svgs = [node for node in _walk(parser.root) if node.tag == "svg"]
        self.assertEqual(len(svgs), 1)
        self.assertEqual(svgs[0].children, [])  # the subtree stays opaque
        self.assertNotIn("label", _text(parser.root))
        self.assertIn("Hi", _text(parser.root))
        self.assertIn("Bye", _text(parser.root))
        # Still recorded as unsupported (the DOCX path and the round-trip still drop it);
        # the slide converter manages <svg> itself instead of warning on it.
        self.assertIn("svg", parser.unsupported_elements)


class SvgWithoutBrowserTests(unittest.TestCase):
    def test_svg_is_omitted_with_an_appearance_mode_warning(self):
        html = (
            "<!doctype html><html><body>"
            '<section class="slide"><h1>Title</h1><p>Body</p>'
            '<svg viewBox="0 0 10 10"><rect width="5" height="5"/></svg>'
            "</section></body></html>"
        )
        from wps_ai_agent_cli.html_slides import convert_html_to_pptx

        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"WPS_AGENT_NO_BROWSER": "1"}):
            source = Path(tmp) / "deck.html"
            source.write_text(html, encoding="utf-8")
            ok, data, errors = convert_html_to_pptx(source, Path(tmp) / "deck.pptx", fidelity="editable")
        self.assertTrue(ok, errors)
        self.assertNotIn("svg", data["mapped_objects"])
        self.assertTrue(
            any("<svg>" in warning and "appearance mode" in warning for warning in data["warnings"]),
            data["warnings"],
        )


if __name__ == "__main__":
    unittest.main()
