import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from wps_ai_agent_cli.batch_conversion import convert_html_batch, inspect_batch_request, _request_record_path
from wps_ai_agent_cli.com_backend import run_com_smoke
from wps_ai_agent_cli.document_text import docx_body_paragraphs


class BatchConversionTests(unittest.TestCase):
    def test_request_inspection_can_verify_current_evidence_without_mutation(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "input", root / "output"
            source.mkdir()
            (source / "a.html").write_text("A", encoding="utf-8")

            def render(path, destination, output_format):
                destination.write_bytes(b"PDF")
                return True, {}, []

            with patch("wps_ai_agent_cli.task_status.task_status_state_path", return_value=root / "statuses.json"), \
                 patch("wps_ai_agent_cli.batch_conversion.render_html", side_effect=render):
                ok, converted, _ = convert_html_batch(source, output, "pdf", request_id="verify-me")
                self.assertTrue(ok)
                record = _request_record_path("verify-me")
                manifest = Path(converted["manifest_path"])
                record_before, manifest_before = record.read_bytes(), manifest.read_bytes()
                ok, inspected, errors = inspect_batch_request("verify-me", verify=True)
                self.assertTrue(ok, errors)
                self.assertEqual(inspected["state"], "succeeded")
                self.assertEqual(inspected["evidence_status"], "passed")
                self.assertEqual((record.read_bytes(), manifest.read_bytes()), (record_before, manifest_before))

                (output / "a.pdf").write_bytes(b"damaged")
                ok, inspected, errors = inspect_batch_request("verify-me", verify=True)
                self.assertTrue(ok, errors)
                self.assertEqual(inspected["state"], "succeeded")
                self.assertEqual(inspected["evidence_status"], "failed")
                self.assertIn("changed", inspected["evidence_summary"])
                self.assertEqual((record.read_bytes(), manifest.read_bytes()), (record_before, manifest_before))

    def test_read_only_request_inspection_current_legacy_missing_and_corrupt(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("wps_ai_agent_cli.task_status.task_status_state_path", return_value=root / "statuses.json"):
                ok, _, errors = inspect_batch_request("missing")
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "BATCH_REQUEST_NOT_FOUND")
                self.assertEqual(list(root.iterdir()), [])

                record_path = _request_record_path("current")
                record_path.parent.mkdir()
                record_path.write_text(json.dumps({
                    "request_id": "current", "state": "succeeded",
                    "arguments": {"source_directory": "input", "output_directory": str(root / "out"),
                                  "mode": "docx", "recursive": False},
                }), encoding="utf-8")
                before = record_path.read_bytes()
                ok, record, errors = inspect_batch_request("current")
                self.assertTrue(ok, errors)
                self.assertEqual(record["record_origin"], "current")
                self.assertEqual(record["manifest_path"], str(root / "out" / "batch-conversion-manifest.json"))
                self.assertIn("replay", record["recovery_guidance"])
                self.assertEqual(record_path.read_bytes(), before)

                legacy_path = root / "html_batch_requests.json"
                legacy_path.write_text(json.dumps({"requests": {"legacy": {
                    "state": "cancelled", "arguments": {"output_directory": str(root / "legacy-output")},
                }}}), encoding="utf-8")
                ok, legacy, errors = inspect_batch_request("legacy")
                self.assertTrue(ok, errors)
                self.assertEqual(legacy["record_origin"], "legacy")
                self.assertIn("partial", legacy["recovery_guidance"])
                record_path.write_text("{bad", encoding="utf-8")
                ok, _, errors = inspect_batch_request("current")
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "BATCH_REQUEST_REGISTRY_INVALID")

    def test_completed_request_replays_in_new_cli_process(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "input", root / "output"
            source.mkdir()
            (source / "a.html").write_text("<p>Cross-process replay</p>", encoding="utf-8")
            env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))

            def invoke(destination):
                completed = subprocess.run([
                    sys.executable, "-m", "wps_ai_agent_cli", "html-batch-convert",
                    "--input-dir", str(source), "--output-dir", str(destination),
                    "--mode", "docx", "--request-id", "cross-process-request",
                ], cwd=root, env=env, capture_output=True, text=True, timeout=20)
                return completed, json.loads(completed.stdout)

            first, initial = invoke(output)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertTrue(initial["ok"])
            artifact = output / "a.docx"
            before_bytes = artifact.read_bytes()
            before_mtime = artifact.stat().st_mtime_ns

            second, replay = invoke(output)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertTrue(replay["data"]["replayed"])
            self.assertEqual(artifact.read_bytes(), before_bytes)
            self.assertEqual(artifact.stat().st_mtime_ns, before_mtime)

            third, conflict = invoke(root / "changed-output")
            self.assertFalse(conflict["ok"])
            self.assertEqual(conflict["errors"][0]["code"], "BATCH_REPLAY_CONFLICT")
            self.assertFalse((root / "changed-output" / "a.docx").exists())

    def test_request_record_write_failures_keep_recoverable_evidence(self):
        from wps_ai_agent_cli import batch_conversion

        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "input", root / "output"
            source.mkdir()
            (source / "a.html").write_text("A", encoding="utf-8")
            calls = []

            def render(path, destination, output_format):
                calls.append(path.name)
                destination.write_bytes(b"PDF")
                return True, {}, []

            with patch("wps_ai_agent_cli.task_status.task_status_state_path", return_value=root / "statuses.json"), \
                 patch("wps_ai_agent_cli.batch_conversion.render_html", side_effect=render):
                with patch.object(batch_conversion, "_store_request_record", side_effect=OSError("storage unavailable")):
                    ok, _, errors = convert_html_batch(source, output, "pdf", request_id="recover")
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "BATCH_REQUEST_REGISTRY_WRITE_FAILED")
                self.assertEqual(calls, [])
                self.assertFalse((output / "batch-conversion-manifest.json").exists())

                original_store = batch_conversion._store_request_record
                stores = 0

                def fail_terminal(path, record):
                    nonlocal stores
                    stores += 1
                    if stores == 2:
                        raise OSError("terminal update unavailable")
                    return original_store(path, record)

                with patch.object(batch_conversion, "_store_request_record", side_effect=fail_terminal):
                    ok, manifest, errors = convert_html_batch(source, output, "pdf", request_id="recover")
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "BATCH_REQUEST_REGISTRY_WRITE_FAILED")
                self.assertTrue(Path(manifest["manifest_path"]).is_file())
                self.assertEqual(json.loads(_request_record_path("recover").read_text(encoding="utf-8"))["state"], "running")

                ok, replayed, errors = convert_html_batch(source, output, "pdf", request_id="recover")
                self.assertTrue(ok, errors)
                self.assertTrue(replayed["replayed"])
                self.assertEqual(calls, ["a.html"])

    def test_request_records_are_bounded_and_legacy_completion_migrates(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "input", root / "output"
            source.mkdir()
            (source / "a.html").write_text("A", encoding="utf-8")

            def render(path, destination, output_format):
                destination.write_bytes(b"PDF")
                return True, {}, []

            with patch("wps_ai_agent_cli.task_status.task_status_state_path", return_value=root / "statuses.json"), \
                 patch("wps_ai_agent_cli.batch_conversion.render_html", side_effect=render):
                with patch("wps_ai_agent_cli.batch_conversion._MAX_REQUEST_RECORD_BYTES", 20):
                    ok, _, errors = convert_html_batch(source, output, "pdf", request_id="bounded")
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "BATCH_REQUEST_REGISTRY_FULL")
                self.assertFalse(_request_record_path("bounded").exists())
                self.assertFalse((output / "batch-conversion-manifest.json").exists())

                ok, _, errors = convert_html_batch(source, output, "pdf", request_id="legacy")
                self.assertTrue(ok, errors)
                record_path = _request_record_path("legacy")
                record = json.loads(record_path.read_text(encoding="utf-8"))
                record_path.unlink()
                legacy_path = root / "html_batch_requests.json"
                legacy_path.write_text(json.dumps({"requests": {"legacy": {
                    "arguments": record["arguments"], "state": "running",
                }}}), encoding="utf-8")
                ok, replayed, errors = convert_html_batch(source, output, "pdf", request_id="legacy")
                self.assertTrue(ok, errors)
                self.assertTrue(replayed["replayed"])
                self.assertEqual(json.loads(record_path.read_text(encoding="utf-8"))["state"], "succeeded")
                self.assertEqual(json.loads(legacy_path.read_text(encoding="utf-8"))["requests"]["legacy"]["state"], "running")

    def test_corrupt_request_record_blocks_replay_without_touching_manifest(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "input", root / "output"
            source.mkdir()
            (source / "a.html").write_text("A", encoding="utf-8")

            def render(path, destination, output_format):
                destination.write_bytes(b"PDF")
                return True, {}, []

            with patch("wps_ai_agent_cli.task_status.task_status_state_path", return_value=root / "statuses.json"), \
                 patch("wps_ai_agent_cli.batch_conversion.render_html", side_effect=render):
                ok, result, _ = convert_html_batch(source, output, "pdf", request_id="damaged")
                self.assertTrue(ok)
                manifest = Path(result["manifest_path"])
                before = manifest.read_bytes()
                _request_record_path("damaged").write_text("{bad", encoding="utf-8")
                ok, _, errors = convert_html_batch(source, output, "pdf", request_id="damaged")
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "BATCH_REQUEST_REGISTRY_INVALID")
                self.assertEqual(manifest.read_bytes(), before)

    def test_stranded_running_request_recovers_only_from_verified_manifest(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "input", root / "output"
            source.mkdir()
            (source / "a.html").write_text("A", encoding="utf-8")
            calls = []

            def render(path, destination, output_format):
                calls.append(path.name)
                destination.write_bytes(b"PDF")
                return True, {}, []

            with patch("wps_ai_agent_cli.task_status.task_status_state_path", return_value=root / "statuses.json"), \
                 patch("wps_ai_agent_cli.batch_conversion.render_html", side_effect=render):
                registry = _request_record_path("stranded")
                ok, result, _ = convert_html_batch(source, output, "pdf", request_id="stranded")
                self.assertTrue(ok)
                state = json.loads(registry.read_text(encoding="utf-8"))
                state["state"] = "running"
                registry.write_text(json.dumps(state), encoding="utf-8")
                ok, replayed, errors = convert_html_batch(source, output, "pdf", request_id="stranded")
                self.assertTrue(ok, errors)
                self.assertTrue(replayed["replayed"])
                self.assertEqual(calls, ["a.html"])
                self.assertEqual(json.loads(registry.read_text(encoding="utf-8"))["state"], "succeeded")

                state["state"] = "running"
                registry.write_text(json.dumps(state), encoding="utf-8")
                (output / "a.pdf").write_bytes(b"damaged")
                ok, _, errors = convert_html_batch(source, output, "pdf", request_id="stranded")
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "BATCH_REPLAY_EVIDENCE_MISMATCH")
                self.assertEqual(json.loads(registry.read_text(encoding="utf-8"))["state"], "running")
                self.assertEqual(calls, ["a.html"])

    def test_active_duplicate_request_is_not_rendered_twice(self):
        from threading import Event, Thread

        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "input", root / "output"
            source.mkdir()
            (source / "a.html").write_text("A", encoding="utf-8")
            started, release = Event(), Event()
            result = {}
            calls = []

            def render(path, destination, output_format):
                calls.append(path.name)
                started.set()
                self.assertTrue(release.wait(5))
                destination.write_bytes(b"PDF")
                return True, {}, []

            def worker():
                result["first"] = convert_html_batch(source, output, "pdf", request_id="active")

            with patch("wps_ai_agent_cli.task_status.task_status_state_path", return_value=root / "statuses.json"), \
                 patch("wps_ai_agent_cli.batch_conversion.render_html", side_effect=render):
                thread = Thread(target=worker)
                thread.start()
                try:
                    self.assertTrue(started.wait(5))
                    ok, _, errors = convert_html_batch(source, output, "pdf", request_id="active")
                    self.assertFalse(ok)
                    self.assertEqual(errors[0]["code"], "BATCH_REPLAY_UNAVAILABLE")
                finally:
                    release.set()
                    thread.join(5)
                self.assertFalse(thread.is_alive())
                self.assertTrue(result["first"][0])
                self.assertEqual(calls, ["a.html"])

    def test_completed_request_replays_only_with_intact_arguments_and_artifacts(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "input", root / "output"
            source.mkdir()
            html = source / "a.html"
            html.write_text("A", encoding="utf-8")
            calls = []

            def render(path, destination, output_format):
                calls.append(path.name)
                destination.write_bytes(b"PDF")
                return True, {}, []

            with patch("wps_ai_agent_cli.task_status.task_status_state_path", return_value=root / "statuses.json"), \
                 patch("wps_ai_agent_cli.batch_conversion.render_html", side_effect=render):
                ok, first, errors = convert_html_batch(source, output, "pdf", request_id="same")
                self.assertTrue(ok, errors)
                manifest = Path(first["manifest_path"])
                original_bytes = manifest.read_bytes()
                ok, replayed, errors = convert_html_batch(source, output, "pdf", request_id="same")
                self.assertTrue(ok, errors)
                self.assertTrue(replayed["replayed"])
                self.assertEqual(calls, ["a.html"])
                self.assertEqual(manifest.read_bytes(), original_bytes)

                ok, _, errors = convert_html_batch(source, output, "pdf", request_id="different")
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "OUTPUT_ALREADY_EXISTS")
                for kwargs in ({"request_id": "same", "recursive": True},):
                    ok, _, errors = convert_html_batch(source, output, "pdf", **kwargs)
                    self.assertFalse(ok)
                    self.assertEqual(errors[0]["code"], "BATCH_REPLAY_CONFLICT")
                ok, _, errors = convert_html_batch(source, root / "other-output", "pdf", request_id="same")
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "BATCH_REPLAY_CONFLICT")

                html.write_text("changed", encoding="utf-8")
                ok, _, errors = convert_html_batch(source, output, "pdf", request_id="same")
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "BATCH_REPLAY_EVIDENCE_MISMATCH")
                html.write_text("A", encoding="utf-8")
                (output / "a.pdf").write_bytes(b"CHANGED")
                ok, _, errors = convert_html_batch(source, output, "pdf", request_id="same")
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "BATCH_REPLAY_EVIDENCE_MISMATCH")
                self.assertEqual(calls, ["a.html"])

    def test_replay_rejects_added_source_and_legacy_manifest(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "input", root / "output"
            source.mkdir()
            (source / "a.html").write_text("A", encoding="utf-8")

            def render(path, destination, output_format):
                destination.write_bytes(b"PDF")
                return True, {}, []

            with patch("wps_ai_agent_cli.task_status.task_status_state_path", return_value=root / "statuses.json"), \
                 patch("wps_ai_agent_cli.batch_conversion.render_html", side_effect=render):
                ok, result, _ = convert_html_batch(source, output, "pdf", request_id="same")
                self.assertTrue(ok)
                (source / "b.html").write_text("B", encoding="utf-8")
                ok, _, errors = convert_html_batch(source, output, "pdf", request_id="same")
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "BATCH_REPLAY_EVIDENCE_MISMATCH")
                (source / "b.html").unlink()
                manifest = Path(result["manifest_path"])
                stored = json.loads(manifest.read_text(encoding="utf-8"))
                stored.pop("request_id")
                manifest.write_text(json.dumps(stored), encoding="utf-8")
                ok, _, errors = convert_html_batch(source, output, "pdf", request_id="same")
                self.assertFalse(ok)
                self.assertEqual(errors[0]["code"], "OUTPUT_ALREADY_EXISTS")

    def test_batch_isolates_file_failure_and_writes_provenance_manifest(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "input", root / "output"
            source.mkdir()
            (source / "a.html").write_text("A", encoding="utf-8")
            (source / "b.html").write_text("B", encoding="utf-8")
            calls = []

            def convert(path, destination, output_format):
                calls.append(path.name)
                if path.name == "a.html":
                    return False, {}, [{"code": "TEST_FAILURE", "message": "isolated"}]
                destination.write_bytes(b"PDF")
                return True, {"output_path": str(destination)}, []

            with patch("wps_ai_agent_cli.batch_conversion.render_html", side_effect=convert):
                ok, result, errors = convert_html_batch(source, output, "pdf")
            self.assertFalse(ok)
            self.assertEqual(errors, [])
            self.assertEqual(calls, ["a.html", "b.html"])
            self.assertEqual(result["summary"], {"total": 2, "processed": 2, "passed": 1, "failed": 1, "cancelled": False})
            manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
            self.assertEqual([item["status"] for item in manifest["files"]], ["failed", "passed"])
            self.assertEqual(len(manifest["files"][1]["output_sha256"]), 64)

    def test_cooperative_cancel_preserves_completed_files_in_manifest(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "input", root / "output"
            source.mkdir()
            (source / "a.html").write_text("A", encoding="utf-8")
            (source / "b.html").write_text("B", encoding="utf-8")
            converted = []

            def convert(path, destination, output_format):
                converted.append(path.name)
                destination.write_bytes(b"PDF")
                return True, {}, []

            def progress(completed, total, message):
                return completed < 1

            with patch("wps_ai_agent_cli.batch_conversion.render_html", side_effect=convert):
                ok, result, errors = convert_html_batch(source, output, "pdf", progress_callback=progress)
            self.assertFalse(ok)
            self.assertEqual(errors, [])
            self.assertEqual(converted, ["a.html"])
            self.assertTrue(result["cancelled"])
            self.assertEqual(result["summary"], {"total": 2, "processed": 1, "passed": 1, "failed": 0, "cancelled": True})
            stored = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
            self.assertEqual([entry["relative_source"] for entry in stored["files"]], ["a.html"])

    def test_batch_refuses_existing_manifest_and_output_is_not_overwritten(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "input", root / "output"
            source.mkdir()
            output.mkdir()
            (source / "a.html").write_text("A", encoding="utf-8")
            (output / "batch-conversion-manifest.json").write_text("keep", encoding="utf-8")
            ok, _, errors = convert_html_batch(source, output, "docx")
            self.assertFalse(ok)
            self.assertEqual(errors[0]["code"], "OUTPUT_ALREADY_EXISTS")

    def test_batch_rejects_output_inside_input_tree(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input"
            source.mkdir()
            ok, _, errors = convert_html_batch(source, source / "output", "png")
            self.assertFalse(ok)
            self.assertEqual(errors[0]["code"], "INVALID_OUTPUT")


@unittest.skipUnless(os.environ.get("WPS_AGENT_RUN_BROWSER_INTEGRATION") == "1", "set WPS_AGENT_RUN_BROWSER_INTEGRATION=1 to launch local Edge")
class BatchConversionBrowserIntegrationTests(unittest.TestCase):
    def test_batch_pdf_and_png_outputs_are_verified_and_network_isolated(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input"
            source.mkdir()
            for name, color in (("one", "#d13b3b"), ("two", "#227755")):
                (source / f"{name}.html").write_text(
                    f"<!doctype html><html><head><title>{name}</title></head><body><h1 style='color:{color}'>Visible {name}</h1></body></html>",
                    encoding="utf-8",
                )
            for mode in ("pdf", "png"):
                output = root / f"{mode}-output"
                ok, result, errors = convert_html_batch(source, output, mode)
                self.assertTrue(ok, {"errors": errors, "result": result})
                self.assertEqual(result["summary"], {"total": 2, "passed": 2, "failed": 0})
                manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
                self.assertEqual(len(manifest["files"]), 2)
                for entry in manifest["files"]:
                    self.assertEqual(len(entry["source_sha256"]), 64)
                    self.assertEqual(len(entry["output_sha256"]), 64)
                    self.assertFalse(entry["conversion"]["network_access"])
                    self.assertFalse(entry["conversion"]["javascript_enabled"])
                    artifact = Path(entry["output"])
                    self.assertGreater(artifact.stat().st_size, 1000)
                    if mode == "pdf":
                        self.assertEqual(artifact.read_bytes()[:4], b"%PDF")
                    else:
                        from PIL import Image
                        import io
                        image = Image.open(io.BytesIO(artifact.read_bytes()))
                        self.assertEqual(image.format, "PNG")
                        self.assertGreater(image.width, 320)


@unittest.skipUnless(os.environ.get("WPS_AGENT_RUN_INTEGRATION") == "1", "set WPS_AGENT_RUN_INTEGRATION=1 to launch local WPS Writer")
class BatchConversionWpsIntegrationTests(unittest.TestCase):
    def test_batch_docx_outputs_open_save_and_retain_text_in_wps(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "input", root / "output"
            source.mkdir()
            expected = {}
            for name in ("alpha", "beta"):
                text = f"WPS batch verification {name}"
                expected[name] = text
                (source / f"{name}.html").write_text(f"<h1>{text}</h1>", encoding="utf-8")
            ok, result, errors = convert_html_batch(source, output, "docx")
            self.assertTrue(ok, {"errors": errors, "result": result})
            for entry in result["files"]:
                source_docx = Path(entry["output"])
                saved_copy = root / f"wps-{source_docx.stem}.docx"
                outcome = run_com_smoke("writer", str(source_docx), str(saved_copy), visible=False)
                self.assertTrue(outcome["ok"], outcome)
                paragraphs = docx_body_paragraphs(saved_copy)
                self.assertIn(expected[source_docx.stem], "\n".join(paragraphs))


if __name__ == "__main__":
    unittest.main()
