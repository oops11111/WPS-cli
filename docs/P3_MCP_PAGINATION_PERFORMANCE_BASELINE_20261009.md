# P3-264 MCP Pagination Performance Baseline

Date: 2026-10-09

## Environment and Method

- Runtime: Python 3.12.14, Windows 10.0.19045, local workspace.
- Catalog: 81 MCP tools, fixed page size 50, yielding 50 + 31 tools.
- Samples: 200 complete sequential traversals in one process. Each sample serialized each JSON-RPC response as compact UTF-8 JSON (`ensure_ascii=False`, compact separators) and measured handler plus serialization time with `perf_counter_ns`.
- The complete tool-name sequence was checked against the canonical schema order on every iteration; duplicate-free status was checked on every iteration.

## Results

| Measurement | p50 | p95 | Min | Max |
| --- | ---: | ---: | ---: | ---: |
| Page 1 handler + serialization | 2.647 ms | 3.487 ms | 2.592 ms | 7.372 ms |
| Page 2 handler + serialization | 2.385 ms | 2.962 ms | 2.339 ms | 6.288 ms |
| Full 2-page traversal | 5.078 ms | 6.726 ms | 4.966 ms | 13.672 ms |

| Page | Tools | Serialized JSON-RPC response |
| --- | ---: | ---: |
| 1 | 50 | 65,054 UTF-8 bytes |
| 2 | 31 | 41,965 UTF-8 bytes |

All 200 iterations matched catalog order exactly, traversed all 81 tools, and contained no duplicates. The measured values are local observations, not machine-independent thresholds or a desktop-client latency claim.

## Limitations

This isolates in-process request handling and compact JSON serialization. It excludes stdio transport, process startup, client parsing/rendering, and network latency. Real desktop-client behavior remains unverified; see `docs/P3_DESKTOP_MCP_CLIENT_AUDIT_20261009.md`.
