# Phase 3 Production Readiness Plan

## Goal

Phase 3 的目标是把当前本地可用的 WPS + MCP 自动化底座推进到生产就绪：更强恢复能力、更严格安全边界、可重复回归测试、真实 Agent 端到端评测，以及后续 WPS 高级能力扩展。

## Workstreams

| Workstream | 目标 | 首批验收门槛 |
| --- | --- | --- |
| Regression suite | 把关键 CLI、MCP、WPS smoke 固化成可机器读取清单 | 每个场景有命令、输入、期望检查和证据字段 |
| Recovery hardening | 强化备份、恢复、事务边界和失败后处理 | 每个修改类命令有恢复路径和失败演练 |
| Security boundary | 审计本地文件访问、命令执行和 MCP 修改类工具暴露 | 修改类工具有 request_id、dry-run 或明确风险提示 |
| Performance baseline | 建立批量文件、快照和 MCP tools/list 的基线 | 输出耗时、文件数、失败数和资源观察点 |
| Desktop integration | 在目标 MCP desktop client 中完成真实连接审计 | 记录 client 配置、握手、tools/list、tools/call 证据 |
| Advanced WPS capability | 深化 Writer、Presentation、Spreadsheet 高级对象处理 | 新能力先有 fixture、dry-run、备份和验证 |

## Initial Risk Register

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| WPS COM 行为在不同版本上不一致 | 命令成功率和验证结果不稳定 | 用 capability probe、fixture smoke 和版本矩阵分层记录 |
| Windows Python launcher 指向 Store 占位符 | MCP client 无法启动 server | client config 使用已验证的绝对 Python 路径，并通过 `mcp-config-audit` 审计 |
| 修改类 MCP 工具被误调用 | 文档被意外修改 | 保留 request_id、backup、dry-run、task_id、recovery playbook |
| tools/list 输出增长过大 | 客户端加载变慢 | 后续增加分页或工具分组过滤策略 |
| 结构验证不足以证明视觉正确 | 格式回归漏检 | Phase 3 引入渲染级验证和差异报告 |

## Acceptance Gates

1. 所有 Phase 3 回归场景必须能由单条 CLI 命令或 manifest runner 执行。
2. 所有修改类场景必须包含备份证据、验证证据和恢复建议。
3. MCP 场景至少覆盖 `initialize`、`tools/list`、`tools/call`、config audit。
4. WPS 真机 smoke 必须标注组件、输入文件、输出文件、request_id 和后端。
5. 报告必须区分本机已验证能力与未完成的真实桌面客户端联调。

## First Next Task

`P3-002 Regression suite manifest and smoke matrix` 已完成，清单见 `config/regression_manifest.json`，说明见 `docs/REGRESSION_MANIFEST.md`。

`P3-003 Regression manifest WPS smoke execution`：

- 运行 `regression-run --profile wps --include-wps`。
- 记录真实 WPS Writer、Spreadsheet 和 conversion smoke 证据。
- 标记环境问题、输出文件和后续修复项。
