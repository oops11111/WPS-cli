# P3-267 Bound MCP Cursor Input Length

## Objective

Bound parsing work for the opaque cursor accepted by `tools/list`. A cursor generated for this static two-page catalog is short; arbitrarily long values should not reach base64 decoding.

## Contract

- Define a small explicit maximum encoded cursor length consistent with generated tokens (128 ASCII characters).
- Reject longer strings with JSON-RPC `-32602` before encoding or decoding them.
- Preserve omitted-cursor behavior and all valid first, continuation, and final-page responses.
- Preserve rejection of malformed, stale, and out-of-range cursors.

## Validation

Test just-below/at/above the limit as applicable, a very large cursor, valid catalog traversal, and stdio error serialization. Do not impose a machine-dependent timing assertion.
