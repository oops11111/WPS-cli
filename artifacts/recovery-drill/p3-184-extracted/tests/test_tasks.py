import unittest

from wps_ai_agent_cli.tasks import list_tasks


class TaskBoardTests(unittest.TestCase):
    def test_can_filter_tasks_by_phase_and_status(self):
        tasks = list_tasks(phase="phase0", status="done")

        self.assertTrue(tasks)
        self.assertTrue(all(task["phase"] == "phase0" for task in tasks))
        self.assertTrue(all(task["status"] == "done" for task in tasks))


if __name__ == "__main__":
    unittest.main()
