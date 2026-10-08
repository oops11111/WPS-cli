import unittest

from wps_ai_agent_cli.capabilities import probe_wps_capabilities


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


if __name__ == "__main__":
    unittest.main()
