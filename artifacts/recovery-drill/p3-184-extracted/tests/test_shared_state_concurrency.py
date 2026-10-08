import os
import subprocess
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook

from wps_ai_agent_cli.operations import list_operations
from wps_ai_agent_cli.sessions import list_documents, register_document
from wps_ai_agent_cli.spreadsheet_ops import rename_spreadsheet_sheet
from wps_ai_agent_cli.state_store import atomic_write_json


class SharedStateConcurrencyTests(unittest.TestCase):
    def test_failed_atomic_replace_keeps_previous_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "documents.json"
            atomic_write_json(path, {"documents": {"original": {}}})
            previous = path.read_bytes()
            with patch("wps_ai_agent_cli.state_store.os.replace", side_effect=PermissionError("busy")):
                with patch("wps_ai_agent_cli.state_store.time.sleep") as sleep:
                    with self.assertRaises(PermissionError):
                        atomic_write_json(path, {"documents": {"replacement": {}}})
            self.assertEqual(path.read_bytes(), previous)
            self.assertEqual(list(Path(tmp).glob("*.tmp")), [])
            self.assertEqual(sleep.call_count, 19)

    def test_different_documents_keep_all_records_across_processes(self):
        workers, per_worker = 4, 12
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            for worker in range(workers):
                for index in range(per_worker):
                    (workspace / f"worker-{worker}-{index}.docx").write_bytes(f"{worker}:{index}".encode())
            code = (
                "import sys\n"
                "from pathlib import Path\n"
                "from wps_ai_agent_cli.sessions import register_document\n"
                "from wps_ai_agent_cli.operations import record_operation\n"
                "root, worker, count = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])\n"
                "for index in range(count):\n"
                "    ok, record, errors = register_document('writer', str(root / f'worker-{worker}-{index}.docx'), root)\n"
                "    if not ok: raise RuntimeError(errors)\n"
                "    record_operation(f'req-{worker}-{index}', 'probe', {'document_id': record['document_id']}, root)\n"
            )
            env = dict(os.environ)
            source = str(Path(__file__).resolve().parents[1] / "src")
            env["PYTHONPATH"] = source + os.pathsep + env.get("PYTHONPATH", "")
            processes = [subprocess.Popen(
                [sys.executable, "-c", code, tmp, str(worker), str(per_worker)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
            ) for worker in range(workers)]
            try:
                deadline = time.monotonic() + 30
                while any(process.poll() is None for process in processes):
                    self.assertLess(time.monotonic(), deadline, "Concurrent state workers timed out.")
                    list_documents(workspace)
                    list_operations(workspace)
                    time.sleep(0.01)
                for process in processes:
                    output, error = process.communicate(timeout=5)
                    self.assertEqual(process.returncode, 0, output + error)
                self.assertEqual(len(list_documents(workspace)), workers * per_worker)
                self.assertEqual(len(list_operations(workspace)), workers * per_worker)
            finally:
                for process in processes:
                    if process.poll() is None:
                        process.terminate()
                        process.wait(timeout=5)
                    if process.stdout:
                        process.stdout.close()
                    if process.stderr:
                        process.stderr.close()

    def test_same_request_id_on_different_documents_conflicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            document_ids = []
            for index in range(2):
                path = Path(tmp) / f"book-{index}.xlsx"
                workbook = Workbook()
                workbook.active.title = "Same"
                workbook.save(path)
                workbook.close()
                ok, record, errors = register_document("spreadsheets", str(path), tmp)
                self.assertTrue(ok, errors)
                document_ids.append(record["document_id"])
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(
                    lambda document_id: rename_spreadsheet_sheet(
                        document_id, "Same", "Same", "shared-request", workspace=tmp,
                    ), document_ids,
                ))
            self.assertEqual(sum(result[0] for result in results), 1)
            self.assertEqual([error["code"] for result in results for error in result[2]], ["IDEMPOTENCY_CONFLICT"])


if __name__ == "__main__":
    unittest.main()
