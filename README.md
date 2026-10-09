# WPS AI Agent CLI

面向 Agent 的 WPS Office 控制 CLI。所有命令输出统一的 JSON 信封（`ok`、`data`、`validation`、`errors`、`warnings`），并可通过内置 MCP 服务器暴露为 MCP 工具。

- 读取、检查文档（Writer、表格、演示）不需要 WPS，可在任何平台运行。
- 修改文档、转换、冒烟测试通过 WPS COM 自动化完成，只能在装有 WPS 的 Windows 上运行。
- 修改类命令带备份、`--request-id` 幂等账本和源文件身份校验。

## 安装

要求 Python 3.10 及以上。

```bash
pip install -e .            # 核心运行时，依赖 openpyxl
pip install -e ".[wps]"     # Windows：pywin32
pip install -e ".[html]"    # HTML 可编辑转换：python-docx
pip install -e ".[test]"    # 运行测试所需的全部依赖
```

HTML 渲染（`html-render`）额外需要 Node.js 18 及以上、Microsoft Edge 和 Playwright：

```bash
npm install                 # 在仓库根目录安装 playwright
```

脚本通过 `WPS_AGENT_NODE` 与 `WPS_AGENT_EDGE` 环境变量定位 `node` 和 `msedge`，未设置时从 `PATH` 查找。

## 快速开始

```bash
wps-agent inspect-env                       # 检查 OS、pywin32、WPS COM 注册
wps-agent mcp-tools                         # 列出 MCP 工具目录
wps-agent open-documents                    # 列出 WPS 中已打开的文档（需要 Windows 与 WPS）
wps-agent mcp-server                        # 启动 stdio MCP 服务器
```

从源码目录运行，不安装：

```bash
PYTHONPATH=src python3 -m wps_ai_agent_cli inspect-env
```

MCP 客户端配置见 [docs/MCP_SERVER_CLIENT_CONFIG.md](docs/MCP_SERVER_CLIENT_CONFIG.md)。

## 测试

```bash
pip install -e ".[test]"
PYTHONPATH=src python3 -m unittest discover -s tests
```

在没有 WPS 的环境中，依赖 COM 的用例会被跳过。要运行 PowerShell 假 COM 对象用例，设置 `WPS_TEST_PWSH` 指向 `pwsh` 可执行文件。

## 目录

| 路径 | 内容 |
| --- | --- |
| `src/wps_ai_agent_cli/` | CLI、MCP 适配器与服务器、各文档域的实现 |
| `tests/` | 离线单元测试，COM 部分用假对象 |
| `config/` | MCP 目录漂移守卫、回归清单 |
| `fixtures/` | 测试与回归使用的文档夹具 |
| `artifacts/` | 回归、恢复演练等运行产物，已清理到只保留真实 WPS 证据与最新结果，见 [docs/ARTIFACT_INVENTORY.md](docs/ARTIFACT_INVENTORY.md) |
| `scripts/` | 夹具构建脚本与 Windows 辅助脚本 |
| `docs/` | 设计、PRD、阶段报告、审查报告 |

## 文档索引

- 产品需求：[docs/WPS_AI_Agent_CLI_PRD_v1.2.docx](docs/WPS_AI_Agent_CLI_PRD_v1.2.docx)、[docs/PRD_V1_2_OPEN_DOCUMENT_OPERATIONS.md](docs/PRD_V1_2_OPEN_DOCUMENT_OPERATIONS.md)
- 路线与任务：[docs/ROADMAP.md](docs/ROADMAP.md)、[docs/TASK_BOARD.md](docs/TASK_BOARD.md)
- MCP：[docs/MCP_TOOL_SCHEMA_DRAFT.md](docs/MCP_TOOL_SCHEMA_DRAFT.md)、[docs/MCP_SERVER_CLIENT_CONFIG.md](docs/MCP_SERVER_CLIENT_CONFIG.md)
- 回归与 CI：[docs/REGRESSION_MANIFEST.md](docs/REGRESSION_MANIFEST.md)、[docs/REGRESSION_CI_HANDOFF.md](docs/REGRESSION_CI_HANDOFF.md)、[docs/TEST_STRATEGY.md](docs/TEST_STRATEGY.md)
- 转换能力：[docs/CONVERSION_MATRIX.md](docs/CONVERSION_MATRIX.md)
- 代码审查：[批次 1-2](docs/CODE_REVIEW_BATCH_1_2.md)、[批次 3](docs/CODE_REVIEW_BATCH_3.md)、[批次 4-5](docs/CODE_REVIEW_BATCH_4_5.md)、[批次 6](docs/CODE_REVIEW_BATCH_6.md)
- 阶段报告：`docs/PHASE*.md`；迭代流水记录：`docs/P3_*.md`、`docs/TASK_BOARD.md`（按迭代追加，是历史记录，可能提到已删除的命令，见批次 6 报告 G-07）

