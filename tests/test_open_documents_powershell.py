import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wps_ai_agent_cli import open_documents

PWSH = os.environ.get("WPS_TEST_PWSH") or shutil.which("pwsh")

FAKE_WPS_PRELUDE = r"""
Add-Type -TypeDefinition @"
using System;
using System.IO;
namespace WpsAgent {
  public static class State {
    public static string Mode = Environment.GetEnvironmentVariable("WPSFAKE_MODE") ?? "running";
    public static string Path = Environment.GetEnvironmentVariable("WPSFAKE_PATH") ?? "";
    public static bool Saved = (Environment.GetEnvironmentVariable("WPSFAKE_SAVED") ?? "1") == "1";
    public static bool ReadOnly = (Environment.GetEnvironmentVariable("WPSFAKE_READONLY") ?? "0") == "1";
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
    public bool ReadOnly { get { return State.ReadOnly; } }
    public FakeWindow ActiveWindow { get { return new FakeWindow(); } }
    public FakeRange Range(int s, int e) { return new FakeRange(s, e); }
    public void Save() { State.SaveCalls++; State.Saved = true; }
    public void SaveAs2(string p, int fmt) { File.WriteAllText(p, "<html>" + State.Text + "</html>"); }
    public void SaveAs(string p, int fmt) { SaveAs2(p, fmt); }
    public void Close(bool save) { if (!IsCopy) { File.WriteAllText(State.Path + ".closed", save ? "saved" : "discarded"); } }
  }
  public class FakeDocs {
    public int Count { get { return 1; } }
    public FakeDoc Item(int i) { return new FakeDoc(); }
    public FakeDoc Add(string template) { var d = new FakeDoc(); d.IsCopy = true; return d; }
  }
  public class FakeApp {
    public string AppName = "WPS Office";
    public string Name { get { return AppName; } }
    public string Version { get { return "12.1"; } }
    public FakeDocs Documents { get { return new FakeDocs(); } }
    public FakeDoc ActiveDocument { get { return new FakeDoc(); } }
    public object Workbooks { get { return null; } }
  }
  public class FakeRotDoc {
    public FakeApp Application { get { var app = new FakeApp(); app.AppName = Environment.GetEnvironmentVariable("WPSFAKE_ROT_APP") ?? "WPS Office"; return app; } }
  }
  // Stands in for the Running Object Table and the process list (P6-003).
  public static class Rot {
    public static object[] Find(string[] extensions) {
      string registered = Environment.GetEnvironmentVariable("WPSFAKE_ROT") ?? "";
      foreach (string extension in extensions) {
        if (registered.Length > 0 && registered.EndsWith(extension, StringComparison.OrdinalIgnoreCase)) {
          return new object[] { new FakeRotDoc() };
        }
      }
      return new object[0];
    }
    public static int WindowedProcessCount(string name) {
      return name == (Environment.GetEnvironmentVariable("WPSFAKE_WINDOWED") ?? "") ? 1 : 0;
    }
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
"""


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
            patch.object(
                open_documents,
                "_render",
                side_effect=lambda script, params: (
                    FAKE_WPS_PRELUDE + open_documents.json.dumps(params).join(script.split("__PARAMS_JSON__"))
                ),
            ),
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

    def test_an_application_reached_through_a_registered_document_is_used(self):
        # A WPS started by opening a file registers no application object, only the document (P5-011).
        with patch.dict(os.environ, {"WPSFAKE_MODE": "none", "WPSFAKE_ROT": str(self.document)}):
            listing = open_documents._run_open_documents_com(["writer"])
            result = self.attached("selection-read")
        instances = listing["data"]["instances"]
        instances = instances if isinstance(instances, list) else [instances]
        self.assertEqual(instances[0]["attached_via"], "running_object_table")
        self.assertEqual(result["data"]["selection_text"], "brave")

    def test_a_registered_document_of_another_office_suite_is_ignored(self):
        env = {"WPSFAKE_MODE": "none", "WPSFAKE_ROT": str(self.document), "WPSFAKE_ROT_APP": "Microsoft Word"}
        with patch.dict(os.environ, env):
            result = self.attached("selection-read")
        self.assertEqual(result["data"]["status"], "no_instance")

    def test_a_wps_window_without_automation_is_not_automatable(self):
        with patch.dict(os.environ, {"WPSFAKE_MODE": "none", "WPSFAKE_WINDOWED": "wps"}):
            result = self.attached("selection-read")
            listing = open_documents._run_open_documents_com(["writer", "spreadsheets"])
            ok, data, errors = open_documents.list_open_documents("writer")
        self.assertEqual(result["data"]["status"], "not_automatable")
        unreachable = listing["data"]["not_automatable"]
        self.assertEqual(unreachable if isinstance(unreachable, list) else [unreachable], ["writer"])
        self.assertFalse(ok)
        self.assertEqual([error["code"] for error in errors], ["WPS_INSTANCE_NOT_AUTOMATABLE"])
        self.assertIn("/Automation", errors[0]["message"])
        self.assertEqual(data["not_automatable"], ["writer"])

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
        result = self.attached(
            "selection-replace", text="bold", expected_start=6, expected_end=11, expected_text="brave"
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["data"]["status"], "ok")
        self.assertEqual(result["data"]["read_back_text"], "bold")

    def test_replace_refuses_unsaved_document_and_changed_selection(self):
        with patch.dict(os.environ, {"WPSFAKE_SAVED": "0"}):
            unsaved = self.attached(
                "selection-replace", text="x", expected_start=6, expected_end=11, expected_text="brave"
            )
        self.assertEqual(unsaved["data"]["status"], "unsaved")

        with patch.dict(os.environ, {"WPSFAKE_READONLY": "1"}):
            readonly = self.attached(
                "selection-replace", text="x", expected_start=6, expected_end=11, expected_text="brave"
            )
        self.assertEqual(readonly["data"]["status"], "read_only")

        changed = self.attached("selection-replace", text="x", expected_start=6, expected_end=11, expected_text="BRAVE")
        self.assertEqual(changed["data"]["status"], "selection_changed")

    def test_close_unchanged_closes_a_saved_document_without_saving(self):
        result = self.attached("close-unchanged", component="writer", do_close=True)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["data"]["status"], "closed")
        self.assertEqual(Path(str(self.document) + ".closed").read_text(encoding="utf-8"), "discarded")

    def test_close_unchanged_never_closes_a_document_with_unsaved_changes(self):
        with patch.dict(os.environ, {"WPSFAKE_SAVED": "0"}):
            result = self.attached("close-unchanged", component="writer", do_close=True)
        self.assertEqual(result["data"]["status"], "unsaved")
        self.assertFalse(Path(str(self.document) + ".closed").exists())

    def test_close_unchanged_only_reports_when_asked_not_to_close(self):
        result = self.attached("close-unchanged", component="writer", do_close=False)
        self.assertEqual(result["data"]["status"], "open")
        self.assertFalse(Path(str(self.document) + ".closed").exists())

    def test_close_unchanged_reports_a_document_that_is_not_open(self):
        other = self.dir / "other.docx"
        result = open_documents._run_writer_attached_com(
            "close-unchanged", {"path": str(other), "component": "writer", "do_close": True}
        )
        self.assertEqual(result["data"]["status"], "not_open")

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

    def test_export_copies_a_read_only_saved_document(self):
        output = self.dir / "readonly.html"
        before = self.document.read_bytes()
        with patch.dict(os.environ, {"WPSFAKE_READONLY": "1"}):
            result = self.attached("export-html", output=str(output))
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["data"]["status"], "ok")
        self.assertEqual(result["data"]["export_method"], "SaveAs2")
        self.assertTrue(result["data"]["source_still_open"])
        self.assertEqual(output.read_text(encoding="utf-8"), "<html>hello brave world</html>")
        self.assertEqual(self.document.read_bytes(), before)


