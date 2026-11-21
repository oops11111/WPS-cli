import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("flowpreflight", ROOT / "scripts/qualified_flow_preflight.py")
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class QualifiedFlowPreflightTests(unittest.TestCase):
    def records(self):
        old = {
            "print_context": {"cssom": {"links": []}},
            "elements": [{"tag": "p", "style": {"line-height": "22px"}, "box": {"x": 8}}],
        }
        new = copy.deepcopy(old)
        new["elements"][0]["style"].update({key: "auto" for key in m.BREAKS})
        return old, new

    def test_only_four_new_properties_are_permitted(self):
        old, new = self.records()
        self.assertTrue(m.core_equal(old, new, "A-contract-docx", Path("out")))
        for key, value in (("line-height", "23px"), ("fifth-property", "auto"), ("break-after", "")):
            changed = copy.deepcopy(new)
            changed["elements"][0]["style"][key] = value
            self.assertFalse(m.core_equal(old, changed, "A-contract-docx", Path("out")))
        del new["elements"][0]["style"]["break-after"]
        self.assertFalse(m.core_equal(old, new, "A-contract-docx", Path("out")))

    def test_known_link_relocation_preserves_resource_and_error(self):
        old, new = self.records()
        old["print_context"]["cssom"]["links"] = [
            {
                "href": "file:///C:/old/artifacts/natural-merged-rows-20261121/A-report-docx/input/print.css",
                "has_sheet": True,
            }
        ]
        out = ROOT / "out"
        new["print_context"]["cssom"]["links"] = [
            {"href": (out / "A-report-docx/input/print.css").as_uri(), "has_sheet": True}
        ]
        self.assertTrue(m.core_equal(old, new, "A-report-docx", out))
        new["print_context"]["cssom"]["links"][0]["has_sheet"] = False
        self.assertFalse(m.core_equal(old, new, "A-report-docx", out))
        new["print_context"]["cssom"]["links"][0]["href"] = "https://external.invalid/print.css"
        with self.assertRaises(ValueError):
            m.core_equal(old, new, "A-report-docx", out)

    def test_already_attempted_capture_is_rejected_without_source_load(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / "browser-attempt.json").write_text("{}", encoding="utf-8")
            with patch.object(m.html_styles, "load") as load:
                with self.assertRaises(ValueError):
                    m.capture_once(out)
                load.assert_not_called()

    def test_existing_source_reference_rgb_self_control(self):
        path = m.BASE / "A-report-docx/browser.pdf"
        self.assertTrue(m.source_pixels_equal(path, path))
