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

## WPS 实例与已打开文档

读写文件的 COM 命令（表格/文字/演示的变更与检查、冒烟与转换）取得 WPS 时**先附着到正在运行的实例**（GetActiveObject 语义），只有没有运行中的实例时才 `New-Object` 启动一个。

- 只有脚本自己启动的实例才会隐藏窗口、`Quit()`（且仅在没有其他文档时）；附着到的实例永不 `Quit()`，不改窗口可见性，临时关闭的 `DisplayAlerts` 等设置会在结束时还原。
- 目标文档已在该实例中打开时，不会被关闭；有未保存修改的表格/文字文档拒绝变更。**演示文稿**在已打开时一律拒绝变更（WPS 不能可靠报告演示的未保存状态），请先关闭。
- 冒烟/转换命令的输入文档已在 WPS 中打开时同样拒绝，避免被另存为其他名称或关闭。
- 路径比较会把 `\\localhost\C$\...`、`\\<本机名>\C$\...` 与 `\\?\` 前缀归一为本地路径，并在 Windows 上展开 8.3 短路径。
- 文档**尚未打开**时，脚本必须在用户的 WPS 里打开它才能读写，因此附着模式下它会在用户的实例里短暂出现（窗口可能一闪），结束后只关闭**自己打开的**那份。这一点无法完全避免（COM 只能通过打开文档来读写）。如果脚本打开前一刻用户恰好打开了同一文档（集合数量没有增加），则按"已打开"处理，不会被关闭。
- `spreadsheet-inspect` 的强制全量重算（`CalculateFullRebuild`）会重算该实例里**所有**已打开的工作簿，并可能让用户的文档变成"已修改"，所以只在脚本自己启动的实例里执行。附着到用户实例时跳过重算，返回 WPS 当前显示的值，结果里 `calculation_performed_in_memory=false`、附带 `recalculation_skipped_reason`，`cache_matches_recalculated` 与 `cache_mismatch_count` 为 `null`（没有比较已保存缓存）。
- `GetActiveObject` 只能取到一个实例。同一组件有**多个 WPS 进程**（`wps`/`et`/`wpp` 进程数大于 1）、且目标文档不在已附着的实例里时，无法判断文档是否在另一个实例中打开，因此变更命令（含演示和冒烟/转换）会拒绝并给出明确错误；请先关闭多余的 WPS 窗口。确认安全时可设置环境变量 `WPS_AGENT_ALLOW_MULTI_INSTANCE=1` 跳过该检查。文档已在附着实例里打开时不受影响，只读的 `spreadsheet-inspect` 也不检查。进程名按 ProgID 推断（Writer→`wps`、表格→`et`、演示→`wpp`），没有遍历 ROT 去匹配其他实例（未经真实 WPS 验证，风险较大）。
- 这些行为只有 pwsh 假 COM 测试覆盖；真实 WPS 上的复测步骤见 PR 说明。

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
- 阶段报告：`docs/PHASE*.md`；迭代流水记录（已归档）：`docs/archive/P3_*.md`、`docs/TASK_BOARD.md`（按迭代追加，是历史记录，可能提到已删除的命令，见批次 6 报告 G-07）

## 当前阶段

- Phase 0/1/2: 已完成可行性验证、核心 CLI、恢复能力和 MCP server 原型
- 已实现: 环境探测、WPS ProgID 注册检测、结构化响应、任务清单、文档注册、备份/恢复、Writer/Spreadsheet/Presentation 修改命令、MCP adapter/server、回归套件和本地复现脚本
- MCP: legacy `2025-11-25` initialize 生命周期、分页工具发现、ping、参数/schema 校验和配置客户端持久 stdio 审计；审计会校验工具描述/schema，并限制子进程输出，当前工具面 70 项
- 最近验证: 默认测试套件共 573 项，Linux 无 WPS 环境全部通过（设置 WPS_TEST_PWSH 时 65 项跳过，否则 72 项跳过）；P3-306 adapter 会在参数比较前校验 schema 约束元数据
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
