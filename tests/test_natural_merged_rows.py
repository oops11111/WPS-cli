import copy
import json
import shutil
import subprocess
import unittest
from pathlib import Path


class NaturalMergedRowsTests(unittest.TestCase):
    def fixture(self):
        from test_measured_collapsed_widths import MeasuredWidthsTests

        from wps_ai_agent_cli.html_editable import _Node

        s, t, g, styles, boxes, body = MeasuredWidthsTests().fixture()
        first = t.children[0]
        a, b = g[0]
        a.attrs["rowspan"] = "2"
        c, d, e = (_Node("td", {}, [text]) for text in ("C", "D", "E"))
        rows = [first, _Node("tr", {}, [c]), _Node("tr", {}, [d, e])]
        t.children[:] = rows
        grid = [[a, b], [None, c], [d, e]]
        prototype = copy.copy(styles[id(a)])
        prototype.update(
            {
                "display": "table-cell",
                "vertical-align": "middle",
                "line-height": "20px",
                "font-size": "16px",
                "padding-top": "2px",
                "padding-bottom": "2px",
            }
        )
        for side in ("top", "right", "bottom", "left"):
            prototype[f"border-{side}-color"] = "rgb(85, 85, 85)"
        for cell, r, col, span in ((a, 0, 0, 2), (b, 0, 1, 1), (c, 1, 1, 1), (d, 2, 0, 1), (e, 2, 1, 1)):
            styles[id(cell)] = copy.copy(prototype)
            boxes[id(cell)] = {"x": 0.5 + col * 40, "y": 0.5 + r * 25, "width": 40, "height": span * 25}
        styles[id(t)]["display"] = "table"
        boxes[id(t)] = {"x": 0, "y": 0, "width": 81, "height": 76}
        for i, row in enumerate(rows):
            styles[id(row)] = copy.copy(styles[id(t)])
            styles[id(row)].update({"display": "table-row", "height": "25px"})
            boxes[id(row)] = {"x": 0.5, "y": 0.5 + i * 25, "width": 80, "height": 25}
        s.print_context["cssom"]["row_height_audit"] = {
            "checked": True,
            "declarations": [],
            "unsupported_rules": [],
            "html_height_attrs": [],
            "errors": [],
        }
        return s, t, grid, rows, styles, boxes

    def test_generic_merged_natural_rows(self):
        from wps_ai_agent_cli.docx_styling import measured_merged_row_minima

        s, t, g, rows, st, boxes = self.fixture()
        self.assertEqual(measured_merged_row_minima(s, t, g, rows, 200), [24, 24, 24])

    def test_missing_or_blocked_author_proof(self):
        from wps_ai_agent_cli.docx_styling import measured_merged_row_minima

        for key in ("checked", "declarations", "unsupported_rules", "html_height_attrs", "errors"):
            s, t, g, rows, st, boxes = self.fixture()
            s.print_context["cssom"]["row_height_audit"].pop(key)
            self.assertIsNone(measured_merged_row_minima(s, t, g, rows, 200))
        s, t, g, rows, st, boxes = self.fixture()
        s.print_context["cssom"]["row_height_audit"]["declarations"] = [{"property": "height", "value": "auto"}]
        self.assertIsNone(measured_merged_row_minima(s, t, g, rows, 200))

    def test_geometry_and_content_fail_closed(self):
        from wps_ai_agent_cli.docx_styling import measured_merged_row_minima

        for change in (
            "gap",
            "unequal",
            "spanbox",
            "line",
            "alignment",
            "border",
            "alpha",
            "witness",
            "display",
            "height",
            "sourceproof",
        ):
            s, t, g, rows, st, boxes = self.fixture()
            cell = g[0][0]
            if change == "gap":
                boxes[id(rows[1])]["y"] += 1
            elif change == "unequal":
                boxes[id(rows[1])]["height"] += 1
            elif change == "spanbox":
                boxes[id(cell)]["height"] -= 1
            elif change == "line":
                st[id(cell)]["font-size"] = "40px"
            elif change == "alignment":
                st[id(cell)]["vertical-align"] = "top"
            elif change == "border":
                st[id(cell)]["border-left-width"] = "2px"
            elif change == "alpha":
                st[id(cell)]["border-left-color"] = "rgba(85, 85, 85, 0.5)"
            elif change == "witness":
                st[id(g[0][1])]["line-height"] = "19px"
            elif change == "display":
                st[id(t)]["display"] = "grid"
            elif change == "height":
                st[id(rows[0])]["height"] = "auto"
            elif change == "sourceproof":
                s.print_context["cssom"].pop("row_height_audit")
            with self.subTest(change=change):
                self.assertIsNone(measured_merged_row_minima(s, t, g, rows, 200))

    def test_unmerged_tables_unchanged(self):
        from test_measured_collapsed_widths import MeasuredWidthsTests

        from wps_ai_agent_cli.docx_styling import measured_merged_row_minima

        s, t, g, st, boxes, body = MeasuredWidthsTests().fixture()
        self.assertIsNone(measured_merged_row_minima(s, t, g, t.children, 200))

    def test_complete_colspan_only_domain_keeps_old_rows(self):
        from wps_ai_agent_cli.docx_styling import measured_collapsed_widths, measured_merged_row_minima
        from wps_ai_agent_cli.html_editable import _Node

        s, t, g, rows, styles, boxes = self.fixture()
        a = g[0][0]
        a.attrs = {"colspan": "2"}
        rows[0].children[:] = [a]
        g[0] = [a, None]
        boxes[id(a)]["width"] = 80
        boxes[id(a)]["height"] = 25
        f = _Node("td", {}, ["F"])
        rows[1].children.insert(0, f)
        g[1][0] = f
        styles[id(f)] = copy.copy(styles[id(g[1][1])])
        boxes[id(f)] = {"x": 0.5, "y": 25.5, "width": 40, "height": 25}
        self.assertTrue(measured_collapsed_widths(s, t, g, 200))
        self.assertIsNone(measured_merged_row_minima(s, t, g, rows, 200))

    def test_author_veto_does_not_change_existing_width_qualification(self):
        from wps_ai_agent_cli.docx_styling import measured_collapsed_widths, measured_merged_row_minima

        s, t, g, rows, styles, boxes = self.fixture()
        s.print_context["cssom"]["row_height_audit"]["declarations"] = [{"property": "height"}]
        self.assertTrue(measured_collapsed_widths(s, t, g, 200))
        self.assertIsNone(measured_merged_row_minima(s, t, g, rows, 200))