## 当前阶段

- Phase 0/1/2: 已完成可行性验证、核心 CLI、恢复能力和 MCP server 原型
- 已实现: 环境探测、WPS ProgID 注册检测、结构化响应、任务清单、文档注册、备份/恢复、Writer/Spreadsheet/Presentation 修改命令、MCP adapter/server、回归套件和本地复现脚本
- MCP: legacy `2025-11-25` initialize 生命周期、分页工具发现、ping、参数/schema 校验和配置客户端持久 stdio 审计；审计会校验工具描述/schema，并限制子进程输出，当前工具面 70 项
- 最近验证: 默认测试套件共 566 项，Linux 无 WPS 环境全部通过（设置 WPS_TEST_PWSH 时 65 项跳过，否则 72 项跳过）；P3-306 adapter 会在参数比较前校验 schema 约束元数据
- 当前实测: WPS Writer、Spreadsheets、Presentation 均已通过 PowerShell COM fallback 完成打开、保存副本和关闭；表格公式计算验证和 DOCX 到 PDF 转换验证已通过
- Phase 1: 已完成 release candidate 审计，详见 `docs/PHASE1_RELEASE_CANDIDATE_REPORT.md`
- 当前 Phase 3: 本地工作区持续开发，不依赖远程 Git 工作流；当前下一任务为校验 MCP enum 唯一性语义，可用 `tasks --phase phase3 --status next` 查看

## 命令速查

