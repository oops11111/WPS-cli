"""Measured marker eligibility and bounded decorative-shape mapping."""

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from docx import Document
from docx.oxml.ns import qn

from wps_ai_agent_cli import html_styles
from wps_ai_agent_cli.docx_details_marker import ROLE, is_managed_marker, marker_size
from wps_ai_agent_cli.fidelity import read_model
from wps_ai_agent_cli.html_editable import convert_html_editable

ROOT = Path(__file__).resolve().parents[1]


def measured(source, size=16):
    styled = html_styles.load(source, use_browser=False)
    styled.mode = "browser"
    for node in html_styles._walk(styled.root):
        if node.tag == "summary":
            outer = styled.styles[id(node)]
            outer["text-lines"] = "1"
            outer["letter-spacing"] = "normal"
            outer["text-decoration-line"] = "none"
            for side in ("left", "right", "top", "bottom"):
                outer[f"padding-{side}"] = "0px"
                outer[f"border-{side}-width"] = "0px"
            style = {
                "display": "list-item",
                "list-style-type": "disclosure-closed",
                "list-style-position": "inside",
                "list-style-image": "none",
                "direction": "ltr",
                "writing-mode": "horizontal-tb",
                "text-indent": "0px",
                "font-size": f"{size}px",
                "font-family": "Arial",
                "font-style": "normal",
                "font-weight": "400",
                "color": "rgb(0, 0, 0)",
            }
            styled.summary_markers[id(node)] = {
                "style": style,
                "marker": {k: style[k] for k in ("font-size", "font-family", "font-style", "font-weight", "color")}
                | {"content": "normal"},
                "box": {"x": 8},
                "textRects": [{"x": 8 + 1.06 * size, "width": 50}],
            }
    return styled


class DetailsMarkerTests(unittest.TestCase):
    def test_browser_metadata_is_carried_separately(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "s.html"
            source.write_text("<details><summary>Summary</summary><p>Body</p></details>")
            baseline = measured(source)
            summary = next(n for n in html_styles._walk(baseline.root) if n.tag == "summary")
            metadata = baseline.summary_markers[id(summary)]
            reply = {
                "ok": True,
                "browser": "test",
                "elements": {
                    "1": {
                        "style": dict(baseline.style(summary)) | {"summary-marker": metadata},
                        "box": {"x": 8, "y": 0, "width": 200, "height": 21},
                    }
                },
            }
            with (
                patch.object(html_styles, "browser_runtime", return_value=("node", "edge")),
                patch.object(html_styles, "_browser_layout", return_value=reply),
            ):
                styled = html_styles.load(source)
            node = next(n for n in html_styles._walk(styled.root) if n.tag == "summary")
            self.assertEqual(styled.summary_markers[id(node)], metadata)
            self.assertNotIn("summary-marker", styled.style(node))

    def test_eligibility_and_fail_closed_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "s.html"
            source.write_text("<details><summary>Summary</summary><p>Body</p></details>")
            for control in (
                "valid",
                "none",
                "custom",
                "outside",
                "rtl",
                "wrap",
                "missing",
                "content",
                "advance",
                "cascade",
                "letter_spacing",
                "decoration",
            ):
                styled = measured(source)
                summary = next(n for n in html_styles._walk(styled.root) if n.tag == "summary")
                data = styled.summary_markers[id(summary)]
                if control == "none":
                    data["style"]["list-style-type"] = "none"
                if control == "custom":
                    data["style"]["list-style-type"] = "disc"
                if control == "outside":
                    data["style"]["list-style-position"] = "outside"
                if control == "rtl":
                    data["style"]["direction"] = "rtl"
                if control == "wrap":
                    data["textRects"].append(copy.deepcopy(data["textRects"][0]))
                if control == "missing":
                    data["marker"].pop("font-family")
                if control == "content":
                    data["marker"]["content"] = '"custom"'
                if control == "advance":
                    data["textRects"][0]["x"] += 1
                if control == "cascade":
                    styled.mode = "cascade"
                if control == "letter_spacing":
                    styled.styles[id(summary)]["letter-spacing"] = "1px"
                if control == "decoration":
                    styled.styles[id(summary)]["text-decoration-line"] = "underline"
                value, warning = marker_size(styled, summary)
                if control == "valid":
                    self.assertEqual(value, 12)
                    self.assertIsNone(warning)
                elif control == "none":
                    self.assertIsNone(value)
                    self.assertIsNone(warning)
                else:
                    self.assertIsNone(value)
                    self.assertTrue(warning)

    def test_multiple_sizes_trim_hidden_ids_and_narrow_count(self):
        for size in (16, 24):
            with tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "s.html"
                source.write_text(
                    "<details><summary>  Summary  </summary><p>Body</p></details><details><summary>Second</summary><p>Retained</p></details>"
                )
                target = source.with_suffix(".docx")
                styled = measured(source, size)
                with patch.object(html_styles, "load", return_value=styled):
                    result = convert_html_editable(source, target, use_browser=False)
                self.assertTrue(result[0], result)
                document = Document(target)
                self.assertEqual([p.text for p in document.paragraphs], ["SummaryBody", "SecondRetained"])
                drawings = document.element.body.findall(".//" + qn("w:drawing"))
                self.assertEqual(len(drawings), 2)
                self.assertTrue(all(is_managed_marker(d) for d in drawings))
                self.assertEqual(len({d.find(".//" + qn("wp:docPr")).get("id") for d in drawings}), 2)
                self.assertEqual([r.font.hidden for r in document.paragraphs[0].runs], [False, None, True])
                self.assertFalse(any(b.kind == "image" for b in read_model(target).blocks))
                drawings[0].find(".//" + qn("a:path")).set("w", "123")
                self.assertFalse(is_managed_marker(drawings[0]))
                document.save(target)
                self.assertEqual(sum(b.kind == "image" for b in read_model(target).blocks), 1)

    def test_none_and_open_do_not_insert(self):
        for attrs in ('open="false"', ""):
            with tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "s.html"
                source.write_text(
                    f"<style>summary{{list-style:none}}</style><details {attrs}><summary>Summary</summary><p>Body</p></details>"
                )
                target = source.with_suffix(".docx")
                result = convert_html_editable(source, target, use_browser=False)
                self.assertTrue(result[0], result)
                self.assertFalse(Document(target).element.body.findall(".//" + qn("w:drawing")))
                self.assertFalse(any("marker was not preserved" in w for w in result[1]["warnings"]))

    def test_named_real_image_not_exempted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "image.docx"
            document = Document()
            document.add_picture(str(ROOT / "fixtures/html_complex/chart.png"))
            drawing = document.element.body.find(".//" + qn("w:drawing"))
            props = drawing.find(".//" + qn("wp:docPr"))
            props.set("name", "Closed details marker")
            props.set("descr", ROLE)
            self.assertFalse(is_managed_marker(drawing))
            document.save(path)
            self.assertEqual(sum(b.kind == "image" for b in read_model(path).blocks), 1)
