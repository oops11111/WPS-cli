"""The text export keeps every character (P9-003): the real scripts against fake WPS objects.

WPS 12.8 wrote the Writer text export in the system code page (P8-008), where characters outside it are already
"?" in the file. The fakes here write the way WPS might: UTF-8 when asked, the code page when the encoding argument
is ignored, or they reject the argument. The code page is the culture's (1252 under pwsh on Linux): "é" fits it,
"✅" does not, the same way "草" fits GBK and "✅" does not.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.test_open_documents_powershell import FAKE_WPS_PRELUDE
from wps_ai_agent_cli import open_documents
from wps_ai_agent_cli.open_document_scripts import _UNICODE_TEXT_FILE

PWSH = os.environ.get("WPS_TEST_PWSH") or shutil.which("pwsh")

_FAKE_TEXT_SAVE = r"""
    public FakeRange Content { get { return new FakeRange(0, State.Text.Length); } }
    static System.Text.Encoding Ansi() {
      return System.Text.Encoding.GetEncoding(System.Globalization.CultureInfo.CurrentCulture.TextInfo.ANSICodePage);
    }
    // Plain text as Word writes it: paragraphs end with CR LF, table cells (CR BEL) become tabs.
    static string Plain() { return State.Text.Replace("\r\a", "\t").Replace("\r", "\r\n"); }
    public void SaveAs2(string p, int fmt) {
      string mode = Environment.GetEnvironmentVariable("WPSFAKE_TXT_PLAIN") ?? "ansi";
      if (mode == "utf16") { File.WriteAllText(p, Plain(), new System.Text.UnicodeEncoding(false, true)); }
      else { File.WriteAllBytes(p, Ansi().GetBytes(Plain())); }
    }
    public void SaveAs2(object p, object fmt, object a3, object a4, object a5, object a6, object a7, object a8,
                        object a9, object a10, object a11, object encoding) {
      string mode = Environment.GetEnvironmentVariable("WPSFAKE_TXT_ENCODING") ?? "honoured";
      if (mode == "rejected") { throw new System.Runtime.InteropServices.COMException("bad argument", unchecked((int)0x800A1066)); }
      if (mode == "honoured" && (int)encoding == 65001) { File.WriteAllText((string)p, Plain(), new System.Text.UTF8Encoding(false)); return; }
      SaveAs2((string)p, (int)fmt);
    }
