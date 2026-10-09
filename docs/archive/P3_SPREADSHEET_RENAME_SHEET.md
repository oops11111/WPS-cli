# Spreadsheet Worksheet Rename

P3-090 adds `spreadsheet-rename-sheet` and the mutating MCP tool
`wps_agent_spreadsheet_rename_sheet`. Preflight requires the source worksheet
to exist, enforces Excel title restrictions (31 characters, forbidden/control
characters, boundary apostrophes and reserved `History` name), and rejects a
case-insensitive collision before backup or WPS launch.

`--dry-run` reports the original and expected ordered sheet-name lists without
backup or WPS. A real rename creates a backup, renames through WPS, then checks
the full ordered worksheet list both from WPS and from the saved workbook
package. The request ID is bound to the document, old/new names and dry-run
mode. A same-name no-op is recorded without saving or creating a backup.

Unit tests cover name validation, collision, dry-run, commit/read-back,
idempotent replay and conflicting reuse. An opt-in local WPS test renames a
worksheet and verifies that order and cell values remain intact.
