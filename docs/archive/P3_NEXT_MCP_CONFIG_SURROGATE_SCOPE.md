# P3-301 MCP Config Unicode Surrogate Scope

## Goal

Reject JSON strings containing invalid unpaired UTF-16 surrogate code points before using config values to launch a process.

## Requirements

- Validate every decoded JSON string, including object keys and nested values.
- Reject isolated high or low surrogates.
- Accept valid high/low surrogate pairs and ordinary Unicode text.
- Return bounded diagnostics without exposing the offending string or config contents.
- Never spawn a configured process for rejected input.

## Validation

- Cover isolated high/low surrogate escapes at top-level and nested process fields.
- Cover valid surrogate pairs and non-ASCII BMP text.
- Assert rejected cases do not spawn and diagnostics do not include marker content.
- Run configuration audit tests, full default suite, safe regression, and package readiness.
