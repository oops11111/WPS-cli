"""The in-WPS undo scripts (P7-001), run in pwsh against fake WPS objects.

Each script run is a separate process, so a fake's starting state comes from environment variables: the document as
the failed write left it. The script's JSON output is the only thing a test can see afterwards.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.test_open_documents_powershell import FAKE_WPS_PRELUDE
from wps_ai_agent_cli import open_documents

PWSH = os.environ.get("WPS_TEST_PWSH") or shutil.which("pwsh")

FAKE_DECK_PRELUDE = r"""
Add-Type -TypeDefinition @"
using System;
namespace WpsAgent {
  public static class Deck {
    public static string Path = Environment.GetEnvironmentVariable("WPSFAKE_PATH") ?? "";
    public static string Frame = Environment.GetEnvironmentVariable("WPSFAKE_FRAME") ?? "Status: DRAFT";
    public static int SelStart = int.Parse(Environment.GetEnvironmentVariable("WPSFAKE_START") ?? "9");
    public static int SelLength = int.Parse(Environment.GetEnvironmentVariable("WPSFAKE_LENGTH") ?? "5");
    public static string Shape = Environment.GetEnvironmentVariable("WPSFAKE_SHAPE") ?? "Title 1";
    // "drop": the inverse edit loses its text, the way a WPS build that ignored the assignment would.
    public static string Quirk = Environment.GetEnvironmentVariable("WPSFAKE_QUIRK") ?? "";
    public static int Saves = int.Parse(Environment.GetEnvironmentVariable("WPSFAKE_SAVES") ?? "0");
  }
  public class FakeFont { public string Name = "Arial"; public double Size = 18; public int Bold = 0; public int Italic = 0; public int Underline = 0; }
  public class FakeRange {
    public int S; public int L;
    public FakeRange(int s, int l) { S = s; L = l; }
    public int Start { get { return S; } }
    public int Length { get { return L; } }
    public FakeFont Font { get { return new FakeFont(); } }
    public FakeRange Characters(int start, int length) { return new FakeRange(start, length); }
    public string Text {
      get { return Deck.Frame.Substring(S - 1, L); }
      set {
        if (Deck.Quirk == "drop") { value = ""; }
        Deck.Frame = Deck.Frame.Substring(0, S - 1) + value + Deck.Frame.Substring(S - 1 + L);
        L = value.Length;
      }
    }
  }
  public class FakeTextFrame { public FakeRange TextRange { get { return new FakeRange(1, Deck.Frame.Length); } } }
  public class FakeShape { public string Name { get { return Deck.Shape; } } public FakeTextFrame TextFrame { get { return new FakeTextFrame(); } } }
  public class FakeShapes {
    public FakeShape Item(object key) {
      if (key is string && (string)key != Deck.Shape) { throw new ArgumentException("no such shape"); }
      return new FakeShape();
    }
  }
  public class FakeSlide { public int SlideIndex = 1; public FakeShapes Shapes { get { return new FakeShapes(); } } }
  public class FakeSlides { public FakeSlide Item(int i) { if (i != 1) { throw new ArgumentException("no such slide"); } return new FakeSlide(); } }
  public class FakeShapeRange { public int Count = 1; public FakeShape Item(int i) { return new FakeShape(); } }
  public class FakeSelection {
    public int Type { get { return 3; } }
    public FakeShapeRange ShapeRange { get { return new FakeShapeRange(); } }
    public FakeSlide SlideRange { get { return new FakeSlide(); } }
    public FakeRange TextRange { get { return new FakeRange(Deck.SelStart, Deck.SelLength); } }
  }
  public class FakeWindow { public FakeSelection Selection { get { return new FakeSelection(); } } }
  public class FakeWindows { public int Count = 1; public FakeWindow Item(int i) { return new FakeWindow(); } }
  public class FakePresentation {
    public string FullName { get { return Deck.Path; } }
    public string Name { get { return System.IO.Path.GetFileName(Deck.Path); } }
    public bool Saved { get { return Deck.Saves > 0; } }
    public bool ReadOnly { get { return false; } }
    public FakeWindows Windows { get { return new FakeWindows(); } }
    public FakeSlides Slides { get { return new FakeSlides(); } }
    public void Save() { Deck.Saves++; }
  }
  public class FakePresentations { public int Count = 1; public FakePresentation Item(int i) { return new FakePresentation(); } }
  public class FakeApp {
    public string Name { get { return "Microsoft PowerPoint"; } }
    public string Path { get { return "C:\\Kingsoft\\WPS Office\\office6"; } }
    public FakePresentations Presentations { get { return new FakePresentations(); } }
  }
  public static class Running {
    public static object Get(string progId) { return progId == "kwpp.Application" ? new FakeApp() : null; }
  }
}
"@
"""

FAKE_BOOK_PRELUDE = r"""
Add-Type -TypeDefinition @"
using System;
using System.Collections;
using System.Collections.Generic;
namespace WpsAgent {
  public static class Book {
    public static string Path = Environment.GetEnvironmentVariable("WPSFAKE_PATH") ?? "";
    // One entry per selected cell, as "formula" or "'text" for a text constant.
    public static string[] Cells = (Environment.GetEnvironmentVariable("WPSFAKE_CELLS") ?? "'a|'b").Split('|');
    public static int Saves = int.Parse(Environment.GetEnvironmentVariable("WPSFAKE_SAVES") ?? "0");
  }
  public class FakeCell {
    int I;
    public FakeCell(int i) { I = i; }
    string Raw { get { return Book.Cells[I]; } set { Book.Cells[I] = value; } }
    public bool HasFormula { get { return Raw.StartsWith("="); } }
    public string Formula {
      get { return Raw.StartsWith("'") ? Raw.Substring(1) : Raw; }
      set {
        double number;
        if (value.StartsWith("'") || value.StartsWith("=") || value.Length == 0) { Raw = value; }
        else if (double.TryParse(value, System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out number)) { Raw = value; }
        else { Raw = "'" + value; }
      }
    }
    public object Value2 {
      get {
        if (Raw.StartsWith("'")) { return Raw.Substring(1); }
        if (Raw.Length == 0) { return null; }
        return double.Parse(Raw, System.Globalization.CultureInfo.InvariantCulture);
      }
      set {
        // Like WPS, text that reads as a number is stored as a number.
        string text = value == null ? "" : value.ToString();
        double number;
        if (text.Length == 0) { Raw = ""; }
        else if (double.TryParse(text, System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out number)) { Raw = text.TrimStart('0') == "" ? "0" : text.TrimStart('0'); }
        else { Raw = "'" + text; }
      }
    }
    public string Text { get { return Formula; } }
  }
  public class FakeArea {
    public List<FakeCell> Cells { get { var list = new List<FakeCell>(); for (int i = 0; i < Book.Cells.Length; i++) { list.Add(new FakeCell(i)); } return list; } }
    public object Value2 { set { foreach (FakeCell cell in Cells) { cell.Value2 = value; } } }
    public void ClearContents() { foreach (FakeCell cell in Cells) { cell.Value2 = null; } }
  }
  public class FakeRange { public List<FakeArea> Areas { get { return new List<FakeArea> { new FakeArea() }; } } }
  // The user's selection: A1:An on Sheet1, one area.
  public class FakeSelection {
    public string Address(bool rowAbsolute, bool columnAbsolute) { return (char)36 + "A" + (char)36 + "1:" + (char)36 + "A" + (char)36 + Book.Cells.Length; }
    public List<FakeCell> Cells { get { return new FakeArea().Cells; } }
    public List<FakeArea> Areas { get { return new FakeRange().Areas; } }
    public FakeSheet Worksheet { get { return new FakeSheet(); } }
  }
  public class FakeWindow { public FakeSelection Selection { get { return new FakeSelection(); } } }
  public class FakeWindows { public int Count = 1; public FakeWindow Item(int i) { return new FakeWindow(); } }
  public class FakeSheet {
    public string Name = "Sheet1";
    public FakeRange Range(string address) { // The address ends with the row of the last cell (no dollar signs here: the here-string would expand them).
    if (!address.EndsWith(":" + (char)36 + "A" + (char)36 + Book.Cells.Length)) { throw new ArgumentException("bad address"); } return new FakeRange(); }
  }
  public class FakeSheets { public FakeSheet Item(object key) { if ((string)key != "Sheet1") { throw new ArgumentException("no such sheet"); } return new FakeSheet(); } }
  public class FakeWorkbook {
    public string FullName { get { return Book.Path; } }
    public bool Saved { get { return Book.Saves > 0; } }
    public bool ReadOnly { get { return false; } }
    public FakeSheets Worksheets { get { return new FakeSheets(); } }
    public FakeWindows Windows { get { return new FakeWindows(); } }
    public void Save() { Book.Saves++; }
    // Like the workbook reached through the Running Object Table in P7-007: Close(false) faults, Close() works.
    public void Close() { }
    public void Close(object saveChanges) { throw new System.Runtime.InteropServices.COMException("RPC_E_SERVERFAULT", unchecked((int)0x80010105)); }
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
class UndoScriptTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        patcher = patch("wps_ai_agent_cli.powershell_runner.powershell_executable", return_value=PWSH)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_body(self, prelude, runner, document, env, params, action="selection-revert"):
        with (
            patch.dict(os.environ, {"WPSFAKE_PATH": str(document), **env}),
            patch.object(
                open_documents,
                "_render",
                side_effect=lambda script, values: (
                    prelude + open_documents.json.dumps(values).join(script.split("__PARAMS_JSON__"))
                ),
            ),
        ):
            result = runner(action, {"path": str(document), **params})
        self.assertTrue(result["ok"], result)
        return result["data"]

