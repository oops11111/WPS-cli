import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from wps_ai_agent_cli.html_render import render_html

REPO_ROOT = Path(__file__).resolve().parents[1]
HTML_VISUAL_SMOKE = REPO_ROOT / "fixtures" / "phase3" / "html_visual_smoke.html"


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

    def test_matrix_smoke_fixture_is_local_only_and_ready_for_pdf(self):
        self.assertTrue(HTML_VISUAL_SMOKE.is_file(), f"missing fixture: {HTML_VISUAL_SMOKE}")
        html = HTML_VISUAL_SMOKE.read_text(encoding="utf-8")
        self.assertIn("P3-410-VISIBLE", html)
        self.assertIn("example.invalid", html)
        with TemporaryDirectory() as directory:
            destination = Path(directory) / "html_visual_smoke.pdf"

            def fake_run(_node, request, _timeout_seconds):
                self.assertEqual(Path(request["input_path"]), HTML_VISUAL_SMOKE.resolve())
                Path(request["output_path"]).write_bytes(b"%PDF-1.7 p3-410-matrix-smoke")
                return type(
                    "Completed",
                    (),
                    {
                        "stdout": json.dumps({
                            "ok": True,
                            "page_title": "P3-410 HTML visual smoke",
                            "document_height": 800,
                        }),
                        "stderr": "",
                        "returncode": 0,
                    },
                )()

            with patch("wps_ai_agent_cli.html_render._resolve_browser_runtime", return_value=("node", "edge")), patch(
                "wps_ai_agent_cli.html_render._run_renderer",
                side_effect=fake_run,
            ) as renderer:
                ok, data, errors = render_html(HTML_VISUAL_SMOKE, destination, "pdf")
            self.assertTrue(ok, errors)
            self.assertEqual(data["page_title"], "P3-410 HTML visual smoke")
            self.assertFalse(data["network_access"])
            self.assertTrue(destination.read_bytes().startswith(b"%PDF-"))
            renderer.assert_called_once()


class HtmlRenderPublishTests(unittest.TestCase):
    def render_with_fake_browser(self, root, stdout=None, output=None):
        source = root / "page.html"
        source.write_text("<p>x</p>", encoding="utf-8")
        destination = output or root / "page.pdf"

        def fake_run(_node, request, _timeout):
            Path(request["output_path"]).write_bytes(b"%PDF-1.7 body")
            payload = stdout if stdout is not None else json.dumps({"ok": True, "page_title": "t", "document_height": 1})
            return type("Completed", (), {"stdout": payload, "stderr": "", "returncode": 0})()

        with patch("wps_ai_agent_cli.html_render._resolve_browser_runtime", return_value=("node", "edge")), \
                patch("wps_ai_agent_cli.html_render._run_renderer", side_effect=fake_run):
            return render_html(source, destination, "pdf"), destination

    def test_falls_back_to_exclusive_create_when_hard_links_are_unsupported(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("wps_ai_agent_cli.html_render.os.link", side_effect=OSError("hard links unsupported")):
                (ok, data, errors), destination = self.render_with_fake_browser(root)
            self.assertTrue(ok, errors)
            self.assertEqual(destination.read_bytes(), b"%PDF-1.7 body")
            self.assertEqual(data["bytes"], len(b"%PDF-1.7 body"))
            self.assertEqual([item.name for item in root.iterdir() if item.name.startswith(".")], [])

    def test_fallback_still_refuses_to_overwrite_a_destination_that_appears_late(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "page.pdf"

            def link_fails_and_destination_appears(_source, target):
                Path(target).write_bytes(b"someone else")
                raise OSError("hard links unsupported")

            with patch("wps_ai_agent_cli.html_render.os.link", side_effect=link_fails_and_destination_appears):
                (ok, _data, errors), _ = self.render_with_fake_browser(root, output=destination)
            self.assertFalse(ok)
            self.assertEqual(errors[0]["code"], "OUTPUT_ALREADY_EXISTS")
            self.assertEqual(destination.read_bytes(), b"someone else")

    def test_non_object_renderer_output_is_a_render_failure_not_a_crash(self):
        for stdout in ("[]", "1", '"text"', "null"):
            with self.subTest(stdout=stdout), TemporaryDirectory() as directory:
                (ok, _data, errors), destination = self.render_with_fake_browser(Path(directory), stdout=stdout)
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "RENDER_FAILED")
                self.assertFalse(destination.exists())

    def test_readme_documents_node_path_for_wheel_installs(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("NODE_PATH", readme)


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