```powershell
python -m wps_ai_agent_cli inspect-env
python -m wps_ai_agent_cli plan
python -m wps_ai_agent_cli tasks --phase phase0
python -m wps_ai_agent_cli tasks --phase phase2
python -m wps_ai_agent_cli tasks --phase phase3
python -m wps_ai_agent_cli com-smoke --component writer --input input.docx --output output.docx
python -m wps_ai_agent_cli calc-smoke --input input.xlsx --output output.xlsx
python -m wps_ai_agent_cli convert-smoke --component writer --input input.docx --output output.pdf --format pdf
python -m wps_ai_agent_cli html-render --input page.html --output page.pdf --format pdf
python -m wps_ai_agent_cli html-editable --input page.html --output page.docx
python -m wps_ai_agent_cli html-roundtrip-plan --input owned-page.html
python -m wps_ai_agent_cli html-controlled-import --input owned-page.html --output controlled.docx
python -m wps_ai_agent_cli html-roundtrip-verify --docx controlled.docx --mapping controlled.docx.wpsmap.json
python -m wps_ai_agent_cli register-document --component writer --path input.docx
python -m wps_ai_agent_cli documents
python -m wps_ai_agent_cli backup-document --document-id doc_xxx --request-id req-001 --dry-run
python -m wps_ai_agent_cli backup-document --document-id doc_xxx --request-id req-001
python -m wps_ai_agent_cli list-backups --document-id doc_xxx
python -m wps_ai_agent_cli restore-backup --document-id doc_xxx --backup-name backup-file.ext --request-id req-restore --dry-run
python -m wps_ai_agent_cli writer-replace --document-id doc_xxx --find "old text" --replace "new text" --dry-run --request-id req-002
python -m wps_ai_agent_cli writer-fill-bookmark --document-id doc_xxx --bookmark-name ClientName --text "Northwind" --dry-run
python -m wps_ai_agent_cli writer-replace --document-id doc_xxx --find "old text" --replace "new text" --request-id req-002
python -m wps_ai_agent_cli writer-replace --document-id doc_xxx --paragraph-index 1 --find "old text" --replace "new text" --request-id req-003
python -m wps_ai_agent_cli validate-document --document-id doc_xxx --contains "expected text"
python -m wps_ai_agent_cli validate-document --document-id doc_xxx --cell D4 --equals 18
python -m wps_ai_agent_cli snapshot-document --document-id doc_xxx
python -m wps_ai_agent_cli writer-structure --document-id doc_xxx --limit 50
python -m wps_ai_agent_cli writer-structure --document-id doc_xxx --section bookmarks --bookmark-name ClientName --include-text --text-limit 200
python -m wps_ai_agent_cli writer-structure-parity --run-wps
python -m wps_ai_agent_cli operation --request req-002
python -m wps_ai_agent_cli operations
python -m wps_ai_agent_cli task-status-create --task-id task_xxx --command batch-report --operation-request-id req-002
python -m wps_ai_agent_cli task-status-update --task-id task_xxx --state running --progress-percent 45
python -m wps_ai_agent_cli task-status --task-id task_xxx
python -m wps_ai_agent_cli task-statuses
python -m wps_ai_agent_cli task-recovery --task-id task_xxx
python -m wps_ai_agent_cli task-recovery-playbooks
python -m wps_ai_agent_cli mcp-tools
python -m wps_ai_agent_cli mcp-tools --category spreadsheet --mutates-document true
python -m wps_ai_agent_cli mcp-catalog-snapshot
python -m wps_ai_agent_cli mcp-catalog-drift
python -m wps_ai_agent_cli mcp-tool-schema --name wps_agent_spreadsheet_write
python -m wps_ai_agent_cli mcp-call --name wps_agent_tasks --arguments-json "{\"phase\":\"phase2\"}"
python -m wps_ai_agent_cli mcp-server --once-json "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\",\"params\":{}}"
python -m wps_ai_agent_cli mcp-smoke --expected-min-tools 70 --tool-name wps_agent_tasks
python -m wps_ai_agent_cli mcp-config-audit --config config/mcp_client_config.example.json --server-name wps-ai-agent-cli --expected-min-tools 70
python -m wps_ai_agent_cli regression-manifest --profile safe
python -m wps_ai_agent_cli regression-run --profile safe
python -m wps_ai_agent_cli cleanup-plan
python -m wps_ai_agent_cli scan-dir --path fixtures/phase0
python -m wps_ai_agent_cli batch-report --path fixtures/phase0
python -m wps_ai_agent_cli spreadsheet-read --document-id doc_xxx --sheet Sheet1 --range A1:B2
python -m wps_ai_agent_cli spreadsheet-sheets --document-id doc_xxx
python -m wps_ai_agent_cli spreadsheet-rename-sheet --document-id doc_xxx --old-name Sheet1 --new-name Archive --dry-run
python -m wps_ai_agent_cli spreadsheet-create-sheet --document-id doc_xxx --name Archive --index 2 --dry-run
python -m wps_ai_agent_cli spreadsheet-inspect --document-id doc_xxx --sheet Sheet1 --range A1:F1
python -m wps_ai_agent_cli spreadsheet-write --document-id doc_xxx --sheet Sheet1 --range A1:B2 --values-json "[[1,2],[3,4]]" --request-id req-004
python -m wps_ai_agent_cli spreadsheet-write --document-id doc_xxx --sheet Sheet1 --range A1:B2 --values-json "[[1,2],[3,4]]" --request-id req-004 --task-id task_sheet_write_001
python -m wps_ai_agent_cli spreadsheet-formula-write --document-id doc_xxx --sheet Sheet1 --range C1:C2 --formulas-json "[[\"=A1+B1\"],[\"=A2+B2\"]]" --expected-values-json "[[3],[7]]" --request-id req-005
python -m wps_ai_agent_cli presentation-replace --document-id doc_xxx --find "old title" --replace "new title" --request-id req-006
python -m unittest discover -s tests
```

如果没有安装为包，可以临时设置 `PYTHONPATH`:

```powershell
$env:PYTHONPATH = "src"
python -m wps_ai_agent_cli inspect-env
```

## 设计原则

- CLI 是主入口，MCP adapter 和 MCP server 原型复用同一核心逻辑；Phase 2 交付总结见 `docs/PHASE2_FINAL_HANDOFF_REPORT.md`，Phase 3 生产就绪计划见 `docs/PHASE3_PRODUCTION_READINESS_PLAN.md`，回归清单见 `docs/REGRESSION_MANIFEST.md`。
- 所有命令输出结构化 JSON，便于 Agent 解析。
- 修改类操作必须先有备份、请求 ID、状态查询和验证结果。
- Phase 0 只做可行性验证，不承诺未经实测的兼容性和成功率。
