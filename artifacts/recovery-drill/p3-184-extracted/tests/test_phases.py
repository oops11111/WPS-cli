import unittest

from wps_ai_agent_cli.phases import list_phases


class PhaseTests(unittest.TestCase):
    def test_phase2_done_and_phase3_active(self):
        phases = {phase["id"]: phase for phase in list_phases()}

        self.assertEqual(phases["phase2"]["status"], "done")
        self.assertEqual(phases["phase3"]["status"], "active")


if __name__ == "__main__":
    unittest.main()