class AuthorHeightAuditTests(unittest.TestCase):
    def test_cssom_declarations_unknown_rules_and_inline(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node unavailable")
        script = Path(__file__).resolve().parents[1] / "src/wps_ai_agent_cli/html_layout_playwright.cjs"
        js = """const {rowHeightAuthorAudit:a}=require(process.argv[1]);global.CSSRule={STYLE_RULE:1}; const style=(names)=>Object.assign(names,{getPropertyValue:()=> 'var(--x)'}); const run=(rules=[],inline=[],attrs=[])=>{global.document={styleSheets:[{cssRules:rules}],querySelectorAll:(selector)=>selector==='[style]'?inline:attrs};return a();}; console.log(JSON.stringify([run([{type:1,style:style(['color'])}]),run([{type:1,style:style(['height'])}]),run([{type:4,cssRules:[]}]),run([], [{style:style(['block-size'])}]),run([],[],[{tagName:'TD'}])]));"""
        done = subprocess.run([node, "-e", js, str(script)], capture_output=True, text=True, check=True)
        good, height, unknown, inline, attr = json.loads(done.stdout)
        self.assertTrue(good["checked"])
        self.assertEqual(good["declarations"], [])
        self.assertEqual(height["declarations"][0]["property"], "height")
        self.assertTrue(unknown["unsupported_rules"])
        self.assertEqual(inline["declarations"][0]["property"], "block-size")
        self.assertEqual(attr["html_height_attrs"], ["TD"])


if __name__ == "__main__":
    unittest.main()
