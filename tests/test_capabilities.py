import platform
import unittest
from unittest.mock import patch

from wps_ai_agent_cli import capabilities
from wps_ai_agent_cli.capabilities import clear_capabilities_cache, probe_wps_capabilities


class CapabilityProbeTests(unittest.TestCase):
    def test_probe_reports_registered_component_with_injected_resolver(self):
        def resolver(prog_id: str) -> object:
            if prog_id == "kwps.Application":
                return object()
            raise RuntimeError("missing")

        data = probe_wps_capabilities(clsid_resolver=resolver)

        self.assertIn("platform", data)
        self.assertIn("components", data)
        self.assertTrue(data["components"]["writer"]["detected"])
        self.assertEqual(
            data["components"]["writer"]["selected_prog_id"],
            "kwps.Application",
        )

    def test_injected_resolver_does_not_claim_platform_is_windows(self):
        data = probe_wps_capabilities(clsid_resolver=lambda prog_id: object())
        self.assertTrue(data["components"]["spreadsheets"]["detected"])
        self.assertEqual(data["platform"]["is_windows"], platform.system() == "Windows")

    def test_default_probe_is_cached_until_cleared(self):
        clear_capabilities_cache()
        calls = []
        real = capabilities._probe_wps_capabilities

        def counting(resolver=None):
            calls.append(resolver)
            return real(resolver)

        try:
            with patch.object(capabilities, "_probe_wps_capabilities", side_effect=counting):
                first = probe_wps_capabilities()
                first["components"]["writer"]["detected"] = "mutated"
                second = probe_wps_capabilities()
                self.assertEqual(len(calls), 1)
                self.assertNotEqual(second["components"]["writer"]["detected"], "mutated")
                clear_capabilities_cache()
                probe_wps_capabilities()
                self.assertEqual(len(calls), 2)
        finally:
            clear_capabilities_cache()

    def test_injected_resolver_bypasses_cache(self):
        clear_capabilities_cache()
        first = probe_wps_capabilities(clsid_resolver=lambda prog_id: object())
        second = probe_wps_capabilities(clsid_resolver=lambda prog_id: (_ for _ in ()).throw(RuntimeError("x")))
        self.assertTrue(first["components"]["writer"]["detected"])
        self.assertFalse(second["components"]["writer"]["detected"])


if __name__ == "__main__":
    unittest.main()
