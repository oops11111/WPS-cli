"""Bounded standalone figure offset integration."""

import tempfile
import unittest
from pathlib import Path
from shutil import copyfile
from unittest.mock import patch

from docx import Document

from wps_ai_agent_cli import html_styles
from wps_ai_agent_cli.html_editable import convert_html_editable

ROOT = Path(__file__).resolve().parents[1]


class FigureIndentTests(unittest.TestCase):
    def convert(self, offset=40, html=None, mode="browser", wide=False):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "input.html"
            target = root / "out.docx"
            copyfile(ROOT / "fixtures/html_complex/chart.png", root / "chart.png")
            source.write_text(
                html
                or '<body><figure><img src="chart.png" width="320"><figcaption>Caption</figcaption></figure><p>Following</p></body>',
                encoding="utf-8",
            )
            styled = html_styles.load(source, use_browser=False)
            styled.mode = mode
            for n in html_styles._walk(styled.root):
                if n.tag in {"body", "figure", "img"}:
                    styled.boxes[id(n)] = {
                        "x": 8 if n.tag == "body" else 8 + offset,
                        "y": 0,
                        "width": 1200 if n.tag != "img" else (2000 if wide else 320),
                        "height": 160,
                    }
            with patch.object(html_styles, "load", return_value=styled):
                result = convert_html_editable(source, target, use_browser=False)
            self.assertTrue(result[0], result)
            doc = Document(target)
            return next(
                p
                for p in doc.paragraphs
                if p._p.find(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing") is not None
            )

    def test_measured_author_offsets(self):
        for offset in (0, 40, 80):
            p = self.convert(
                offset,
                html=f'<body><figure style="margin-left:{offset}px"><img src="chart.png" width="320"><figcaption>Caption</figcaption></figure><p>Following</p></body>',
            )
            actual = p.paragraph_format.left_indent
            self.assertEqual(actual.pt if actual is not None else 0, offset * 0.75)

    def test_legacy_controls(self):
        for kwargs in (
            {"mode": "cascade"},
            {"wide": True},
            {"html": '<body><div><img src="chart.png"></div></body>'},
            {"html": '<body><p><img src="chart.png"></p></body>'},
            {"html": '<body><section><img src="chart.png"></section></body>'},
            {"html": '<body><img src="chart.png"></body>'},
            {"html": '<body><figure><img src="chart.png"><p>Complex</p></figure></body>'},
        ):
            self.assertIsNone(self.convert(**kwargs).paragraph_format.left_indent)

    def test_eligibility_vetoes(self):
        from types import SimpleNamespace

        from wps_ai_agent_cli.docx_styling import Context
        from wps_ai_agent_cli.html_editable import _Node, figure_image_offset

        for scenario in (
            "no-box",
            "nested",
            "list",
            "table",
            "auto",
            "transform",
            "rtl",
            "center",
            "complex",
            "negative",
            "wide",
        ):
            with self.subTest(scenario=scenario):
                body = _Node("body")
                figure = _Node("figure")
                image = _Node("img")
                figure.children = [image]
                chain = [body]
                css = ""
                if scenario in {"nested", "list", "table"}:
                    chain.append(_Node({"nested": "figure", "list": "li", "table": "td"}[scenario]))
                if scenario == "complex":
                    figure.children.append(_Node("p"))
                if scenario == "auto":
                    css = "figure { margin-left:auto; }"
                if scenario == "transform":
                    body.attrs["style"] = "transform:translateX(2px)"
                styles = {
                    id(e): {"position": "static", "text-align": "start", "direction": "ltr"}
                    for e in [body, figure, image]
                }
                if scenario == "rtl":
                    styles[id(figure)]["direction"] = "rtl"
                if scenario == "center":
                    styles[id(figure)]["text-align"] = "center"
                boxes = {id(body): {"x": 8}, id(figure): {"x": 48}, id(image): {"x": 48, "width": 320}}
                if scenario == "no-box":
                    del boxes[id(figure)]
                if scenario == "negative":
                    boxes[id(figure)]["x"] = -1
                if scenario == "wide":
                    boxes[id(image)]["width"] = 2000
                styled = SimpleNamespace(
                    mode="browser",
                    css_text=css,
                    style=lambda e, styles=styles: styles.get(id(e), {}),
                    box=lambda e, boxes=boxes: boxes.get(id(e)),
                    pseudo_elements=lambda e: [],
                )
                self.assertIsNone(figure_image_offset(image, figure, chain, Context(styled), 700))


if __name__ == "__main__":
    unittest.main()
