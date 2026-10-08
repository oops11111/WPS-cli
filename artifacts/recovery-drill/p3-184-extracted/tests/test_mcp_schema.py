import unittest

from wps_ai_agent_cli.mcp_schema import (
    get_mcp_tool_schema,
    list_mcp_tool_categories,
    list_mcp_tool_schemas,
)


class McpSchemaTests(unittest.TestCase):
    def test_schema_names_are_unique_and_cover_current_cli_surface(self):
        schemas = list_mcp_tool_schemas()
        names = [schema["name"] for schema in schemas]
        commands = {schema["cli_command"] for schema in schemas}

        self.assertEqual(len(names), len(set(names)))
        self.assertGreaterEqual(len(schemas), 36)
        self.assertIn("spreadsheet-write", commands)
        self.assertIn("task-recovery", commands)
        self.assertIn("mcp-tools", commands)
        self.assertIn("mcp-catalog-snapshot", commands)
        self.assertIn("mcp-catalog-drift", commands)
        self.assertIn("mcp-call", commands)
        self.assertIn("mcp-server", commands)
        self.assertIn("wps-process-audit", commands)
        self.assertIn("cleanup-plan", commands)
        self.assertIn("cleanup-approval-manifest", commands)
        self.assertIn("artifact-retention-summary", commands)
        self.assertIn("project-status", commands)
        self.assertIn("workspace-health", commands)
        self.assertIn("local-handoff-summary", commands)
        self.assertIn("validation-runbook", commands)
        self.assertIn("documentation-freshness", commands)
        self.assertIn("mcp-smoke", commands)
        self.assertIn("mcp-config-audit", commands)
        self.assertIn("regression-manifest", commands)
        self.assertIn("regression-run", commands)
        self.assertIn("regression-evidence", commands)
        self.assertIn("regression-history", commands)
        self.assertIn("cloud-sync-package", commands)
        self.assertIn("sync-package-inspect", commands)
        self.assertIn("sync-package-summary", commands)
        self.assertIn("sync-package-manifest", commands)
        self.assertIn("sync-package-coverage", commands)
        self.assertIn("sync-package-readiness", commands)
        self.assertIn("security-audit", commands)
        self.assertIn("performance-baseline", commands)
        self.assertIn("writer-table-write", commands)
        self.assertIn("writer-table-smoke", commands)
        self.assertIn("html-render", commands)
        self.assertIn("html-editable", commands)
        self.assertIn("html-roundtrip-plan", commands)
        self.assertIn("html-batch-convert", commands)
        self.assertIn("batch-template-report", commands)

    def test_html_render_schema_exposes_local_only_safety_contract(self):
        schema = get_mcp_tool_schema("wps_agent_html_render")
        self.assertTrue(schema["mutates_document"])
        self.assertFalse(schema["requires_wps"])
        self.assertEqual(schema["input_schema"]["required"], ["input", "output", "format"])
        self.assertTrue(any("network" in note for note in schema["safety_notes"]))

    def test_html_batch_schema_exposes_bounds_tracking_and_artifact_safety(self):
        schema = get_mcp_tool_schema("wps_agent_html_batch_convert")
        self.assertTrue(schema["mutates_document"])
        self.assertFalse(schema["requires_wps"])
        self.assertEqual(schema["input_schema"]["required"], ["input_dir", "output_dir", "mode"])
        self.assertEqual(schema["input_schema"]["properties"]["mode"]["enum"], ["pdf", "png", "docx"])
        self.assertIn("task_id", schema["input_schema"]["properties"])
        self.assertTrue(any("100" in note and "500 MiB" in note for note in schema["safety_notes"]))
        inspection = get_mcp_tool_schema("wps_agent_html_batch_request")
        self.assertFalse(inspection["mutates_document"])
        self.assertFalse(inspection["requires_wps"])
        self.assertEqual(inspection["input_schema"]["required"], ["batch_request_id"])

    def test_batch_template_report_schema_has_explicit_input_and_write_boundaries(self):
        schema = get_mcp_tool_schema("wps_agent_batch_template_report")
        self.assertTrue(schema["mutates_document"])
        self.assertFalse(schema["requires_wps"])
        self.assertEqual(schema["input_schema"]["required"], ["manifest", "template", "output"])
        self.assertIn("task_id", schema["input_schema"]["properties"])
        self.assertTrue(any("never executed" in note for note in schema["safety_notes"]))

    def test_spreadsheet_write_schema_marks_safety_contract(self):
        schema = get_mcp_tool_schema("wps_agent_spreadsheet_write")

        self.assertIsNotNone(schema)
        self.assertTrue(schema["mutates_document"])
        self.assertTrue(schema["requires_wps"])
        self.assertEqual(
            schema["input_schema"]["required"],
            ["document_id", "range", "values_json"],
        )
        self.assertIn("task_id", schema["input_schema"]["properties"])
        self.assertIn("output_contract", schema)

    def test_schema_lookup_accepts_cli_command_name(self):
        schema = get_mcp_tool_schema("writer-replace")

        self.assertIsNotNone(schema)
        self.assertEqual(schema["name"], "wps_agent_writer_replace")

    def test_regression_run_schema_accepts_artifact_dir(self):
        schema = get_mcp_tool_schema("wps_agent_regression_run")

        self.assertIsNotNone(schema)
        self.assertIn("artifact_dir", schema["input_schema"]["properties"])

    def test_category_and_mutation_filters(self):
        spreadsheet = list_mcp_tool_schemas(category="spreadsheet")
        mutating = list_mcp_tool_schemas(mutates_document=True)
        categories = list_mcp_tool_categories()

        self.assertGreaterEqual(len(spreadsheet), 3)
        self.assertTrue(all(schema["category"] == "spreadsheet" for schema in spreadsheet))
        self.assertTrue(all(schema["mutates_document"] for schema in mutating))
        self.assertIn("recovery", categories)
        self.assertIn("security", categories)
        self.assertIn("performance", categories)
        self.assertIn("maintenance", categories)

    def test_mutating_schemas_expose_safety_boundaries(self):
        mutating = list_mcp_tool_schemas(mutates_document=True)

        self.assertGreaterEqual(len(mutating), 8)
        for schema in mutating:
            properties = schema["input_schema"]["properties"]
            self.assertIn("request_id", properties)
            self.assertIn("request_id", schema["idempotency"])
            self.assertIn("task_id", properties)
            self.assertTrue(schema["safety_notes"])


if __name__ == "__main__":
    unittest.main()
