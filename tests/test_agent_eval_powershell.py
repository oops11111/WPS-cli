"""The runner's WPS document script (P7-003), run in pwsh against a fake WPS.

Covers what P7-003 added: selecting a cell range in a workbook and reading its address back, making an untitled
document with text in each component, and closing an untitled document without saving.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wps_ai_agent_cli import open_documents

REPO_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "run_agent_eval", REPO_ROOT / "scripts" / "agent_eval" / "run_agent_eval.py"
)
run_agent_eval = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_agent_eval)

PWSH = os.environ.get("WPS_TEST_PWSH") or shutil.which("pwsh")

FAKE_PRELUDE = r"""
Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
namespace WpsAgent {
  public class FakeDoc {
    public string Kind; public string Name; public string FullName; public bool Saved = true; public bool Closed = false;
    public string Text = "";
    public FakeDoc(string kind, string name, string fullName) { Kind = kind; Name = name; FullName = fullName; }
    // Writer
    public FakeText Content { get { return new FakeText(this); } }
    public void Close(object option) { Closed = true; State.Log.Add("closed " + Name + " " + option); }
    public void Close() { Closed = true; State.Log.Add("closed " + Name + " saved=" + Saved); }
    // Workbook
    public void Activate() { }
    public FakeSheets Worksheets { get { return new FakeSheets(this); } }
    // Presentation
    public FakeSlides Slides { get { return new FakeSlides(this); } }
  }
  public static class State {
    public static string Path = Environment.GetEnvironmentVariable("WPSFAKE_PATH") ?? "";
    public static List<FakeDoc> Docs = Load();
    public static List<string> Log = new List<string>();
    public static string Selected = "A1";
    static List<FakeDoc> Load() {
      var docs = new List<FakeDoc>();
      string kind = Environment.GetEnvironmentVariable("WPSFAKE_KIND") ?? "writer";
      docs.Add(new FakeDoc(kind, System.IO.Path.GetFileName(Path), Path));
      string untitled = Environment.GetEnvironmentVariable("WPSFAKE_UNTITLED") ?? "";
      if (untitled.Length > 0) { var d = new FakeDoc(kind, untitled, untitled); d.Saved = false; docs.Add(d); }
      return docs;
    }
  }
  public class FakeText { FakeDoc D; public FakeText(FakeDoc d) { D = d; } public string Text { get { return D.Text; } set { D.Text = value; D.Saved = false; } } }
  public class FakeRange {
    FakeDoc D; string A;
    public FakeRange(FakeDoc d, string a) { D = d; A = a; }
    public object Value2 { set { D.Text = A + "=" + value; D.Saved = false; } }
    public void Select() { State.Selected = A.Replace("$", ""); }
  }
  public class FakeSheet {
    FakeDoc D; public string Name;
    public FakeSheet(FakeDoc d, string name) { D = d; Name = name; }
    public void Activate() { State.Log.Add("activated " + Name); }
    public FakeRange Range(string a) { return new FakeRange(D, a); }
  }
  public class FakeSheets {
    FakeDoc D; public FakeSheets(FakeDoc d) { D = d; }
    public FakeSheet Item(object key) {
      if (key is int) { return new FakeSheet(D, "Status"); }
      if ((string)key != "Status") { throw new ArgumentException("no such sheet"); }
      return new FakeSheet(D, "Status");
    }
  }
  public class FakeTextRange { FakeDoc D; public FakeTextRange(FakeDoc d) { D = d; } public string Text { get { return D.Text; } set { D.Text = value; D.Saved = false; } } }
  public class FakeTextFrame { FakeDoc D; public FakeTextFrame(FakeDoc d) { D = d; } public FakeTextRange TextRange { get { return new FakeTextRange(D); } } }
  public class FakeShape { FakeDoc D; public FakeShape(FakeDoc d) { D = d; } public FakeTextFrame TextFrame { get { return new FakeTextFrame(D); } } }
  public class FakeShapes { FakeDoc D; public FakeShapes(FakeDoc d) { D = d; } public FakeShape AddTextbox(int o, float l, float t, float w, float h) { return new FakeShape(D); } }
  public class FakeSlide { FakeDoc D; public FakeSlide(FakeDoc d) { D = d; } public FakeShapes Shapes { get { return new FakeShapes(D); } } }
  public class FakeSlides { FakeDoc D; public FakeSlides(FakeDoc d) { D = d; } public FakeSlide Add(int index, int layout) { return new FakeSlide(D); } }
  public class FakeCollection {
    string Kind; string Prefix;
    public FakeCollection(string kind, string prefix) { Kind = kind; Prefix = prefix; }
    List<FakeDoc> Open { get { return State.Docs.FindAll(d => d.Kind == Kind && !d.Closed); } }
    public int Count { get { return Open.Count; } }
    public FakeDoc Item(int i) { return Open[i - 1]; }
    public FakeDoc Add() { var d = new FakeDoc(Kind, Prefix + (State.Docs.Count + 1), Prefix + (State.Docs.Count + 1)); State.Docs.Add(d); return d; }
  }
  public class FakeSelection {
    public string Address(bool r, bool c) { return State.Selected; }
    public FakeSheet Worksheet { get { return new FakeSheet(null, "Status"); } }
  }
  public class FakeWindow { public FakeSelection Selection { get { return new FakeSelection(); } } }
  public class FakeApp {
    public string Name { get { return "WPS Office"; } }
    public string Path { get { return "C:\\Kingsoft\\WPS Office\\office6"; } }
    public FakeCollection Documents { get { return new FakeCollection("writer", "Document"); } }
    public FakeCollection Workbooks { get { return new FakeCollection("spreadsheets", "Book"); } }
    public FakeCollection Presentations { get { return new FakeCollection("presentation", "Presentation"); } }
    public FakeWindow ActiveWindow { get { return new FakeWindow(); } }
  }
  public static class Running {
    public static object Get(string progId) {
      return (progId == "kwps.Application" || progId == "ket.Application" || progId == "kwpp.Application") ? new FakeApp() : null;
    }
  }
}
"@
"""


@unittest.skipUnless(PWSH, "PowerShell (pwsh) is required to run the runner's WPS script against a fake WPS")
class RunnerScriptTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        patcher = patch("wps_ai_agent_cli.powershell_runner.powershell_executable", return_value=PWSH)
        patcher.start()
        self.addCleanup(patcher.stop)

    def action(self, component, fixture, step, env=None, **params):
        path = self.dir / fixture
        path.write_bytes(b"x")

        def render(script, values):
            return FAKE_PRELUDE + open_documents.json.dumps(values).join(script.split("__PARAMS_JSON__"))

        with (
            patch.dict(os.environ, {"WPSFAKE_PATH": str(path.resolve()), "WPSFAKE_KIND": component, **(env or {})}),
            patch.object(open_documents, "_render", side_effect=render),
        ):
            return run_agent_eval.wps_document_action(component, path, step, **params)

    def test_a_cell_range_is_selected_on_the_named_sheet_and_read_back(self):
        payload = self.action("spreadsheets", "status.xlsx", "select", range="C2:C3", sheet="Status")
        self.assertEqual(payload["status"], "ok", payload)
        self.assertEqual(payload["address"], "C2:C3")
        self.assertEqual(payload["sheet"], "Status")

    def test_a_missing_sheet_fails_the_script(self):
        payload = self.action("spreadsheets", "status.xlsx", "select", range="C2", sheet="Other")
        self.assertEqual(payload["status"], "script_failed", payload)

    def test_each_component_makes_an_untitled_document_with_text(self):
        for component, name, prefix in (
            ("writer", "report.docx", "Document"),
            ("spreadsheets", "status.xlsx", "Book"),
            ("presentation", "deck.pptx", "Presentation"),
        ):
            with self.subTest(component=component):
                payload = self.action(component, name, "new_untitled", text="Meeting notes")
                self.assertEqual(payload["status"], "ok", payload)
                self.assertEqual(payload["name"], f"{prefix}2")
                self.assertFalse(payload["saved"])

    def test_only_an_untitled_document_of_that_name_is_closed(self):
        closed = self.action(
            "writer", "report.docx", "close_untitled", {"WPSFAKE_UNTITLED": "Document7"}, name="Document7"
        )
        self.assertEqual(closed["status"], "closed", closed)
        # The fixture has a path on disk, so it is never closed as an untitled document.
        missing = self.action("writer", "report.docx", "close_untitled", name="report.docx")
        self.assertEqual(missing["status"], "not_found", missing)

    def test_a_workbook_is_closed_without_saving(self):
        payload = self.action("spreadsheets", "status.xlsx", "close_discard")
        self.assertEqual(payload["status"], "closed", payload)


if __name__ == "__main__":
    unittest.main()
