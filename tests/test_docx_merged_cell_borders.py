"""Inspect physical merge-continuation cells; table.cell aliases their origin."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

from wps_ai_agent_cli.html_editable import convert_html_editable

ROOT = Path(__file__).resolve().parents[1]


class MergedCellBorderTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)

    def convert(self, html=None, source=None):
        if source is None:
            source = self.folder / "source.html"
            source.write_text(html, encoding="utf-8")
        target = self.folder / "out.docx"
        ok, _data, errors = convert_html_editable(source, target, use_browser=False)
        self.assertTrue(ok, errors)
        return Document(target)

    def edges(self, cell):
        borders = cell.tcPr.findall(qn("w:tcBorders"))
        self.assertEqual(len(borders), 1)
        return {edge.tag.rsplit("}", 1)[-1]: edge.get(qn("w:val")) for edge in borders[0]}

    def assert_shading(self, cell, color):
        shades = cell.tcPr.findall(qn("w:shd"))
        self.assertEqual(len(shades), 1)
        self.assertEqual(shades[0].get(qn("w:fill")), color)
        names = [child.tag.rsplit("}", 1)[-1] for child in cell.tcPr]
        self.assertLess(names.index("tcBorders"), names.index("shd"))
        if "tcMar" in names:
            self.assertLess(names.index("shd"), names.index("tcMar"))

    def test_original_contract_continuations_keep_the_header_perimeter_and_fill(self):
        document = self.convert(source=ROOT / "fixtures/fidelity/contract.html")
        table = document.tables[1]
        first, second = table._tbl.tr_lst[:2]
        for origin, continuation in ((first.tc_lst[0], second.tc_lst[0]), (first.tc_lst[-1], second.tc_lst[-1])):
            self.assertEqual(origin.tcPr.vMerge.val, "restart")
            self.assertEqual(continuation.tcPr.vMerge.val, "continue")
            self.assertEqual(
                self.edges(origin), {"top": "single", "left": "single", "bottom": "nil", "right": "single"}
            )
            self.assertEqual(
                self.edges(continuation), {"top": "nil", "left": "single", "bottom": "single", "right": "single"}
            )
            self.assert_shading(origin, "DDE6F0")
            self.assert_shading(continuation, "DDE6F0")
        self.assertEqual(table.cell(0, 0).text, "阶段")
        self.assertEqual(table.cell(0, 3).text, "条件")

    def test_three_row_two_column_merge_styles_physical_cells_without_internal_seams(self):
        document = self.convert(
            "<style>td{border:2px solid #123456} .merged{background:#ffeeaa}</style>"
            '<table><tr><td rowspan="3" colspan="2" class="merged">Owner</td><td>A</td></tr>'
            "<tr><td>B</td></tr><tr><td>C</td></tr></table>"
        )
        table = document.tables[0]
        for i, row in enumerate(table._tbl.tr_lst):
            tc = row.tc_lst[0]
            self.assertEqual(tc.tcPr.gridSpan.val, 2)
            edges = self.edges(tc)
            self.assertEqual(edges["top"], "single" if i == 0 else "nil")
            self.assertEqual(edges["bottom"], "single" if i == 2 else "nil")
            self.assertEqual(edges["left"], "single")
            self.assertEqual(edges["right"], "single")
            self.assert_shading(tc, "FFEEAA")
        self.assertEqual([table.cell(i, 2).text for i in range(3)], ["A", "B", "C"])
        self.assertEqual(table.cell(0, 0).text, "Owner")

    def test_unmerged_cells_keep_their_own_edges_and_fills(self):
        document = self.convert(
            '<table><tr><td style="border:1px solid #123456;background:#ffeeaa">A</td><td>B</td></tr></table>'
        )
        first, second = document.tables[0]._tbl.tr_lst[0].tc_lst
        self.assertEqual(self.edges(first), dict.fromkeys(("top", "left", "bottom", "right"), "single"))
        self.assert_shading(first, "FFEEAA")
        self.assertIsNone(second.tcPr.find(qn("w:tcBorders")))
        self.assertIsNone(second.tcPr.find(qn("w:shd")))

    def test_borderless_vertical_merge_does_not_gain_a_visible_perimeter_or_fill(self):
        document = self.convert('<table><tr><td rowspan="2">A</td><td>B</td></tr><tr><td>C</td></tr></table>')
        for row in document.tables[0]._tbl.tr_lst:
            cell = row.tc_lst[0]
            self.assertIsNone(cell.tcPr.find(qn("w:tcBorders")))
            self.assertIsNone(cell.tcPr.find(qn("w:shd")))
