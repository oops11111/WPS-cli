import copy
import importlib.util
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "envgate", Path(__file__).resolve().parents[1] / "scripts/table_width_environment.py"
)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class TableWidthEnvironmentTests(unittest.TestCase):
    def test_explicit_data_na_preserves_raw_absence(self):
        result = (
            True,
            {
                "passed": True,
                "group": "A",
                "verdict": {"text": True, "structure": True, "formatting": True},
                "aspects": {
                    **{k: {"score": 1.0} for k in ("text", "structure", "formatting")},
                    "data": {"status": "not applicable"},
                    "animations": {"status": "not applicable"},
                },
            },
            [],
        )
        original = copy.deepcopy(result)
        self.assertTrue(m.semantic_pass(result))
        self.assertTrue(m.semantic_assessment(result)["effective_verdict"]["data"])
        self.assertNotIn("data", result[1]["verdict"])
        self.assertEqual(result, original)

    def test_all_five_archived_schemas_and_rejections(self):
        import json

        base = Path(__file__).resolve().parents[1] / "artifacts/alignment-aware-print-margins-20261121"
        cases = sorted(p.name for p in base.glob("A-*-docx"))
        self.assertEqual(len(m.audit_schemas(base, cases)), 5)
        good = json.loads((base / "A-newsletter-docx/semantic-fidelity.json").read_text(encoding="utf-8"))
        for mode in ("false", "contradiction", "unknown", "missing", "score", "verdict", "passed", "group", "bool"):
            bad = copy.deepcopy(good)
            if mode == "false":
                bad[1]["verdict"]["data"] = False
            elif mode == "contradiction":
                bad[1]["aspects"]["data"]["score"] = 1.0
            elif mode == "unknown":
                bad[1]["aspects"]["data"]["status"] = "unknown"
            elif mode == "missing":
                bad[1]["aspects"].pop("data")
            elif mode == "score":
                bad[1]["aspects"]["text"]["score"] = 0.99
            elif mode == "verdict":
                bad[1]["verdict"].pop("text")
            elif mode == "passed":
                bad[1]["passed"] = False
            elif mode == "group":
                bad[1]["group"] = "B"
            elif mode == "bool":
                bad[1]["aspects"]["text"]["score"] = True
            with self.subTest(mode=mode):
                self.assertFalse(m.semantic_pass(bad))
        good[1]["verdict"]["data"] = True
        self.assertTrue(m.semantic_pass(good))

    def test_missing_module_environment_stops_before_runtime(self):
        with (
            patch.dict(os.environ, {"NODE_PATH": ""}),
            patch("wps_ai_agent_cli.html_styles.browser_runtime") as runtime,
        ):
            with self.assertRaisesRegex(ValueError, "NODE_PATH"):
                m.environment_gate(Path.cwd())
            runtime.assert_not_called()

    def test_cascade_semantic_source_rejected_without_reader(self):
        with patch("wps_ai_agent_cli.fidelity.fidelity_check") as check:
            with self.assertRaises(ValueError):
                m.semantic_snapshot(Path("a.html"), Path("a.docx"), SimpleNamespace(mode="cascade"))
            check.assert_not_called()

    def test_browser_snapshot_source_identity_and_no_recapture(self):
        from wps_ai_agent_cli import html_styles

        source = Path("a.html").resolve()
        styled = SimpleNamespace(mode="browser", source=source)
        good = (
            True,
            {
                "passed": True,
                "group": "A",
                "verdict": {k: True for k in ("text", "structure", "formatting", "data")},
                "aspects": {
                    **{k: {"score": 1.0} for k in ("text", "structure", "formatting", "data")},
                    "animations": {"status": "not applicable"},
                },
            },
            [],
        )

        def reader(path, target, **kwargs):
            self.assertIs(html_styles.load(path, use_browser=True), styled)
            return good

        with patch("wps_ai_agent_cli.fidelity.fidelity_check", side_effect=reader):
            self.assertTrue(m.semantic_pass(m.semantic_snapshot(source, Path("a.docx"), styled)))

        def wrong_reader(path, target, **kwargs):
            return html_styles.load(Path("wrong.html"))

        with patch("wps_ai_agent_cli.fidelity.fidelity_check", side_effect=wrong_reader):
            with self.assertRaises(ValueError):
                m.semantic_snapshot(source, Path("a.docx"), styled)

    def test_snapshot_fallback_rejected_before_parse(self):
        with patch("wps_ai_agent_cli.html_styles.load") as loader:
            with self.assertRaises(ValueError):
                m.restore_snapshot(Path("unused"), {"mode": "cascade"})
            loader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
