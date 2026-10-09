# P3-306 MCP Schema Constraint Metadata Scope

## Goal

Fail safely when adapter-consumed schema constraints have malformed metadata.

## Requirements

- Validate metadata types for numeric minimum/maximum and string minLength/maxLength/pattern before applying constraints.
- Reject contradictory bounds and invalid lengths as schema errors.
- Never let malformed internal schema metadata raise during argument validation.
- Keep error output bounded and do not disclose argument values.

## Validation

- Use direct schema test seams for wrong metadata types and contradictory bounds.
- Confirm valid catalog schemas still pass catalog-wide supported-keyword checks.
- Run adapter/schema tests, full suite, safe regression, and package readiness.
