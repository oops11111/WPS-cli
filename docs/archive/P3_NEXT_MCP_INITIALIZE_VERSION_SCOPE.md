# P3-276 MCP initialize version negotiation

Status: done. MCP tests: 35 passed; full suite: 445 passed/65 skipped.

## Goal

Ensure the legacy initialize handshake validates client input and selects a protocol version the server actually supports.

## Acceptance

- Define the server's supported protocol-version set and behavior for a matching client version.
- Verify missing, unsupported, and malformed client protocol versions against the MCP lifecycle rules; do not silently claim a version that was not selected.
- Preserve request IDs and return structured JSON-RPC errors for malformed initialize parameters.
- Cover handler behavior and a live stdio exchange, followed by a normal request when the connection remains usable.

## Boundaries

Keep the existing legacy initialize-based stdio contract. Do not add HTTP transport or alter desktop client configuration.

The selected legacy lifecycle behavior follows the [MCP lifecycle specification](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle#version-negotiation).