@unittest.skipUnless(PWSH, "PowerShell (pwsh) is required to compile the attach snippet")
class AttachSnippetTests(unittest.TestCase):
    """The real snippet, without the fake COM prelude: it must compile everywhere and attach to nothing here."""

    def test_snippet_compiles_and_the_rot_lookup_finds_nothing_off_windows(self):
        from wps_ai_agent_cli.wps_script_snippets import ATTACH_RUNNING_INSTANCE

        script = (
            "$ErrorActionPreference = 'Stop'\n"
            + ATTACH_RUNNING_INSTANCE
            + """
# Running.Get needs ole32 and only runs on Windows; the ROT lookup must degrade to nothing elsewhere.
[pscustomobject]@{
  rot = @([WpsAgent.Rot]::Find([string[]]@('.docx'))).Count
  missing = (Get-WpsMissingStatus @('ket.Application'))
  wps_by_name = (Test-WpsApplication ([pscustomobject]@{ Name = 'WPS Office'; Path = 'C:\\x' }))
  wps_by_chinese_name = (Test-WpsApplication ([pscustomobject]@{ Name = ([string][char]0x91d1 + [char]0x5c71); Path = 'C:\\x' }))
  word = (Test-WpsApplication ([pscustomobject]@{ Name = 'Microsoft Word'; Path = 'C:\\Program Files\\Microsoft Office\\root\\Office16' }))
  wps_named_word = (Test-WpsApplication ([pscustomobject]@{ Name = 'Microsoft Word'; Path = 'D:\\Apps\\Suite\\12.8.2.18913\\office6' }))
} | ConvertTo-Json -Compress
"""
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "attach.ps1"
            path.write_text(script, encoding="utf-8")
            completed = subprocess.run(
                [PWSH, "-NoProfile", "-File", str(path)], capture_output=True, text=True, timeout=120, check=False
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(
            result,
            {
                "rot": 0,
                "missing": "no_instance",
                "wps_by_name": True,
                "wps_by_chinese_name": True,
                "word": False,
                "wps_named_word": True,
            },
        )


@unittest.skipUnless(PWSH, "PowerShell (pwsh) is required to execute the cell text matcher")
class CellTextMatchTests(unittest.TestCase):
    def test_powershell_matcher_agrees_with_the_python_matcher(self):
        import re
        import subprocess

        body = open_documents._SPREADSHEET_SELECTION_REPLACE_BODY
        function = re.search(r"  function Test-CellTextMatch.*?\n  }\n", body, re.S).group(0)
        cases = [
            ("x", "x"),
            ("123", "00123"),
            ("1", "1.0"),
            ("12", "13"),
            ("abc", "abd"),
            ("1,234", "1234"),
            ("7", "+7"),
        ]
        calls = "\n".join(f"Write-Output (Test-CellTextMatch '{actual}' '{expected}')" for actual, expected in cases)
        completed = subprocess.run(
            [PWSH, "-NoProfile", "-Command", function + "\n" + calls],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            [line == "True" for line in completed.stdout.split()],
            [open_documents._cell_text_matches(actual, expected) for actual, expected in cases],
        )


if __name__ == "__main__":
    unittest.main()
