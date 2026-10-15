"""Presentation selection replace, run against a fake WPS Presentation in pwsh (P6-008 rerun).

On WPS 12.8 the selection does not stay on the new text after TextRange.Text is assigned, so reading the
selection back reported other text and every replace ended in VALIDATION_FAILED. The fake reproduces that:
after the assignment its selection covers the whole shape text.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wps_ai_agent_cli import open_documents

PWSH = os.environ.get("WPS_TEST_PWSH") or shutil.which("pwsh")

FAKE_PRESENTATION_PRELUDE = r"""
Add-Type -TypeDefinition @"
using System;
namespace WpsAgent {
  public static class Deck {
    public static string Path = Environment.GetEnvironmentVariable("WPSFAKE_PATH") ?? "";
    public static string Frame = "Status: DRAFT";
    public static int SelStart = 9;
    public static int SelLength = 5;
    public static bool Assigned = false;
    public static bool SelectionFollowsText = (Environment.GetEnvironmentVariable("WPSFAKE_FOLLOWS") ?? "0") == "1";
    public static int Saves = 0;
  }
  public class FakeFont { public string Name = "Arial"; public double Size = 18; public int Bold = 0; public int Italic = 0; public int Underline = 0; }
  public class FakeRange {
    public int S; public int L;
    public FakeRange(int s, int l) { S = s; L = l; }
    public int Start { get { return S; } }
    public int Length { get { return L; } }
    public FakeFont Font { get { return new FakeFont(); } }
    public string Text {
      get { return Deck.Frame.Substring(S - 1, L); }
      set {
        Deck.Frame = Deck.Frame.Substring(0, S - 1) + value + Deck.Frame.Substring(S - 1 + L);
        L = value.Length;
        Deck.Assigned = true;
      }
    }
  }
  public class FakeTextFrame { public FakeRange TextRange { get { return new FakeRange(1, Deck.Frame.Length); } } }
  public class FakeShape { public string Name = "TextBox 2"; public FakeTextFrame TextFrame { get { return new FakeTextFrame(); } } }
  public class FakeShapeRange { public int Count = 1; public FakeShape Item(int i) { return new FakeShape(); } }
  public class FakeSelection {
    public int Type { get { return 3; } }
    public FakeShapeRange ShapeRange { get { return new FakeShapeRange(); } }
    public FakeRange TextRange {
      get {
        // WPS 12.8: once the text is assigned, the selection no longer covers just the new text.
        if (Deck.Assigned && !Deck.SelectionFollowsText) { return new FakeRange(1, Deck.Frame.Length); }
        return new FakeRange(Deck.SelStart, Deck.Assigned ? Deck.Frame.Length - Deck.SelStart + 1 : Deck.SelLength);
      }
    }
  }
  public class FakeWindow { public FakeSelection Selection { get { return new FakeSelection(); } } }
  public class FakeWindows { public int Count = 1; public FakeWindow Item(int i) { return new FakeWindow(); } }
  public class FakePresentation {
    public string FullName { get { return Deck.Path; } }
    public string Name { get { return System.IO.Path.GetFileName(Deck.Path); } }
    public bool Saved { get { return true; } }
    public bool ReadOnly { get { return false; } }
    public FakeWindows Windows { get { return new FakeWindows(); } }
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


@unittest.skipUnless(PWSH, "PowerShell (pwsh) is required to run the replace script against a fake Presentation")
class PresentationSelectionReplaceScriptTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.deck = Path(tmp.name) / "deck.pptx"
        self.deck.write_bytes(b"pptx")
        for patcher in (
            patch.dict(os.environ, {"WPSFAKE_PATH": str(self.deck)}),
            patch("wps_ai_agent_cli.powershell_runner.powershell_executable", return_value=PWSH),
            patch.object(
                open_documents,
                "_render",
                side_effect=lambda script, params: (
                    FAKE_PRESENTATION_PRELUDE + open_documents.json.dumps(params).join(script.split("__PARAMS_JSON__"))
                ),
            ),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def replace(self):
        return open_documents._run_presentation_attached_com(
            "selection-replace", {"path": str(self.deck), "text": "FINAL", "expected_text": "DRAFT"}
        )

    def test_the_replacement_is_read_back_from_the_shape_when_the_selection_moves(self):
        result = self.replace()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["data"]["status"], "ok", result)
        self.assertEqual(result["data"]["read_back_text"], "FINAL")
        self.assertTrue(result["data"]["read_back_from_shape"])

    def test_a_shape_whose_other_text_changed_does_not_read_back_as_the_replacement(self):
        # If anything else in the shape changed, the read-back is the whole shape text, which fails validation.
        prelude_patch = FAKE_PRESENTATION_PRELUDE.replace(
            "Deck.Frame = Deck.Frame.Substring(0, S - 1) + value + Deck.Frame.Substring(S - 1 + L);",
            'Deck.Frame = "State: " + value;',
        )
        with patch.object(
            open_documents,
            "_render",
            side_effect=lambda script, params: (
                prelude_patch + open_documents.json.dumps(params).join(script.split("__PARAMS_JSON__"))
            ),
        ):
            result = self.replace()
        self.assertEqual(result["data"]["read_back_text"], "State: FINAL")


if __name__ == "__main__":
    unittest.main()