    # Writer: the fake document is one string; Range(s, e) is a slice of it.
    def writer(self, text, params):
        document = self.dir / "open.docx"
        document.write_bytes(b"docx")
        return self.run_body(
            FAKE_WPS_PRELUDE, open_documents._run_writer_attached_com, document, {"WPSFAKE_TEXT": text}, params
        )

    def test_writer_puts_back_replaced_inserted_and_deleted_text(self):
        for name, text, params, original in (
            (
                "replace",
                "hello APPROVED world",
                {"start": 6, "written_text": "APPROVED", "original_text": "brave"},
                "brave",
            ),
            ("insert", "hello XYZbrave world", {"start": 6, "written_text": "XYZ", "original_text": ""}, ""),
            ("delete", "hello  world", {"start": 6, "written_text": "", "original_text": "brave"}, "brave"),
        ):
            with self.subTest(write=name):
                data = self.writer(text, params)
                self.assertEqual(data["status"], "reverted", data)
                self.assertEqual(data["read_back_text"], original)
                self.assertTrue(data["saved"])

    def test_writer_leaves_text_that_changed_since_the_write(self):
        data = self.writer("hello edited world", {"start": 6, "written_text": "APPROVED", "original_text": "brave"})
        self.assertEqual(data["status"], "revert_mismatch")
        # The text where the write was, as long as the write: it is not what the write left there.
        self.assertEqual(data["current_text"], "edited w")

