"""spreadsheet-chart-create adds a chart through WPS and reads the saved chart back (C-04).

WPS is simulated: the stand-in adds the chart with openpyxl, the way WPS would save one, so the offline read-back
(sheet -> drawing -> chart part) runs on a real package.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook, load_workbook
from openpyxl.chart import BarChart, LineChart, PieChart, Reference

from wps_ai_agent_cli import spreadsheet_chart as charts
from wps_ai_agent_cli.cli import run
from wps_ai_agent_cli.sessions import register_document

KINDS = {"column": (BarChart, "col"), "bar": (BarChart, "bar"), "line": (LineChart, None), "pie": (PieChart, None)}


def simulated_wps(*, wrong_type=False, outside=False, title_override=None, add=True):
    """A stand-in for _run_spreadsheet_chart_create_com that saves a chart like WPS does."""

    def run_com(path, sheet_name, range_address, anchor, chart_type, plot_by, title, width, height):
        workbook = load_workbook(path)
        sheet = workbook[sheet_name]
        if add:
            kind, direction = KINDS["line" if wrong_type else chart_type]
            chart = kind()
            if direction:
                chart.type = direction
            last_row = sheet.max_row + (5 if outside else 0)
            data = Reference(sheet, min_col=2, min_row=1, max_col=sheet.max_column, max_row=last_row)
            chart.add_data(data, titles_from_data=True)
            chart.set_categories(Reference(sheet, min_col=1, min_row=2, max_row=last_row))
            chart.title = title_override if title_override is not None else title
            sheet.add_chart(chart, anchor)
        workbook.save(path)
        return {"ok": True, "errors": [], "data": {"backend": "mock-wps", "chart_name": "Chart 1"}}

    return run_com


class ChartTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.workspace = root / "ws"
        self.workspace.mkdir()
        self.path = root / "销售.xlsx"
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Sales Q3"
        for row in (["月份", "华东", "华南"], ["7月", 120, 90], ["8月", 135, 98], ["9月", 150, 110]):
            sheet.append(row)
        workbook.create_sheet("空表")
        workbook.save(self.path)
        ok, record, errors = register_document("spreadsheets", str(self.path), self.workspace)
        self.assertTrue(ok, errors)
        self.document_id = record["document_id"]

    def create(self, chart_type="column", request_id="c1", com=None, **options):
        with patch.object(charts, "_run_spreadsheet_chart_create_com", side_effect=com or simulated_wps()) as fake:
            outcome = charts.create_spreadsheet_chart(
                self.document_id, "Sales Q3", "A1:C4", chart_type, request_id, workspace=self.workspace, **options
            )
        self.calls = fake.call_args_list
        return outcome

    def test_each_type_is_added_and_read_back(self):
        for index, chart_type in enumerate(("column", "bar", "line", "pie")):
            with self.subTest(chart_type=chart_type):
                ok, result, errors, _ = self.create(chart_type, request_id=f"t{index}", title=f"{chart_type} 图")
                self.assertTrue(ok, errors)
                self.assertTrue(all(result["checks"].values()), result["checks"])
                self.assertEqual(result["charts_after"], index + 1)
                self.assertEqual(result["chart_read_back"]["title"], f"{chart_type} 图")
                self.assertTrue(all(ref.startswith("'Sales Q3'!") for ref in result["chart_read_back"]["refs"]))

    def test_the_default_anchor_is_one_column_right_of_the_range(self):
        ok, result, errors, _ = self.create(title="趋势")
        self.assertTrue(ok, errors)
        self.assertEqual(result["anchor"], "E1")
        args = self.calls[0].args
        self.assertEqual(args[2:5], ("A1:C4", "E1", "column"))

    def test_dry_run_checks_without_backup_or_wps(self):
        with patch.object(charts, "create_backup") as backup:
            ok, result, errors, _ = self.create(dry_run=True, anchor="$G$3")
        self.assertTrue(ok, errors)
        self.assertEqual((result["anchor"], result["numeric_cells"], result["charts_before"]), ("G3", 6, 0))
        backup.assert_not_called()
        self.assertEqual(self.calls, [])

    def test_bad_requests_stop_before_wps(self):
        cases = [
            ({"chart_type": "radar"}, "INVALID_ARGUMENT"),
            ({"range_address": "A:A"}, "INVALID_RANGE"),
            ({"range_address": "A1"}, "INVALID_RANGE"),
            ({"range_address": "A1:A4"}, "INVALID_RANGE"),  # labels only, no numbers
            ({"anchor": "E1:F2"}, "INVALID_RANGE"),
            ({"sheet_name": "Missing"}, "SHEET_NOT_FOUND"),
            ({"width": 10}, "INVALID_ARGUMENT"),
        ]
        for index, (override, code) in enumerate(cases):
            arguments = {"sheet_name": "Sales Q3", "range_address": "A1:C4", "chart_type": "column", **override}
            with self.subTest(override=override), patch.object(charts, "_run_spreadsheet_chart_create_com") as com:
                ok, _result, errors, _ = charts.create_spreadsheet_chart(
                    self.document_id, request_id=f"bad{index}", workspace=self.workspace, **arguments
                )
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], code)
                com.assert_not_called()

    def test_a_chart_that_does_not_read_back_is_rolled_back(self):
        before = self.path.read_bytes()
        for index, com in enumerate(
            (
                simulated_wps(wrong_type=True),
                simulated_wps(outside=True),
                simulated_wps(title_override="别的"),
                simulated_wps(add=False),
            )
        ):
            # A rollback restores the file under a new inode, so it is registered again (as after any rollback).
            register_document("spreadsheets", str(self.path), self.workspace)
            with self.subTest(index=index):
                ok, result, errors, _ = self.create(com=com, request_id=f"rb{index}", title="趋势")
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "VALIDATION_FAILED")
                rollback = result["rollback"]
                # Saving without a chart can leave the bytes as they were; then there is nothing to restore.
                self.assertTrue(rollback["performed"] or "already matches" in rollback.get("reason", ""), rollback)
                self.assertEqual(self.path.read_bytes(), before)

    def test_existing_charts_are_told_apart_from_the_new_one(self):
        ok, _result, errors, _ = self.create(request_id="first", title="一")
        self.assertTrue(ok, errors)
        ok, result, errors, _ = self.create(request_id="second", title="一")  # same look as the first
        self.assertTrue(ok, errors)
        self.assertEqual((result["charts_before"], result["charts_after"]), (1, 2))
        self.assertEqual(len(charts.sheet_charts(self.path, "Sales Q3")), 2)
        self.assertEqual(charts.sheet_charts(self.path, "空表"), [])

    def test_replay_returns_the_recorded_result(self):
        ok, first, errors, _ = self.create(request_id="same", title="一")
        self.assertTrue(ok, errors)
        ok, second, errors, replayed = self.create(request_id="same", title="一")
        self.assertTrue(replayed)
        self.assertEqual(self.calls, [])
        self.assertEqual(second["charts_after"], first["charts_after"])

    def test_refs_are_checked_against_sheet_and_bounds(self):
        bounds = (1, 1, 3, 4)
        self.assertTrue(charts._ref_inside("'Sales Q3'!$B$2:$B$4", "Sales Q3", bounds))
        self.assertTrue(charts._ref_inside("Data!$A$1", "Data", bounds))
        self.assertTrue(charts._ref_inside("'It''s'!$A$1", "It's", bounds))
        self.assertFalse(charts._ref_inside("'Sales Q3'!$D$2:$D$4", "Sales Q3", bounds))
        self.assertFalse(charts._ref_inside("Other!$B$2", "Sales Q3", bounds))
        self.assertFalse(charts._ref_inside("garbage", "Sales Q3", bounds))


class CliTests(unittest.TestCase):
    def test_the_cli_passes_every_option(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous = os.getcwd()
            os.chdir(tmp)
            try:
                Workbook().save("b.xlsx")
                ok, record, _ = register_document("spreadsheets", "b.xlsx")
                stream = io.StringIO()
                with patch("wps_ai_agent_cli.cli_spreadsheet.create_spreadsheet_chart") as create:
                    create.return_value = (True, {"normalized_range": "A1:B3", "anchor": "D1"}, [], False)
                    code = run(
                        [
                            "spreadsheet-chart-create",
                            "--document-id",
                            record["document_id"],
                            "--sheet-name",
                            "S",
                            "--range",
                            "A1:B3",
                            "--chart-type",
                            "pie",
                            "--title",
                            "占比",
                            "--series-in",
                            "columns",
                            "--width",
                            "300",
                            "--height",
                            "200",
                        ],
                        output_stream=stream,
                    )
            finally:
                os.chdir(previous)
        self.assertEqual(code, 0, stream.getvalue())
        kwargs = create.call_args.kwargs
        self.assertEqual(
            (kwargs["title"], kwargs["plot_by"], kwargs["width"], kwargs["height"]), ("占比", "columns", 300, 200)
        )
        self.assertIn("pie chart", json.loads(stream.getvalue())["summary"])


if __name__ == "__main__":
    unittest.main()
