import unittest
from pathlib import Path
from subprocess import TimeoutExpired
from tempfile import TemporaryDirectory
from unittest.mock import patch

from wps_ai_agent_cli.com_backend import (
    run_conversion_smoke,
    run_spreadsheet_calc_smoke,
    validate_smoke_inputs,
)
from wps_ai_agent_cli.errors import (
    COM_OPERATION_TIMEOUT,
    INPUT_FILE_NOT_FOUND,
    UNSUPPORTED_COMPONENT,
)


class ComBackendTests(unittest.TestCase):
    def test_validate_smoke_inputs_reports_missing_file_and_bad_component(self):
        errors = validate_smoke_inputs(
            component="bad",
            input_path="missing.docx",
            output_path="out.docx",
        )
        codes = {error["code"] for error in errors}

        self.assertIn(UNSUPPORTED_COMPONENT, codes)
        self.assertIn(INPUT_FILE_NOT_FOUND, codes)

    def test_calc_smoke_reports_missing_file_before_com(self):
        result = run_spreadsheet_calc_smoke(
            input_path="missing.xlsx",
            output_path="out.xlsx",
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["errors"][0]["code"], INPUT_FILE_NOT_FOUND)

    def test_conversion_smoke_reports_missing_file_before_com(self):
        result = run_conversion_smoke(
            component="writer",
            input_path="missing.docx",
            output_path="out.pdf",
            output_format="pdf",
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["errors"][0]["code"], INPUT_FILE_NOT_FOUND)

    def test_conversion_smoke_scripts_cover_spreadsheet_and_presentation_pdf(self):
        from tests.test_presentation_ops import write_minimal_pptx

        cases = (
            ("spreadsheets", "book.xlsx", "Workbooks.Open", "ExportAsFixedFormat(0,"),
            ("presentation", "deck.pptx", "Presentations.Open", "ExportAsFixedFormat($params.output_path, 2)"),
        )
        for component, filename, open_marker, export_marker in cases:
            with self.subTest(component=component), TemporaryDirectory() as tmp:
                source = Path(tmp) / filename
                if component == "presentation":
                    write_minimal_pptx(source, ["convert smoke"])
                else:
                    source.write_bytes(b"placeholder")
                before = source.read_bytes()
                output = Path(tmp) / "out.pdf"
                captured: dict[str, str] = {}

                def fake_run(script, timeout_seconds=120, failure_data=None):
                    captured["script"] = script
                    captured["component"] = (failure_data or {}).get("component")
                    output.write_bytes(b"%PDF-1.4")
                    return {
                        "ok": True,
                        "component": component,
                        "direction": f"{component}_to_pdf",
                        "output_path": str(output),
                        "output_bytes": output.stat().st_size,
                    }, None

                capabilities = {
                    "components": {
                        component: {"selected_prog_id": f"fake.{component}"},
                    }
                }
                with (
                    patch("wps_ai_agent_cli.com_backend.probe_wps_capabilities", return_value=capabilities),
                    patch("wps_ai_agent_cli.com_backend.run_powershell_script", side_effect=fake_run),
                ):
                    result = run_conversion_smoke(component, str(source), str(output), "pdf")
                self.assertTrue(result["ok"], result)
                self.assertEqual(captured["component"], component)
                self.assertIn(open_marker, captured["script"])
                self.assertIn(export_marker, captured["script"])
                self.assertIn("'Documents', 'Workbooks', 'Presentations'", captured["script"])
                self.assertIn("$app.Quit()", captured["script"])
                self.assertIn("$document.Close()", captured["script"])
                self.assertEqual(source.read_bytes(), before)

    def test_conversion_smoke_rejects_non_pdf_format(self):
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "book.xlsx"
            source.write_bytes(b"placeholder")
            result = run_conversion_smoke("spreadsheets", str(source), str(Path(tmp) / "out.pdf"), "png")
        self.assertFalse(result["ok"])
        self.assertEqual(result["errors"][0]["code"], UNSUPPORTED_COMPONENT)

    def test_calc_smoke_rejects_same_input_and_output(self):
        with TemporaryDirectory() as tmp:
            workbook = Path(tmp) / "input.xlsx"
            workbook.write_bytes(b"placeholder")

            result = run_spreadsheet_calc_smoke(
                input_path=str(workbook),
                output_path=str(workbook),
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["errors"][0]["code"], "COM_OPERATION_FAILED")

    def test_calc_smoke_reports_subprocess_timeout_as_structured_error(self):
        with TemporaryDirectory() as tmp:
            workbook = Path(tmp) / "input.xlsx"
            workbook.write_bytes(b"placeholder")
            output = Path(tmp) / "output.xlsx"
            capabilities = {
                "components": {
                    "spreadsheets": {
                        "selected_prog_id": "ket.Application",
                    }
                }
            }

            with (
                patch("wps_ai_agent_cli.com_backend.probe_wps_capabilities", return_value=capabilities),
                patch("wps_ai_agent_cli.com_backend.subprocess.run", side_effect=TimeoutExpired("pwsh", 3)),
            ):
                result = run_spreadsheet_calc_smoke(
                    input_path=str(workbook),
                    output_path=str(output),
                    timeout_seconds=3,
                )

        self.assertFalse(result["ok"])
        self.assertEqual(result["errors"][0]["code"], COM_OPERATION_TIMEOUT)
        self.assertEqual(result["data"]["timeout_seconds"], 3)


if __name__ == "__main__":
    unittest.main()