"""

WRITER_TEXT_PRELUDE = FAKE_WPS_PRELUDE.replace(
    '    public void SaveAs2(string p, int fmt) { File.WriteAllText(p, "<html>" + State.Text + "</html>"); }\n',
    _FAKE_TEXT_SAVE,
)

BOOK_TEXT_PRELUDE = r"""
Add-Type -TypeDefinition @"
using System;
using System.IO;
namespace WpsAgent {
  public static class Book {
    public static string Path = Environment.GetEnvironmentVariable("WPSFAKE_PATH") ?? "";
    // Rows separated by "|", cells by ";".
    public static string[][] Cells() {
      string[] rows = (Environment.GetEnvironmentVariable("WPSFAKE_ROWS") ?? "a;b").Split('|');
      string[][] result = new string[rows.Length][];
      for (int i = 0; i < rows.Length; i++) { result[i] = rows[i].Split(';'); }
      return result;
    }
    public static string Text() {
      var lines = new System.Collections.Generic.List<string>();
      foreach (string[] row in Cells()) { lines.Add(string.Join("\t", row)); }
      return string.Join("\r\n", lines) + "\r\n";
    }
  }
  public class FakeCell { public string Text; }
  public class FakeCells { public FakeCell Item(int r, int c) { return new FakeCell { Text = Book.Cells()[r - 1][c - 1] }; } }
  public class FakeCount { public int Count; }
  public class FakeUsed {
    public FakeCount Rows { get { return new FakeCount { Count = Book.Cells().Length }; } }
    public FakeCount Columns { get { return new FakeCount { Count = Book.Cells()[0].Length }; } }
    public FakeCells Cells { get { return new FakeCells(); } }
  }
  public class FakeSheet { public FakeUsed UsedRange { get { return new FakeUsed(); } } }
  public class FakeWorkbook {
    public bool IsCopy = false;
    public string FullName { get { return Book.Path; } }
    public bool Saved { get { return true; } }
    public FakeSheet ActiveSheet { get { return new FakeSheet(); } }
    public void SaveCopyAs(string p) { File.WriteAllText(p, "xlsx copy"); }
    public void SaveAs(string p, int fmt) {
      string mode = Environment.GetEnvironmentVariable("WPSFAKE_BOOK_TEXT") ?? "unicode";
      if (mode == "unicode" && fmt == 42) { File.WriteAllText(p, Book.Text(), new System.Text.UnicodeEncoding(false, true)); return; }
      if (fmt == 42) { throw new System.Runtime.InteropServices.COMException("no unicode text", unchecked((int)0x800A03EC)); }
      var ansi = System.Text.Encoding.GetEncoding(System.Globalization.CultureInfo.CurrentCulture.TextInfo.ANSICodePage);
      File.WriteAllBytes(p, ansi.GetBytes(Book.Text()));
    }
    public void Close(bool save) { }
  }
  public class FakeWorkbooks {
    public int Count = 1;
    public FakeWorkbook Item(int i) { return new FakeWorkbook(); }
    public FakeWorkbook Open(string p) { return new FakeWorkbook { IsCopy = true }; }
  }
  public class FakeApp {
    public string Name { get { return "Microsoft Excel"; } }
    public bool DisplayAlerts { get; set; }
    public FakeWorkbooks Workbooks { get { return new FakeWorkbooks(); } }
  }
  public static class Running {
    public static object Get(string progId) { return progId == "ket.Application" ? new FakeApp() : null; }
  }
}
"@
"""


def _render_with(prelude):
    return lambda script, values: prelude + open_documents.json.dumps(values).join(script.split("__PARAMS_JSON__"))


@unittest.skipUnless(PWSH, "PowerShell (pwsh) is required to run the text export scripts against fake WPS objects")
class TextExportScriptTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.output = self.dir / "out.txt"
        patcher = patch("wps_ai_agent_cli.powershell_runner.powershell_executable", return_value=PWSH)
        patcher.start()
        self.addCleanup(patcher.stop)

    def writer_export(self, text, **env):
        document = self.dir / "report.docx"
        document.write_bytes(b"docx")
        with (
            patch.dict(os.environ, {"WPSFAKE_PATH": str(document.resolve()), "WPSFAKE_TEXT": text, **env}),
            patch.object(open_documents, "_render", side_effect=_render_with(WRITER_TEXT_PRELUDE)),
        ):
            result = open_documents._run_writer_attached_com(
                "export-text", {"path": str(document.resolve()), "output": str(self.output)}
            )
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["data"]["status"], "ok", result)
        return result["data"]["export_method"]

    def book_export(self, rows, **env):
        book = self.dir / "book.xlsx"
        book.write_bytes(b"xlsx")
        with (
            patch.dict(os.environ, {"WPSFAKE_PATH": str(book.resolve()), "WPSFAKE_ROWS": rows, **env}),
            patch.object(open_documents, "_render", side_effect=_render_with(BOOK_TEXT_PRELUDE)),
        ):
            result = open_documents._run_spreadsheet_attached_com(
                "export-text", {"path": str(book.resolve()), "output": str(self.output)}
            )
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["data"]["status"], "ok", result)
        return result["data"]["export_method"]

    def test_writer_asks_for_utf8_and_keeps_what_wps_wrote(self):
        method = self.writer_export("café ✅ done\r")
        self.assertEqual(method, "SaveAsUtf8Text")
        self.assertEqual(self.output.read_bytes(), "café ✅ done\r\n".encode())
        self.assertEqual(open_documents._text_encoding(self.output), "utf-8")

    def test_a_code_page_file_that_lost_nothing_is_re_encoded_to_utf8(self):
        method = self.writer_export("café done\r", WPSFAKE_TXT_ENCODING="ignored")
        self.assertEqual(method, "SaveAsUtf8Text+transcoded")
        self.assertEqual(self.output.read_bytes(), "café done\r\n".encode("utf-8-sig"))

    def test_characters_the_code_page_lost_are_written_from_the_documents_text(self):
        method = self.writer_export("café ✅ done\r", WPSFAKE_TXT_ENCODING="ignored")
        self.assertEqual(method, "SaveAsUtf8Text+document_text")
        self.assertEqual(self.output.read_bytes().decode("utf-8-sig"), "café ✅ done\r\n")
        self.assertEqual(open_documents._text_encoding(self.output), "utf-8-sig")

    def test_table_cells_line_and_page_breaks_become_plain_text(self):
        self.writer_export("a\r\ab\r\a\rnext ✅\x0bline\x0cpage\r", WPSFAKE_TXT_ENCODING="ignored")
        self.assertEqual(self.output.read_bytes().decode("utf-8-sig"), "a\tb\t\r\nnext ✅\r\nline\r\npage\r\n")

    def test_without_the_encoding_argument_the_unicode_text_format_is_used(self):
        method = self.writer_export("café ✅ done\r", WPSFAKE_TXT_ENCODING="rejected", WPSFAKE_TXT_PLAIN="utf16")
        self.assertEqual(method, "SaveAsUnicodeText")
        self.assertEqual(self.output.read_bytes().decode("utf-16"), "café ✅ done\r\n")

    def test_spreadsheet_unicode_text_is_kept(self):
        method = self.book_export("地区;状态|华北;✅")
        self.assertEqual(method, "SaveCopyAsThenUnicodeText")
        self.assertEqual(open_documents._text_encoding(self.output), "utf-16")

    def test_spreadsheet_windows_text_that_lost_characters_is_rebuilt_from_the_cells(self):
        method = self.book_export("Region;Status|North;✅|South;café", WPSFAKE_BOOK_TEXT="windows")
        self.assertEqual(method, "SaveCopyAsThenWindowsText+document_text")
        self.assertEqual(self.output.read_bytes().decode("utf-8-sig"), "Region\tStatus\r\nNorth\t✅\r\nSouth\tcafé\r\n")

    def test_spreadsheet_windows_text_that_lost_nothing_is_re_encoded(self):
        method = self.book_export("Region;Status|South;café", WPSFAKE_BOOK_TEXT="windows")
        self.assertEqual(method, "SaveCopyAsThenWindowsText+transcoded")
        self.assertEqual(self.output.read_bytes().decode("utf-8-sig"), "Region\tStatus\r\nSouth\tcafé\r\n")


@unittest.skipUnless(PWSH, "PowerShell (pwsh) is required to run the text file helper")
class UnicodeTextFileHelperTests(unittest.TestCase):
    """Complete-WpsUnicodeTextFile on its own: the files WPS might leave, and when it reads the document."""

    def run_helper(self, data, document_text):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.txt"
            path.write_bytes(data)
            literal = document_text.replace("'", "''")
            script = (
                _UNICODE_TEXT_FILE
                + f"\n$script:reads = 0\n$r = Complete-WpsUnicodeTextFile '{path}' {{ $script:reads++; '{literal}' }}\n"
                + "Write-Output ($r + ' ' + $script:reads)\n"
            )
            script_path = Path(tmp) / "helper.ps1"
            script_path.write_text(script, encoding="utf-8-sig")
            completed = subprocess.run(
                [PWSH, "-NoProfile", "-File", str(script_path)],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            return completed.stdout.strip(), path.read_bytes()

    def test_a_file_with_a_byte_order_mark_is_kept_without_reading_the_document(self):
        for data in ("﻿hi".encode("utf-16-le"), "hi ✅".encode("utf-8-sig")):
            with self.subTest(data=data):
                outcome, after = self.run_helper(data, "hi ✅")
                self.assertEqual(outcome, "unicode 0")
                self.assertEqual(after, data)

    def test_utf8_beyond_ascii_is_kept(self):
        outcome, after = self.run_helper("hi ✅".encode(), "hi ✅")
        self.assertEqual(outcome, "unicode 1")
        self.assertEqual(after, "hi ✅".encode())

    def test_plain_ascii_is_kept_unless_the_document_had_characters_it_lost(self):
        kept, after = self.run_helper(b"hi\r\n", "hi\r\n")
        self.assertEqual((kept, after), ("unicode 1", b"hi\r\n"))
        lost, after = self.run_helper(b"hi ?\r\n", "hi ✅\r\n")
        self.assertEqual(lost, "document_text 1")
        self.assertEqual(after, "hi ✅\r\n".encode("utf-8-sig"))


if __name__ == "__main__":
    unittest.main()
