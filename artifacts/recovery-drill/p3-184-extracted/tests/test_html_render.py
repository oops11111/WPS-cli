import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from wps_ai_agent_cli.html_render import render_html


class HtmlRenderTests(unittest.TestCase):
    def test_rejects_invalid_format_and_existing_output_before_starting_browser(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "page.html"
            source.write_text("<h1>hello</h1>", encoding="utf-8")
            ok, _, errors = render_html(source, root / "page.pdf", "svg")
            self.assertFalse(ok)
            self.assertEqual(errors[0]["code"], "INVALID_ARGUMENT")
            output = root / "existing.pdf"
            output.write_bytes(b"keep")
            ok, _, errors = render_html(source, output, "pdf")
            self.assertFalse(ok)
            self.assertEqual(errors[0]["code"], "OUTPUT_ALREADY_EXISTS")
            self.assertEqual(output.read_bytes(), b"keep")

    def test_requires_matching_output_extension(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "page.html"
            source.write_text("<p>hello</p>", encoding="utf-8")
            ok, _, errors = render_html(source, Path(directory) / "page.png", "pdf")
            self.assertFalse(ok)
            self.assertEqual(errors[0]["code"], "OUTPUT_EXTENSION_MISMATCH")


@unittest.skipUnless(os.environ.get("WPS_AGENT_RUN_BROWSER_INTEGRATION") == "1", "set WPS_AGENT_RUN_BROWSER_INTEGRATION=1 to launch local Edge")
class HtmlRenderBrowserIntegrationTests(unittest.TestCase):
    def test_pdf_and_png_are_nonblank_and_network_isolation_is_reported(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pixel.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="80" height="40"><rect width="80" height="40" fill="#e02020"/></svg>',
                encoding="utf-8",
            )
            source = root / "page.html"
            source.write_text(
                '<!doctype html><html><head><title>Render Check</title><style>body{font:32px Arial;color:#123}img{display:block}</style></head><body><h1>Visible content</h1><img src="pixel.svg"><img src="https://example.invalid/blocked.png"></body></html>',
                encoding="utf-8",
            )
            for extension in ("pdf", "png"):
                ok, data, errors = render_html(source, root / f"page.{extension}", extension)
                self.assertTrue(ok, errors)
                self.assertFalse(data["javascript_enabled"])
                self.assertFalse(data["network_access"])
                self.assertEqual(data["page_title"], "Render Check")
                artifact = (root / f"page.{extension}").read_bytes()
                self.assertGreater(len(artifact), 1000)
                if extension == "png":
                    from PIL import Image, ImageStat
                    import io
                    image = Image.open(io.BytesIO(artifact)).convert("RGB")
                    self.assertGreater(image.width, 320)
                    self.assertGreater(sum(ImageStat.Stat(image).stddev), 20)


if __name__ == "__main__":
    unittest.main()
