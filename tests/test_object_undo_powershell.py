"""The in-WPS undo scripts for worksheet shapes and charts (P10-004), run in pwsh against fake WPS objects.

The fake workbook has one selected object, chosen by WPSFAKE_KIND: a shape with text, a chart title, an axis title or
a chart series. Its state comes from environment variables (the object as the failed write left it), and the
script's JSON output is the only thing a test can see afterwards.
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wps_ai_agent_cli import open_documents

PWSH = os.environ.get("WPS_TEST_PWSH") or shutil.which("pwsh")

# A missing member on a WPS COM object raises; on these .NET fakes PowerShell returns $null instead. The shape
# scripts tell a shape from a chart element by whether $sel.Parent.HasTitle raises, so the fake run raises there.
_CHART_PROBE = "$null = [bool]$sel.Parent.HasTitle"

FAKE_OBJECT_BOOK_PRELUDE = r"""
Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
namespace WpsAgent {
  public static class Book {
    public static string Path = Environment.GetEnvironmentVariable("WPSFAKE_PATH") ?? "";
    public static string Kind = Environment.GetEnvironmentVariable("WPSFAKE_KIND") ?? "shape";
    // The shape text, the title text, or the series values joined by TAB.
    public static string Text = Environment.GetEnvironmentVariable("WPSFAKE_OBJECT_TEXT") ?? "";
    public static bool HasTitle = (Environment.GetEnvironmentVariable("WPSFAKE_HAS_TITLE") ?? "1") == "1";
    // What the cells a series is linked to hold; setting the series formula reads them again.
    public static string Linked = Environment.GetEnvironmentVariable("WPSFAKE_LINKED") ?? "";
    public static bool FormulaFails = Environment.GetEnvironmentVariable("WPSFAKE_FORMULA_FAILS") == "1";
    public static string Formula = Environment.GetEnvironmentVariable("WPSFAKE_FORMULA") ?? "";
    public static bool Stuck = Environment.GetEnvironmentVariable("WPSFAKE_STUCK") == "1";
    public static int Saves = 1;
    public static void Set(string value) { if (!Stuck) { Text = value; } }
  }
  public class FakeChars { public string Text { get { return Book.Text; } set { Book.Set(value); } } }
  public class FakeTextFrame { public FakeChars Characters() { return new FakeChars(); } }
  public class NotAChart { public bool HasTitle { get { throw new InvalidOperationException("no such property"); } } }
  public class FakeShape {
    public string Name { get { return "Chart 1"; } }
    public int Type { get { return 1; } }
    public FakeTextFrame TextFrame { get { return new FakeTextFrame(); } }
  }
  public class FakeShapeRange { public int Count { get { return 1; } } public FakeShape Item(int i) { return new FakeShape(); } }
  public class FakeChartObject { public string Name { get { return "Chart 1"; } } }
  public class FakeTitle { public string Text { get { return Book.HasTitle ? Book.Text : ""; } set { Book.Set(value); } } }
  public class FakeChart {
    public int ChartType { get { return 51; } }
    public bool HasTitle { get { return Book.HasTitle; } set { if (!Book.Stuck) { Book.HasTitle = value; } } }
    public FakeTitle ChartTitle { get { return new FakeTitle(); } }
    public FakeChartObject Parent { get { return new FakeChartObject(); } }
  }
  public class FakeAxis {
    public bool HasTitle { get { return Book.HasTitle; } set { if (!Book.Stuck) { Book.HasTitle = value; } } }
    public FakeTitle AxisTitle { get { return new FakeTitle(); } }
    public FakeChart Parent { get { return new FakeChart(); } }
  }
  public class FakeSeries {
    public string Name { get { return "Sales"; } }
    public FakeChart Parent { get { return new FakeChart(); } }
    public object Values {
      get {
        var parts = Book.Text.Split((char)9);
        var values = new object[parts.Length];
        for (int i = 0; i < parts.Length; i++) { values[i] = parts[i].Length == 0 ? null : (object)double.Parse(parts[i]); }
        return values;
      }
      set {
        var parts = new List<string>();
        foreach (object item in (object[])value) { parts.Add(item == null ? "" : item.ToString()); }
        Book.Set(string.Join(((char)9).ToString(), parts));
      }
    }
    public string Formula {
      get { return Book.Formula; }
      set { if (Book.FormulaFails) { throw new InvalidOperationException("formula refused"); } Book.Formula = value; Book.Set(Book.Linked); }
    }
  }
  public class TitleSelection { public FakeChart Parent { get { return new FakeChart(); } } }
  public class AxisTitleSelection { public FakeAxis Parent { get { return new FakeAxis(); } } }
  public class ShapeSelection {
    public FakeShapeRange ShapeRange { get { return new FakeShapeRange(); } }
    public NotAChart Parent { get { return new NotAChart(); } }
  }
  public class FakeWindow {
    public object Selection {
      get {
        if (Book.Kind == "chart_title") { return new TitleSelection(); }
        if (Book.Kind == "axis_title") { return new AxisTitleSelection(); }
        if (Book.Kind == "series") { return new FakeSeries(); }
        return new ShapeSelection();
      }
    }
  }
  public class FakeWindows { public int Count = 1; public FakeWindow Item(int i) { return new FakeWindow(); } }
  public class FakeWorkbook {
    public string FullName { get { return Book.Path; } }
    public bool Saved { get { return Book.Saves > 0; } }
    public bool ReadOnly { get { return false; } }
    public FakeWindows Windows { get { return new FakeWindows(); } }
    public void Save() { Book.Saves++; }
  }
  public class FakeWorkbooks { public int Count = 1; public FakeWorkbook Item(int i) { return new FakeWorkbook(); } }
  public class FakeApp {
    public string Name { get { return "Microsoft Excel"; } }
    public string Path { get { return "C:\\Kingsoft\\WPS Office\\office6"; } }
    public FakeWorkbooks Workbooks { get { return new FakeWorkbooks(); } }
  }
  public static class Running {
    public static object Get(string progId) { return progId == "ket.Application" ? new FakeApp() : null; }
  }
}
"@
"""


@unittest.skipUnless(PWSH, "PowerShell (pwsh) is required to run the undo scripts against fake WPS objects")
class ObjectUndoScriptTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.document = Path(tmp.name) / "book.xlsx"
        self.document.write_bytes(b"xlsx")
        patcher = patch("wps_ai_agent_cli.powershell_runner.powershell_executable", return_value=PWSH)
        patcher.start()
        self.addCleanup(patcher.stop)

    def obj(self, kind, text, params, action, **env):
        def render(script, values):
            if kind == "shape":
                script = script.replace(_CHART_PROBE, "throw 'not a chart element'")
            return FAKE_OBJECT_BOOK_PRELUDE + json.dumps(values).join(script.split("__PARAMS_JSON__"))

        environment = {"WPSFAKE_PATH": str(self.document), "WPSFAKE_KIND": kind, "WPSFAKE_OBJECT_TEXT": text, **env}
        with patch.dict(os.environ, environment), patch.object(open_documents, "_render", side_effect=render):
            result = open_documents._run_spreadsheet_attached_com(
                action, {"path": str(self.document), "expected_object_name": "Chart 1", **params}
            )
        self.assertTrue(result["ok"], result)
        return result["data"]

    def revert(self, kind, current, original, written, action, formula="", read_back="", **env):
        params = {
            "original_text": original,
            "written_text": written,
            "read_back_text": read_back,
            "original_formula": formula,
        }
        return self.obj(kind, current, params, action, **env)

    def test_each_object_kind_puts_the_original_text_back_and_saves(self):
        for kind, action, original, written in (
            ("shape", "selection-shape-revert", "Status: DRAFT", "Status: FIN"),
            ("chart_title", "selection-chart-title-revert", "Q3 sales", "Q3"),
            ("axis_title", "selection-axis-title-revert", "Quarter", "Mon"),
            ("series", "selection-series-values-revert", "10\t20", "30\t4"),
        ):
            with self.subTest(kind=kind):
                data = self.revert(kind, written, original, written, action, WPSFAKE_FORMULA_FAILS="1")
                self.assertEqual(data["status"], "reverted", data)
                self.assertEqual(data["read_back_text"], original)
                self.assertTrue(data["saved"])

    def test_a_deleted_title_is_shown_again_with_its_text(self):
        data = self.revert("chart_title", "", "Q3 sales", "", "selection-chart-title-revert", WPSFAKE_HAS_TITLE="0")
        self.assertEqual(data["status"], "reverted", data)
        self.assertEqual(data["read_back_text"], "Q3 sales")

    def test_a_series_gets_its_formula_back_so_it_reads_its_cells_again(self):
        data = self.revert(
            "series",
            "30\t40",
            "10\t20",
            "30\t40",
            "selection-series-values-revert",
            formula="=SERIES(,,Sheet1!$B$2:$B$3,1)",
            WPSFAKE_LINKED="10\t20",
        )
        self.assertEqual(data["status"], "reverted", data)
        self.assertEqual(data["read_back_text"], "10\t20")

    def test_an_object_edited_since_the_write_is_left_alone(self):
        data = self.revert("shape", "typed by the user", "OLD", "NEW", "selection-shape-revert")
        self.assertEqual(data["status"], "revert_mismatch")
        self.assertEqual(data["current_text"], "typed by the user")
        data = self.revert("shape", "OLD", "OLD", "NEW", "selection-shape-revert")
        self.assertEqual(data["status"], "unchanged")

    def test_an_object_holding_what_wps_read_back_is_undone_too(self):
        data = self.revert(
            "chart_title", "Q3 tot", "Q3 sales", "Q3 total", "selection-chart-title-revert", read_back="Q3 tot"
        )
        self.assertEqual(data["status"], "reverted", data)
        self.assertEqual(data["read_back_text"], "Q3 sales")

    def test_an_undo_that_does_not_read_back_is_not_saved(self):
        data = self.revert("axis_title", "Mon", "Quarter", "Mon", "selection-axis-title-revert", WPSFAKE_STUCK="1")
        self.assertEqual(data["status"], "revert_read_back_failed")
        self.assertEqual(data["read_back_text"], "Mon")

    def test_another_selected_object_is_not_touched(self):
        params = {
            "original_text": "OLD",
            "written_text": "NEW",
            "original_formula": "",
            "expected_object_name": "Other",
        }
        data = self.obj("shape", "NEW", params, "selection-shape-revert")
        self.assertEqual(data["status"], "selection_changed")

    def test_series_writes_record_the_formula_the_undo_needs(self):
        for action, params in (
            ("selection-series-values-replace", {"values": ["30", "40"], "expected_text": "10\t20"}),
            ("selection-series-values-delete", {"expected_text": "10\t20"}),
        ):
            with self.subTest(action=action):
                data = self.obj("series", "10\t20", params, action, WPSFAKE_FORMULA="=SERIES(,,Sheet1!$B$2:$B$3,1)")
                self.assertEqual(data["status"], "ok", data)
                self.assertEqual(data["before_formula"], "=SERIES(,,Sheet1!$B$2:$B$3,1)")
                revert = open_documents._spreadsheet_object_revert(
                    "series_values", {"object_name": "Chart 1", "selection_text": "10\t20"}, data, "30\t40"
                )
                self.assertEqual(revert["original_formula"], "=SERIES(,,Sheet1!$B$2:$B$3,1)")
                self.assertEqual(revert["revert_action"], "selection-series-values-revert")


if __name__ == "__main__":
    unittest.main()
