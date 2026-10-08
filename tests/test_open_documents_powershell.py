import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wps_ai_agent_cli import open_documents


PWSH = os.environ.get("WPS_TEST_PWSH") or shutil.which("pwsh")

FAKE_WPS_PRELUDE = r'''
Add-Type -TypeDefinition @"
using System;
using System.IO;
namespace WpsAgent {
  public static class State {
    public static string Mode = Environment.GetEnvironmentVariable("WPSFAKE_MODE") ?? "running";
    public static string Path = Environment.GetEnvironmentVariable("WPSFAKE_PATH") ?? "";
    public static bool Saved = (Environment.GetEnvironmentVariable("WPSFAKE_SAVED") ?? "1") == "1";
    public static string Text = Environment.GetEnvironmentVariable("WPSFAKE_TEXT") ?? "hello brave world";
    public static int SelStart = int.Parse(Environment.GetEnvironmentVariable("WPSFAKE_START") ?? "6");
    public static int SelEnd = int.Parse(Environment.GetEnvironmentVariable("WPSFAKE_END") ?? "11");
    public static int SaveCalls = 0;
  }
  public class FakeRange {
    public int S; public int E;
    public FakeRange(int s, int e) { S = s; E = e; }
    public int Start { get { return S; } }
    public FakeParas Paragraphs { get { return new FakeParas(); } }
    public string Text {
      get { return State.Text.Substring(S, E - S); }
      set { State.Text = State.Text.Substring(0, S) + value + State.Text.Substring(E); }
    }
  }
  public class FakePara { public FakeRange Range { get { return new FakeRange(0, 0); } } }
  public class FakeParas {
    public int Count { get { return 2; } }
    public FakePara Item(int i) { return new FakePara(); }
  }
  public class FakeSel {
    public int Start { get { return State.SelStart; } }
    public int End { get { return State.SelEnd; } }
    public string Text { get { return State.Text.Substring(State.SelStart, State.SelEnd - State.SelStart); } }
    public FakeParas Paragraphs { get { return new FakeParas(); } }
    public int Information(int kind) { return 2; }
  }
  public class FakeWindow { public FakeSel Selection { get { return new FakeSel(); } } }
  public class FakeDoc {
    public bool IsCopy = false;
    public string Name { get { return System.IO.Path.GetFileName(State.Path); } }
    public string FullName { get { return State.Path; } }
    public bool Saved { get { return State.Saved; } }
    public bool ReadOnly { get { return false; } }
    public FakeWindow ActiveWindow { get { return new FakeWindow(); } }
    public FakeRange Range(int s, int e) { return new FakeRange(s, e); }
    public void Save() { State.SaveCalls++; State.Saved = true; }
    public void SaveAs2(string p, int fmt) { File.WriteAllText(p, "<html>" + State.Text + "</html>"); }
    public void SaveAs(string p, int fmt) { SaveAs2(p, fmt); }
    public void Close(bool save) { }
  }
  public class FakeDocs {
    public int Count { get { return 1; } }
    public FakeDoc Item(int i) { return new FakeDoc(); }
    public FakeDoc Add(string template) { var d = new FakeDoc(); d.IsCopy = true; return d; }
  }
  public class FakeApp {
    public string Version { get { return "12.1"; } }
    public FakeDocs Documents { get { return new FakeDocs(); } }
    public FakeDoc ActiveDocument { get { return new FakeDoc(); } }
    public object Workbooks { get { return null; } }
  }
  public static class Running {
    public static object Get(string progId) {
      if (State.Mode == "none") { return null; }
      if (progId == "kwps.Application") { return new FakeApp(); }
      return null;
    }
  }
}
"@
'''


@unittest.skipUnless(PWSH, "PowerShell (pwsh) is required to execute the generated scripts against a fake COM object")
class GeneratedScriptBehaviourTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.document = self.dir / "open.docx"
        self.document.write_bytes(b"docx")
        env = patch.dict(os.environ, {"WPSFAKE_PATH": str(self.document)})
        env.start()
        self.addCleanup(env.stop)
        for patcher in (
            patch("wps_ai_agent_cli.powershell_runner.powershell_executable", return_value=PWSH),
            patch.object(open_documents, "_render", side_effect=lambda script, params: FAKE_WPS_PRELUDE + open_documents.json.dumps(params).join(script.split("__PARAMS_JSON__"))),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def attached(self, action, **params):
        return open_documents._run_writer_attached_com(action, {"path": str(self.document), **params})

    def test_list_script_returns_documents_for_running_component_only(self):
        result = open_documents._run_open_documents_com(["writer", "spreadsheets"])
        self.assertTrue(result["ok"], result)
        instances = result["data"]["instances"]
        instances = instances if isinstance(instances, list) else [instances]
        self.assertEqual([item["component"] for item in instances], ["writer"])
        documents = instances[0]["documents"]
        documents = documents if isinstance(documents, list) else [documents]
        self.assertEqual(documents[0]["full_name"], str(self.document))
        self.assertTrue(documents[0]["saved"])
        self.assertTrue(documents[0]["active"])

    def test_no_instance_is_a_status_not_a_failure(self):
        with patch.dict(os.environ, {"WPSFAKE_MODE": "none"}):
            result = self.attached("selection-read")
            listing = open_documents._run_open_documents_com(["writer"])
        self.assertEqual(result["data"]["status"], "no_instance")
        self.assertTrue(listing["ok"], listing)

    def test_document_matching_is_by_path_not_active_window(self):
        other = self.dir / "other.docx"
        result = open_documents._run_writer_attached_com("selection-read", {"path": str(other)})
        self.assertEqual(result["data"]["status"], "not_open")

    def test_selection_read_reports_range_text_and_paragraph(self):
        result = self.attached("selection-read")
        self.assertTrue(result["ok"], result)
        data = result["data"]
        self.assertEqual((data["status"], data["start"], data["end"], data["selection_text"]), ("ok", 6, 11, "brave"))
        self.assertEqual(data["paragraph_index"], 1)
        self.assertEqual(data["page_number"], 2)

    def test_replace_edits_by_range_saves_and_reads_back(self):
        result = self.attached("selection-replace", text="bold", expected_start=6, expected_end=11, expected_text="brave")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["data"]["status"], "ok")
        self.assertEqual(result["data"]["read_back_text"], "bold")

    def test_replace_refuses_unsaved_document_and_changed_selection(self):
        with patch.dict(os.environ, {"WPSFAKE_SAVED": "0"}):
            unsaved = self.attached("selection-replace", text="x", expected_start=6, expected_end=11, expected_text="brave")
        self.assertEqual(unsaved["data"]["status"], "unsaved")

        changed = self.attached("selection-replace", text="x", expected_start=6, expected_end=11, expected_text="BRAVE")
        self.assertEqual(changed["data"]["status"], "selection_changed")

    def test_export_saves_a_copy_and_leaves_source_open(self):
        output = self.dir / "out.html"
        result = self.attached("export-html", output=str(output))
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["data"]["status"], "ok")
        self.assertTrue(result["data"]["source_still_open"])
        self.assertEqual(output.read_text(encoding="utf-8"), "<html>hello brave world</html>")

        with patch.dict(os.environ, {"WPSFAKE_SAVED": "0"}):
            unsaved = self.attached("export-html", output=str(self.dir / "never.html"))
        self.assertEqual(unsaved["data"]["status"], "unsaved")
        self.assertFalse((self.dir / "never.html").exists())


if __name__ == "__main__":
    unittest.main()
