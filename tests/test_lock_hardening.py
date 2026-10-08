import os
import tempfile
import threading
import time
import unittest
from pathlib import Path

from wps_ai_agent_cli import mutation_lock
from wps_ai_agent_cli.mutation_lock import DocumentBusyError, document_mutation_lock
from wps_ai_agent_cli.sessions import stable_document_id


class ReentrancyTests(unittest.TestCase):
    def test_same_thread_can_reenter_without_waiting(self):
        with tempfile.TemporaryDirectory() as tmp:
            started = time.monotonic()
            with document_mutation_lock("doc", tmp, 0.5):
                with document_mutation_lock("doc", tmp, 0.5):
                    pass
            self.assertLess(time.monotonic() - started, 0.4)

    def test_lock_still_excludes_other_threads_after_inner_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            outcome = []

            def other():
                try:
                    with document_mutation_lock("doc", tmp, 0.2):
                        outcome.append("acquired")
                except DocumentBusyError:
                    outcome.append("busy")

            with document_mutation_lock("doc", tmp, 1):
                with document_mutation_lock("doc", tmp, 1):
                    pass
                thread = threading.Thread(target=other)
                thread.start()
                thread.join()
            self.assertEqual(outcome, ["busy"])
            with document_mutation_lock("doc", tmp, 1):
                pass

    def test_lock_is_released_after_outer_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            with document_mutation_lock("doc", tmp, 1):
                pass
            outcome = []

            def other():
                with document_mutation_lock("doc", tmp, 1):
                    outcome.append("acquired")

            thread = threading.Thread(target=other)
            thread.start()
            thread.join()
            self.assertEqual(outcome, ["acquired"])


class StaleLockPruningTests(unittest.TestCase):
    def test_old_unheld_lock_files_are_removed_and_recent_ones_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            locks = Path(tmp).resolve() / ".wps-agent" / "locks"
            locks.mkdir(parents=True)
            old, recent = locks / "old.lock", locks / "recent.lock"
            old.write_bytes(b"")
            recent.write_bytes(b"")
            ancient = time.time() - mutation_lock.STALE_LOCK_SECONDS - 100
            os.utime(old, (ancient, ancient))
            mutation_lock._pruned_directories.discard(str(locks))
            with document_mutation_lock("fresh", tmp, 1):
                pass
            self.assertFalse(old.exists())
            self.assertTrue(recent.exists())


class DocumentIdTests(unittest.TestCase):
    def test_id_is_stable_for_same_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "a.docx")
            self.assertEqual(stable_document_id("writer", path), stable_document_id("writer", path))
            self.assertNotEqual(stable_document_id("writer", path), stable_document_id("spreadsheets", path))

    @unittest.skipIf(os.name == "nt", "case-sensitive file systems only")
    def test_paths_differing_only_by_case_do_not_collide_on_case_sensitive_systems(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertNotEqual(
                stable_document_id("writer", str(Path(tmp) / "A.docx")),
                stable_document_id("writer", str(Path(tmp) / "a.docx")),
            )


if __name__ == "__main__":
    unittest.main()
