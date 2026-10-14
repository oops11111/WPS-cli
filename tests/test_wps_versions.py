import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from wps_ai_agent_cli import cli
from wps_ai_agent_cli.wps_versions import (
    compare_version_text,
    compare_wps_versions,
    parse_wps_version,
    version_state_path,
)


class WpsVersionCompareTests(unittest.TestCase):
    def test_parse_and_trailing_zero_equality(self):
        self.assertEqual(parse_wps_version(" 12.8.2.18913 "), (12, 8, 2, 18913))
        self.assertEqual(compare_version_text("12", "12.0.0"), "equal")
        self.assertEqual(compare_version_text("12.0", "12.0.0"), "equal")

    def test_orders_different_length_versions(self):
        self.assertEqual(compare_version_text("12.1", "12.0.9"), "newer")
        self.assertEqual(compare_version_text("11.9", "12"), "older")
        self.assertEqual(compare_version_text("12.0.1", "12"), "newer")

    def test_rejects_unparsable_shapes(self):
        for value in ("", "   ", "v12", "12.", "12..0", "12.8.2.18913.1.2.3.4.5", "12.1234567890", "12.-1"):
            self.assertIsNone(parse_wps_version(value), value)

    def test_record_then_compare_equal(self):
        with TemporaryDirectory() as tmpdir:
            ok, first, errors = compare_wps_versions(tmpdir, {"writer": "12.0"}, record=True)
            self.assertTrue(ok, errors)
            self.assertTrue(first["persisted"])
            self.assertEqual(first["comparisons"][0]["relation"], "absent_baseline")

            ok, second, errors = compare_wps_versions(tmpdir, {"writer": "12.0.0"}, record=False)
            self.assertTrue(ok, errors)
            self.assertFalse(second["persisted"])
            writer = second["comparisons"][0]
            self.assertEqual(writer["relation"], "equal")
            self.assertEqual(writer["baseline"], "12.0")

    def test_record_false_does_not_write(self):
        with TemporaryDirectory() as tmpdir:
            ok, result, errors = compare_wps_versions(tmpdir, {"writer": "12.0"}, record=False)
            self.assertTrue(ok, errors)
            self.assertFalse(result["persisted"])
            self.assertFalse(version_state_path(tmpdir).exists())

    def test_unparsable_current_keeps_baseline(self):
        with TemporaryDirectory() as tmpdir:
            compare_wps_versions(tmpdir, {"writer": "12.8.2.18913"}, record=True)
            before = version_state_path(tmpdir).read_text(encoding="utf-8")
            ok, result, errors = compare_wps_versions(tmpdir, {"writer": "not-a-version"}, record=True)
            self.assertTrue(ok, errors)
            self.assertFalse(result["persisted"])
            self.assertEqual(result["comparisons"][0]["relation"], "unparsable_current")
            self.assertEqual(version_state_path(tmpdir).read_text(encoding="utf-8"), before)

    def test_blank_observation_keeps_recorded_component(self):
        with TemporaryDirectory() as tmpdir:
            compare_wps_versions(tmpdir, {"writer": "12.0"}, record=True)
            ok, result, errors = compare_wps_versions(
                tmpdir,
                {"writer": "  ", "spreadsheets": "11.1"},
                record=True,
            )
            self.assertTrue(ok, errors)
            self.assertTrue(result["persisted"])
            relations = {item["component"]: item["relation"] for item in result["comparisons"]}
            self.assertEqual(relations["writer"], "absent_current")
            self.assertEqual(relations["spreadsheets"], "absent_baseline")
            stored = json.loads(version_state_path(tmpdir).read_text(encoding="utf-8"))
            self.assertEqual(stored["components"]["writer"]["version"], "12.0")
            self.assertEqual(stored["components"]["spreadsheets"]["version"], "11.1")

    def test_corrupt_json_is_quarantined_and_not_replaced(self):
        with TemporaryDirectory() as tmpdir:
            path = version_state_path(tmpdir)
            path.parent.mkdir(parents=True)
            path.write_text("{", encoding="utf-8")
            ok, result, errors = compare_wps_versions(tmpdir, {"writer": "12.0"}, record=True)
            self.assertFalse(ok)
            self.assertEqual(errors[0]["code"], "STATE_CORRUPT")
            self.assertFalse(path.exists())
            quarantined = list(path.parent.glob("wps-versions.json.corrupt-*"))
            self.assertEqual(len(quarantined), 1)
            self.assertEqual(quarantined[0].read_text(encoding="utf-8"), "{")
            self.assertNotIn("comparisons", result)

    def test_invalid_shape_is_not_overwritten(self):
        with TemporaryDirectory() as tmpdir:
            path = version_state_path(tmpdir)
            path.parent.mkdir(parents=True)
            original = json.dumps({"schema_version": 2, "components": {}})
            path.write_text(original, encoding="utf-8")
            ok, _result, errors = compare_wps_versions(tmpdir, {"writer": "12.0"}, record=True)
            self.assertFalse(ok)
            self.assertEqual(errors[0]["code"], "WPS_VERSION_STATE_INVALID")
            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_unknown_component_rejected(self):
        with TemporaryDirectory() as tmpdir:
            ok, _result, errors = compare_wps_versions(tmpdir, {"writer": "12.0", "pdf": "1"}, record=True)
            self.assertFalse(ok)
            self.assertEqual(errors[0]["code"], "WPS_VERSION_COMPONENT_UNKNOWN")
            self.assertFalse(version_state_path(tmpdir).exists())

    def test_cli_record_round_trip(self):
        with TemporaryDirectory() as tmpdir:
            stream = io.StringIO()
            code = cli.run(
                [
                    "wps-version-compare",
                    "--workspace",
                    tmpdir,
                    "--writer-version",
                    "12.0",
                    "--record",
                    "--request-id",
                    "p3-397",
                ],
                stream,
            )
            payload = json.loads(stream.getvalue())
            self.assertEqual(code, 0)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["command"], "wps-version-compare")
            self.assertEqual(payload["request_id"], "p3-397")
            self.assertTrue(payload["data"]["wps_version_compare"]["persisted"])
            stored = json.loads(version_state_path(tmpdir).read_text(encoding="utf-8"))
            self.assertEqual(stored["components"]["writer"]["version"], "12.0")
            self.assertEqual(list(Path(tmpdir).rglob("*.docx")), [])