    # Presentation: the fake shape's whole text is Deck.Frame; TextRange.Characters is 1-based.
    def deck(self, frame, params, **env):
        document = self.dir / "deck.pptx"
        document.write_bytes(b"pptx")
        return self.run_body(
            FAKE_DECK_PRELUDE,
            open_documents._run_presentation_attached_com,
            document,
            {"WPSFAKE_FRAME": frame, **env},
            params,
        )

    def deck_params(self, written, original, expected, restored):
        return {
            "slide_index": 1,
            "shape_name": "Title 1",
            "start": 9,
            "written_text": written,
            "original_text": original,
            "frame_expected": expected,
            "frame_restored": restored,
        }

    def test_presentation_puts_back_replaced_inserted_and_deleted_text(self):
        for name, frame, params in (
            ("replace", "Status: FINAL", self.deck_params("FINAL", "DRAFT", "Status: FINAL", "Status: DRAFT")),
            ("insert", "Status: DRAFT", self.deck_params("DRAFT", "", "Status: DRAFT", "Status: ")),
            ("delete", "Status: ", self.deck_params("", "DRAFT", "Status: ", "Status: DRAFT")),
        ):
            with self.subTest(write=name):
                data = self.deck(frame, params)
                self.assertEqual(data["status"], "reverted", data)
                self.assertEqual(data["read_back_text"], params["frame_restored"])
                self.assertTrue(data["saved"])

    def test_presentation_reports_a_write_that_did_not_stick(self):
        data = self.deck("Status: DRAFT", self.deck_params("FINAL", "DRAFT", "Status: FINAL", "Status: DRAFT"))
        self.assertEqual(data["status"], "unchanged")

    def test_presentation_refuses_a_shape_edited_since_the_write(self):
        params = self.deck_params("FINAL", "DRAFT", "Status: FINAL", "Status: DRAFT")
        data = self.deck("Status: FINAL (edited)", params)
        self.assertEqual(data["status"], "revert_mismatch")
        data = self.deck("Status: FINAL", {**params, "shape_name": "Gone"})
        self.assertEqual(data["status"], "revert_target_missing")

