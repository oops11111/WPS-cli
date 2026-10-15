import unittest

from wps_ai_agent_cli.phases import list_phases


class PhaseTests(unittest.TestCase):
    def test_phase2_and_phase3_done(self):
        phases = {phase["id"]: phase for phase in list_phases()}

        self.assertEqual(phases["phase2"]["status"], "done")
        self.assertEqual(phases["phase3"]["status"], "done")

    def test_phase4_is_active(self):
        phases = {phase["id"]: phase for phase in list_phases()}

        self.assertEqual(phases["phase4"]["status"], "done")

    def test_phase5_is_done(self):
        phases = {phase["id"]: phase for phase in list_phases()}

        self.assertEqual(phases["phase5"]["status"], "done")

    def test_phase6_is_done(self):
        phases = {phase["id"]: phase for phase in list_phases()}

        self.assertEqual(phases["phase6"]["status"], "done")

    def test_phase7_is_active(self):
        phases = {phase["id"]: phase for phase in list_phases()}

        self.assertEqual(phases["phase7"]["status"], "active")


if __name__ == "__main__":
    unittest.main()
