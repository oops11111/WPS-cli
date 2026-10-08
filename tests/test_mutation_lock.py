import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wps_ai_agent_cli.mutation_lock import DocumentBusyError, document_mutation_lock
from wps_ai_agent_cli.sessions import register_document, stable_document_id
from wps_ai_agent_cli.writer_ops import writer_fill_bookmark


class MutationLockTests(unittest.TestCase):
    def test_lock_releases_after_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                with document_mutation_lock("doc-example", tmp):
                    raise RuntimeError("controlled failure")
            with document_mutation_lock("doc-example", tmp, timeout_seconds=0.1):
                pass

    def test_cross_process_contention_and_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            document = Path(tmp) / "sample.docx"
            document.write_bytes(b"controlled")
            document_id = stable_document_id("writer", str(document))
            code = (
                "import sys, time\n"
                "from wps_ai_agent_cli.mutation_lock import document_mutation_lock\n"
                "with document_mutation_lock(sys.argv[1], sys.argv[2]):\n"
                "    print('locked', flush=True)\n"
                "    time.sleep(3)\n"
            )
            env = dict(os.environ)
            source = str(Path(__file__).resolve().parents[1] / "src")
            env["PYTHONPATH"] = source + os.pathsep + env.get("PYTHONPATH", "")
            process = subprocess.Popen(
                [sys.executable, "-c", code, document_id, tmp],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
            )
            try:
                self.assertEqual(process.stdout.readline().strip(), "locked", process.stderr.read() if process.poll() is not None else "")
                with self.assertRaises(DocumentBusyError):
                    with document_mutation_lock(document_id, tmp, timeout_seconds=0.1):
                        pass
                with patch("wps_ai_agent_cli.mutation_lock.DEFAULT_TIMEOUT_SECONDS", 0.1):
                    ok, _, errors, _ = writer_fill_bookmark(
                        document_id, "Target", "new", "contended", workspace=tmp,
                    )
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "DOCUMENT_BUSY")
                with patch("wps_ai_agent_cli.sessions.REGISTRATION_LOCK_TIMEOUT_SECONDS", 0.1):
                    registered, _, register_errors = register_document("writer", str(document), tmp)
                self.assertFalse(registered)
                self.assertEqual(register_errors[0]["code"], "DOCUMENT_BUSY")
                with document_mutation_lock("another-document", tmp, timeout_seconds=0.1):
                    pass
                process.wait(timeout=6)
                self.assertEqual(process.returncode, 0, process.stderr.read())
                with document_mutation_lock(document_id, tmp, timeout_seconds=0.1):
                    pass
                registered, _, register_errors = register_document("writer", str(document), tmp)
                self.assertTrue(registered, register_errors)
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=6)
                process.stdout.close()
                process.stderr.close()


if __name__ == "__main__":
    unittest.main()
