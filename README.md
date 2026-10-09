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