    def test_presentation_does_not_save_an_undo_that_did_not_read_back(self):
        params = self.deck_params("FINAL", "DRAFT", "Status: FINAL", "Status: DRAFT")
        data = self.deck("Status: FINAL", params, WPSFAKE_QUIRK="drop")
        self.assertEqual(data["status"], "revert_read_back_failed")
        self.assertEqual(data["read_back_text"], "Status: ")
        self.assertFalse(data["saved"])

    def test_presentation_writes_record_where_they_wrote(self):
        document = self.dir / "deck.pptx"
        document.write_bytes(b"pptx")
        data = self.run_body(
            FAKE_DECK_PRELUDE,
            open_documents._run_presentation_attached_com,
            document,
            {"WPSFAKE_FRAME": "Status: DRAFT", "WPSFAKE_SAVES": "1"},
            {"text": "FINAL", "expected_text": "DRAFT"},
            action="selection-replace",
        )
        self.assertEqual(data["status"], "ok", data)
        revert = open_documents._presentation_revert(data, "FINAL", "DRAFT")
        self.assertEqual(revert, self.deck_params("FINAL", "DRAFT", "Status: FINAL", "Status: DRAFT"))

    # Spreadsheets: the fake selection is A1:An, one cell per entry of WPSFAKE_CELLS.
    def book(self, cells, params, action="selection-revert", **env):
        document = self.dir / "book.xlsx"
        document.write_bytes(b"xlsx")
        return self.run_body(
            FAKE_BOOK_PRELUDE,
            open_documents._run_spreadsheet_attached_com,
            document,
            {"WPSFAKE_CELLS": "|".join(cells), **env},
            params,
            action=action,
        )

    def test_spreadsheet_writes_record_each_cell_so_the_undo_can_restore_it(self):
        write = {"expected_address": "$A$1:$A$2", "expected_text": "a\t7", "max_cells": 100}
        for action, params, after in (
            ("selection-replace", {**write, "mode": "constant", "text": "NEW"}, ["'NEW", "'NEW"]),
            ("selection-delete", write, ["", ""]),
        ):
            with self.subTest(write=action):
                data = self.book(["'a", "7"], params, action=action, WPSFAKE_SAVES="1")
                self.assertEqual(data["status"], "ok", data)
                revert = open_documents._spreadsheet_revert(data)
                self.assertEqual(
                    revert,
                    {
                        "sheet_name": "Sheet1",
                        "address": "$A$1:$A$2",
                        "before_cells": [
                            {"formula": "a", "text_constant": True},
                            {"formula": "7", "text_constant": False},
                        ],
                        "after_formulas": [cell.lstrip("'") for cell in after],
                    },
                )
                undone = self.book(after, revert)
                self.assertEqual(undone["status"], "reverted", undone)
                self.assertEqual(undone["read_back_formulas"], ["a", "7"])

    def cell_params(self, before, after):
        return {
            "sheet_name": "Sheet1",
            "address": f"$A$1:$A${len(before)}",
            "before_cells": [{"formula": formula, "text_constant": text} for formula, text in before],
            "after_formulas": after,
        }

    def test_spreadsheet_puts_back_text_numbers_formulas_and_blanks(self):
        before = [("label", True), ("007", True), ("42", False), ("=A3*2", False), ("", False)]
        data = self.book(["'NEW"] * 5, self.cell_params(before, ["NEW"] * 5))
        self.assertEqual(data["status"], "reverted", data)
        self.assertEqual(data["read_back_formulas"], ["label", "007", "42", "=A3*2", ""])
        self.assertTrue(data["saved"])

    def test_an_unchanged_workbook_is_closed_without_the_argument_that_faulted(self):
        data = self.book(
            ["'a"], {"component": "spreadsheets", "do_close": True}, action="close-unchanged", WPSFAKE_SAVES="1"
        )
        self.assertEqual(data["status"], "closed", data)

    def test_spreadsheet_leaves_cells_that_changed_since_the_write(self):
        params = self.cell_params([("a", True), ("b", True)], ["NEW", "NEW"])
        data = self.book(["'NEW", "'typed"], params)
        self.assertEqual(data["status"], "revert_mismatch")
        self.assertEqual(data["current_formulas"], ["NEW", "typed"])
        data = self.book(["'a", "'b"], params)
        self.assertEqual(data["status"], "unchanged")
        data = self.book(["'NEW", "'NEW"], {**params, "sheet_name": "Other"})
        self.assertEqual(data["status"], "revert_target_missing")


if __name__ == "__main__":
    unittest.main()
