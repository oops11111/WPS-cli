import copy
import unittest
from types import SimpleNamespace


class MeasuredWidthsTests(unittest.TestCase):
    def fixture(self):
        from wps_ai_agent_cli.html_editable import _Node

        cells = [_Node("td", {}, ["A"]), _Node("td", {}, ["B"])]
        row = _Node("tr", {}, cells)
        table = _Node("table", {}, [row])
        body = _Node("body", {}, [table])
        root = _Node("document", {}, [body])
        base = {
            "transform": "none",
            "zoom": "1",
            "writing-mode": "horizontal-tb",
            "direction": "ltr",
            "overflow-x": "visible",
            "overflow-y": "visible",
            "clip-path": "none",
            "position": "static",
            "float": "none",
            "visibility": "visible",
            "opacity": "1",
            "border-collapse": "collapse",
            "text-lines": "1",
            "white-space": "normal",
        }
        for side in ("top", "right", "bottom", "left"):
            base.update(
                {f"border-{side}-style": "solid", f"border-{side}-width": "1px", f"border-{side}-color": "#555555"}
            )
        for corner in ("top-left", "top-right", "bottom-left", "bottom-right"):
            base[f"border-{corner}-radius"] = "0px"
        styles = {id(n): copy.copy(base) for n in (body, table, row, *cells)}
        boxes = {id(c): {"x": 0, "y": 0, "width": 40.0, "height": 20} for c in cells}
        styled = SimpleNamespace(
            mode="browser",
            root=root,
            parser=SimpleNamespace(has_declarative_shadow_root=False),
            print_context={
                "cssom": {
                    "complete": True,
                    "imports": [],
                    "errors": [],
                    "links": [],
                    "style_sources": {"checked": True, "document_adopted_count": 0, "open_shadow_root_count": 0},
                }
            },
            style=lambda n: styles.get(id(n), {}),
            box=lambda n: boxes.get(id(n)),
            pseudo_elements=lambda n: [],
        )
        return styled, table, [cells], styles, boxes, body

    def test_measured_positive_and_legacy_fallback(self):
        from wps_ai_agent_cli.docx_styling import _column_widths, measured_collapsed_widths

        s, t, g, styles, boxes, body = self.fixture()
        self.assertTrue(measured_collapsed_widths(s, t, g, 200))
        self.assertEqual(_column_widths(s, t, g, 200), [40, 40])
        s.mode = "cascade"
        self.assertEqual(_column_widths(s, t, g, 200), [41, 41])

    def test_fail_closed_layout_border_content_and_audit(self):
        from wps_ai_agent_cli.docx_styling import measured_collapsed_widths
        from wps_ai_agent_cli.html_editable import _Node

        for change in (
            "metadata",
            "ancestor",
            "separate",
            "borderless",
            "mixed",
            "multiline",
            "nested",
            "missingbox",
            "scale",
            "import",
            "shadow",
            "complex",
            "hole",
            "rtl",
        ):
            with self.subTest(change=change):
                s, t, g, st, boxes, body = self.fixture()
                cell = g[0][0]
                if change == "metadata":
                    st[id(cell)].pop("zoom")
                elif change == "ancestor":
                    st[id(body)]["transform"] = "scale(2)"
                elif change == "separate":
                    st[id(t)]["border-collapse"] = "separate"
                elif change == "borderless":
                    st[id(cell)]["border-top-style"] = "none"
                elif change == "mixed":
                    st[id(cell)]["border-top-width"] = "2px"
                elif change == "multiline":
                    st[id(cell)]["text-lines"] = "2"
                elif change == "nested":
                    cell.children.append(_Node("table"))
                elif change == "missingbox":
                    boxes.pop(id(cell))
                elif change == "scale":
                    boxes[id(cell)]["width"] = 200
                elif change == "import":
                    s.print_context["cssom"]["imports"] = ["x.css"]
                elif change == "shadow":
                    s.print_context["cssom"]["style_sources"]["open_shadow_root_count"] = 1
                elif change == "complex":
                    cell.children.append(_Node("span"))
                elif change == "hole":
                    g[0][1] = None
                elif change == "rtl":
                    st[id(cell)]["direction"] = "rtl"
                self.assertFalse(measured_collapsed_widths(s, t, g, 200))

    def test_all_required_metadata_and_clipping(self):
        from wps_ai_agent_cli.docx_styling import measured_collapsed_widths

        for field in ("transform", "zoom", "writing-mode", "direction", "overflow-x", "overflow-y", "clip-path"):
            for target in ("cell", "ancestor"):
                with self.subTest(field=field, target=target):
                    s, t, g, st, boxes, body = self.fixture()
                    st[id(body if target == "ancestor" else g[0][0])].pop(field)
                    self.assertFalse(measured_collapsed_widths(s, t, g, 200))
        for field, value in (
            ("overflow-x", "hidden"),
            ("overflow-y", "auto"),
            ("clip-path", "inset(0px)"),
            ("writing-mode", "vertical-rl"),
            ("zoom", "2"),
            ("border-top-left-radius", "1px"),
        ):
            s, t, g, st, boxes, body = self.fixture()
            st[id(body)][field] = value
            self.assertFalse(measured_collapsed_widths(s, t, g, 200))

    def test_merge_witness_and_bad_measurements(self):
        from wps_ai_agent_cli.docx_styling import measured_collapsed_widths
        from wps_ai_agent_cli.html_editable import _Node

        s, t, g, st, boxes, body = self.fixture()
        span = _Node("th", {"colspan": "2"}, ["C"])
        row = _Node("tr", {}, [span])
        st[id(span)] = copy.copy(st[id(g[0][0])])
        st[id(row)] = copy.copy(st[id(t)])
        boxes[id(span)] = {"x": 0, "y": 0, "width": 80.0, "height": 20}
        t.children.insert(0, row)
        g.insert(0, [span, None])
        self.assertTrue(measured_collapsed_widths(s, t, g, 200))
        boxes[id(span)]["width"] = 81
        self.assertFalse(measured_collapsed_widths(s, t, g, 200))
        for value in (float("nan"), float("inf"), -1, 0):
            s, t, g, st, boxes, body = self.fixture()
            boxes[id(g[0][0])]["width"] = value
            self.assertFalse(measured_collapsed_widths(s, t, g, 200))


if __name__ == "__main__":
    unittest.main()
