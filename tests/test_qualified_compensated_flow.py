import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BREAKS = ("break-after", "page-break-after", "break-inside", "page-break-inside")


class QualifiedCompensatedFlowTests(unittest.TestCase):
    def fixture(self, source):
        from wps_ai_agent_cli import html_styles

        styled = html_styles.load(source, use_browser=False)
        styled.mode = "browser"
        y = 100
        for node in html_styles._walk(styled.root):
            style = dict(styled.style(node))
            style.update(
                {
                    "position": "static",
                    "transform": "none",
                    "zoom": "1",
                    "float": "none",
                    "writing-mode": "horizontal-tb",
                    "direction": "ltr",
                    "overflow-x": "visible",
                    "overflow-y": "visible",
                    "clip-path": "none",
                    "visibility": "visible",
                    "opacity": "1",
                    "font-family": "Arial",
                    "vertical-align": "baseline",
                    "text-lines": "1",
                }
            )
            for key in ("break-before", "page-break-before", *BREAKS):
                style[key] = "auto"
            for side in ("top", "right", "bottom", "left"):
                style[f"padding-{side}"] = style[f"border-{side}-width"] = "0px"
                style[f"margin-{side}"] = "0px"
            style.update({"font-size": "16px", "line-height": "20px"})
            if node.tag in {"p", "h2"}:
                heading = node.tag == "h2"
                style.update(
                    {
                        "display": "block",
                        "line-height": "30px" if heading else "20px",
                        "font-size": "20px" if heading else "16px",
                        "margin-top": "24px" if heading else "16px",
                        "margin-bottom": "24px" if heading else "16px",
                    }
                )
                styled.boxes[id(node)] = {"x": 0, "y": y, "width": 400, "height": 30 if heading else 20}
                y += (30 if heading else 20) + 24
            styled.styles[id(node)] = style
        return styled

    def convert(self, middle="", *, applied=True, mutate=None, table=True):
        from docx import Document

        from wps_ai_agent_cli import html_styles
        from wps_ai_agent_cli.html_editable import convert_html_editable

        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / "in.html", Path(directory) / "out.docx"
            prefix = "<table><tr><td>generic table</td></tr></table>" if table else ""
            source.write_text(
                f"<body>{prefix}<p>Alpha</p>{middle}<h2>Beta</h2><p>Gamma</p><h2>Delta</h2></body>", encoding="utf-8"
            )
            styled = self.fixture(source)
            if mutate:
                mutate(styled)
            table_status = {"side_effect": applied} if isinstance(applied, list) else {"return_value": applied}
            with (
                patch.object(html_styles, "load", return_value=styled),
                patch("wps_ai_agent_cli.docx_styling.apply_table", **table_status),
            ):
                ok, _, errors = convert_html_editable(source, target, use_browser=False)
            self.assertTrue(ok, errors)
            return Document(target)

    def headings(self, document):
        return [p.paragraph_format.space_before.pt for p in document.paragraphs if p.text in {"Beta", "Delta"}]

    def test_supported_flow_changes_native_request_without_table_identifiers(self):
        self.assertEqual(self.headings(self.convert()), [18, 18])
        for status in (False, None):
            self.assertEqual(self.headings(self.convert(applied=status)), [6, 6])
        self.assertEqual(self.headings(self.convert(table=False)), [6, 6])

    def test_missing_or_explicit_breaks_clear_entire_flow(self):
        from wps_ai_agent_cli import html_styles

        for key in BREAKS:
            for value in (None, "page", "column", "avoid", "always", "left", "right", ""):

                def mutate(styled, key=key, value=value):
                    p = next(n for n in html_styles._walk(styled.root) if n.tag == "p")
                    if value is None:
                        styled.styles[id(p)].pop(key)
                    else:
                        styled.styles[id(p)][key] = value

                self.assertEqual(self.headings(self.convert(mutate=mutate)), [6, 6], (key, value))

    def test_ancestor_break_and_effects_fail_closed(self):
        from wps_ai_agent_cli import html_styles

        for key, value in (("break-after", "page"), ("page-break-inside", "avoid"), ("transform", "scale(2)")):

            def mutate(styled, key=key, value=value):
                body = next(n for n in html_styles._walk(styled.root) if n.tag == "body")
                styled.styles[id(body)][key] = value

            self.assertEqual(self.headings(self.convert(mutate=mutate)), [6, 6])

    def test_inline_break_or_shifted_metrics_clear_flow(self):
        from wps_ai_agent_cli import html_styles
        from wps_ai_agent_cli.html_editable import _Node

        def mutate(styled, change=None):
            node = next(n for n in html_styles._walk(styled.root) if n.tag == "p")
            child = _Node("span", {}, list(node.children))
            node.children[:] = [child]
            style = dict(styled.style(node))
            style["display"] = "inline"
            for side in ("top", "right", "bottom", "left"):
                style[f"margin-{side}"] = "0px"
            if change:
                style[change[0]] = change[1]
            styled.styles[id(child)] = style

        self.assertEqual(self.headings(self.convert(mutate=mutate)), [18, 18])
        for change in (("break-inside", "avoid"), ("font-size", "24px"), ("vertical-align", "super")):
            self.assertEqual(self.headings(self.convert(mutate=lambda s, change=change: mutate(s, change))), [6, 6])

    def test_generic_margin_magnitudes_and_native_request_check(self):
        from wps_ai_agent_cli import html_styles
        from wps_ai_agent_cli.docx_styling import Context, qualified_margin_boundary

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.html"
            source.write_text("<body><p>Other content</p><h2>Other title</h2></body>", encoding="utf-8")
            for after, before in ((8, 12), (20, 32), (13, 27.5)):
                styled = self.fixture(source)
                p, h = [n for n in html_styles._walk(styled.root) if n.tag in {"p", "h2"}]
                styled.styles[id(p)]["margin-bottom"] = f"{after}px"
                styled.styles[id(h)]["margin-top"] = f"{before}px"
                styled.boxes[id(h)]["y"] = styled.box(p)["y"] + styled.box(p)["height"] + before
                context = Context(styled, last_space_after=after * 0.75)
                self.assertTrue(qualified_margin_boundary(context, p, h, [], after * 0.75))
                self.assertFalse(qualified_margin_boundary(context, p, h, [], after * 0.75 + 1))
                styled.boxes[id(h)]["y"] += 1
                self.assertFalse(qualified_margin_boundary(context, p, h, [], after * 0.75))
            for after, before in ((16, 16), (24, 16), (0, 24)):
                styled = self.fixture(source)
                p, h = [n for n in html_styles._walk(styled.root) if n.tag in {"p", "h2"}]
                styled.styles[id(p)]["margin-bottom"] = f"{after}px"
                styled.styles[id(h)]["margin-top"] = f"{before}px"
                styled.boxes[id(h)]["y"] = styled.box(p)["y"] + styled.box(p)["height"] + max(after, before)
                self.assertFalse(
                    qualified_margin_boundary(Context(styled, last_space_after=after * 0.75), p, h, [], after * 0.75)
                )

    def test_unproven_boundary_clears_following_authorization(self):
        from wps_ai_agent_cli import html_styles

        def mutate(styled):
            heading = next(n for n in html_styles._walk(styled.root) if n.tag == "h2")
            styled.boxes[id(heading)]["y"] += 1

        self.assertEqual(self.headings(self.convert(mutate=mutate)), [6, 6])

    def test_intervening_flow_transitions_do_not_leak(self):
        for middle in (
            "raw",
            "<span>inline</span>",
            "<div>x</div>",
            "<ul><li>x</li></ul>",
            "<hr>",
            "<figure>x</figure>",
            "<pre>x</pre>",
            "<details><summary>x</summary><p>y</p></details>",
            "<table><tr><td>new</td></tr></table>",
        ):
            # A second table with applied=False must not preserve the first table's token.
            document = self.convert(middle, applied=[True, False] if middle.startswith("<table") else True)
            values = self.headings(document)
            self.assertNotEqual(values, [18, 18], middle)

    def test_missing_or_unmeasured_geometry_is_not_authorized(self):
        from wps_ai_agent_cli import html_styles

        mutations = (
            ("line-height", "normal"),
            ("text-lines", "2"),
            ("padding-top", "1px"),
            ("overflow-x", "hidden"),
        )
        for key, value in mutations:

            def mutate(styled, key=key, value=value):
                p = next(n for n in html_styles._walk(styled.root) if n.tag == "p")
                styled.styles[id(p)][key] = value

            self.assertNotEqual(self.headings(self.convert(mutate=mutate)), [18, 18])

    def test_negative_margin_guard_preserves_legacy_path(self):
        from wps_ai_agent_cli import html_styles
        from wps_ai_agent_cli.docx_styling import Context, qualified_flow_block

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.html"
            source.write_text("<body><p>generic</p></body>", encoding="utf-8")
            styled = self.fixture(source)
            node = next(n for n in html_styles._walk(styled.root) if n.tag == "p")
            styled.styles[id(node)]["margin-bottom"] = "-1px"
            self.assertFalse(qualified_flow_block(Context(styled), node, []))

    def test_actual_table_status_only_after_full_compensation(self):
        from docx import Document
        from test_natural_merged_rows import NaturalMergedRowsTests

        from wps_ai_agent_cli.docx_styling import Context, apply_table

        s, t, grid, rows, _, _ = NaturalMergedRowsTests().fixture()
        table = Document().add_table(rows=3, cols=2)
        self.assertIs(apply_table(table, t, grid, rows, Context(s), 200), True)
        table = Document().add_table(rows=3, cols=2)
        with patch("wps_ai_agent_cli.docx_styling.measured_merged_row_minima", return_value=None):
            self.assertIs(apply_table(table, t, grid, rows, Context(s), 200), False)
        with patch("wps_ai_agent_cli.docx_styling.measured_merged_row_minima", return_value=[24]):
            self.assertIs(apply_table(table, t, grid, rows, Context(s), 200), False)

    def test_collector_adds_exact_four_properties(self):
        source = (Path(__file__).resolve().parents[1] / "src/wps_ai_agent_cli/html_layout_playwright.cjs").read_text()
        properties = re.search(r"const PROPERTIES = \[(.*?)\];", source, re.S)[1]
        for name in BREAKS:
            self.assertEqual(properties.count(f"'{name}'"), 1)

    def test_old_newsletter_pdfsource_never_have_a_compensated_table(self):
        from qualified_flow_feasibility import extract

        result = extract()
        for case in ("newsletter", "pdfsource", "manual", "report"):
            self.assertTrue(all(table["minima"] is None for table in result["tables"][case]))
