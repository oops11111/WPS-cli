import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wps_ai_agent_cli import com_backend, presentation_ops, spreadsheet_ops, writer_ops

CAPABILITIES = {
    "components": {
        "writer": {"selected_prog_id": "kwps.Application"},
        "spreadsheets": {"selected_prog_id": "ket.Application"},
        "presentation": {"selected_prog_id": "kwpp.Application"},
    }
}


class FakeCompleted:
    returncode = 0
    stdout = "{}"
    stderr = ""


def capture_scripts(module, call):
    scripts = []

    def fake_run(command, **kwargs):
        scripts.append(Path(command[-1]).read_text(encoding="utf-8-sig"))
        return FakeCompleted()

    with patch.object(module, "probe_wps_capabilities", return_value=CAPABILITIES), \
            patch("subprocess.run", side_effect=fake_run):
        try:
            call()
        except Exception:
            pass
    return scripts


class QuitGuardTests(unittest.TestCase):
    def test_every_generated_script_quits_only_when_wps_is_idle(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "input.docx"
            src.write_bytes(b"x")
            out = Path(tmp) / "out"
            p = str(src)
            cases = [
                (writer_ops, lambda: writer_ops._run_writer_replace_com(p, "a", "b")),
                (writer_ops, lambda: writer_ops._run_writer_bookmark_fill_com(p, "n", "v", "old")),
                (writer_ops, lambda: writer_ops._run_writer_table_write_com(p, 1, 1, 1, "t")),
                (presentation_ops, lambda: presentation_ops._run_presentation_replace_com(p, "a", "b")),
                (spreadsheet_ops, lambda: spreadsheet_ops._run_spreadsheet_rename_sheet_com(p, "a", "b")),
                (spreadsheet_ops, lambda: spreadsheet_ops._run_spreadsheet_create_sheet_com(p, "n", 1)),
                (spreadsheet_ops, lambda: spreadsheet_ops._run_spreadsheet_visibility_com(p, "n", True)),
                (spreadsheet_ops, lambda: spreadsheet_ops._run_spreadsheet_delete_sheet_com(p, "n")),
                (spreadsheet_ops, lambda: spreadsheet_ops._run_spreadsheet_copy_sheet_com(p, "a", "b", 1)),
                (spreadsheet_ops, lambda: spreadsheet_ops._run_spreadsheet_tab_color_com(p, "n", "FF0000")),
                (spreadsheet_ops, lambda: spreadsheet_ops._run_spreadsheet_write_com(p, None, "A1", [[1]])),
                (spreadsheet_ops, lambda: spreadsheet_ops._run_spreadsheet_formula_write_com(p, None, "A1", [["=1"]])),
                (com_backend, lambda: com_backend.run_com_smoke("writer", p, str(out / "a.docx"))),
                (com_backend, lambda: com_backend.run_conversion_smoke("writer", p, str(out / "a.pdf"), "pdf")),
                (com_backend, lambda: com_backend.run_spreadsheet_calc_smoke(p, str(out / "a.xlsx"))),
            ]
            with patch.object(com_backend, "_load_win32com", return_value=None):
                for module, call in cases:
                    scripts = capture_scripts(module, call)
                    self.assertEqual(len(scripts), 1, call)
                    script = scripts[0]
                    self.assertIn("$app.Quit()", script)
                    self.assertEqual(
                        script.count("$app.Quit()"),
                        script.count("if ($wpsIdle) { $app.Quit() }"),
                        "unguarded Quit in script",
                    )


if __name__ == "__main__":
    unittest.main()
