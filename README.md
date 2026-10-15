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
pip install -e ".[lint]"    # 代码检查：ruff（版本与 CI 一致）
```

提交前可以在仓库根目录运行 `ruff check .` 和 `ruff format .`，规则和格式设置写在 `pyproject.toml` 里，CI 的 lint 任务运行 `ruff check .` 和 `ruff format --check .`。整仓库格式化的提交记在 `.git-blame-ignore-revs`，`git blame --ignore-revs-file .git-blame-ignore-revs` 可以跳过它。

HTML 渲染（`html-render`）额外需要 Node.js 18 及以上、Microsoft Edge 和 Playwright：

```bash
npm install                 # 在仓库根目录安装 playwright
```

脚本通过 `WPS_AGENT_NODE` 与 `WPS_AGENT_EDGE` 环境变量定位 `node` 和 `msedge`，未设置时从 `PATH` 查找。

渲染脚本 `html_render_playwright.cjs` 通过 `require('playwright')` 解析依赖：从源码目录（`pip install -e .`）运行时会向上找到仓库根的 `node_modules`；如果以 wheel 方式安装，请把 `NODE_PATH` 指向安装了 `playwright` 的 `node_modules` 目录。

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

## 退出码与失败检测

命令失败时，默认仍然只在 stdout 输出 JSON 信封（`ok: false`、`errors`），进程退出码为 `0`；这是为了兼容已有调用方，**不要只靠退出码判断成败**，请解析信封里的 `ok`。需要用退出码表示失败的脚本，加上 `--strict-exit`（可放在子命令前或后）：失败时退出码为 `1`，成功仍为 `0`。MCP 工具调用不受影响，`isError` 与信封中的 `ok` 一致。参数解析错误由 argparse 以退出码 `2` 结束。

```bash
wps-agent --strict-exit backup-document --document-id doc_xxx --request-id r1 || echo "failed"
```

## 文档被占用

文档被另一个句柄持有时（多半是在 WPS 中打开），读写命令都会在改动任何内容之前拒绝执行，错误码统一为 `DOCUMENT_HELD_OPEN`。这时没有写入、保存或关闭任何东西。请在 WPS 中保存或关闭该文档后重试。

无法判断文件是否被占用时（例如探测本身被拒绝），命令同样会保守地拒绝，但错误码是 `COM_OPERATION_FAILED`，因为这种情况并不能证明文件被占用。其他原因导致的身份读取失败仍然返回 `DOCUMENT_IDENTITY_UNAVAILABLE`。

## 修改失败与回滚

修改类命令在写入前先创建备份。如果命令在写入之后失败（读回的值与写入的不一致、源文件校验失败，或命令抛出异常），而文件已经被改动，CLI 会从这份备份原子地恢复文件，并核对恢复后的哈希与备份一致。此时信封里会有：

- `MUTATION_ROLLED_BACK`：文件已恢复。`data.rollback.performed` 为 `true`，`data.rollback.open_in_wps` 表示文档在 WPS 中是否仍然打开（`true`、`false`，无法检查时为 `null`）。
- `MUTATION_ROLLBACK_FAILED`：自动恢复失败，信封里给出需要用于手动恢复的备份路径，请用 `restore-backup` 处理。
- `MUTATION_ROLLBACK_BLOCKED`：WPS 持有文件，自动恢复被文件锁拒绝（Windows 上为拒绝访问）。文件仍保留被拒绝的写入值。请先在 WPS 中不保存地关闭该文档，再用信封里给出的备份路径执行 `restore-backup`；也可以给 `restore-backup` 加 `--close-in-wps`，让它在 WPS 里没有未保存改动时替你不保存地关闭该文档再恢复（有未保存改动时会拒绝，返回 `DOCUMENT_HAS_UNSAVED_CHANGES`）。

文件未被改动的失败不会回滚，原有错误照常返回。

限制：

- WPS 本身的保存不是原子的。回滚只保证文件恢复到修改前的内容，不改变 WPS 中已经打开的文档。如果 `open_in_wps` 为 `true` 或 `null`，请在 WPS 中不保存地关闭文档或重新加载，否则 WPS 可能把被拒绝的内容写回去。
- 恢复会覆盖备份之后、且不是通过本 CLI 做的修改。
- 命令抛出异常且账本中没有对应备份记录时，异常照常抛出；请用 `mutation-request-inspect` 检查该请求后再重试。
- 当前回滚路径只有离线测试覆盖，尚未在真实 WPS 上验证。

## WPS 实例与已打开文档

读写文件的 COM 命令（表格/文字/演示的变更与检查、冒烟与转换）取得 WPS 时**先附着到正在运行的实例**（GetActiveObject 语义），只有没有运行中的实例时才 `New-Object` 启动一个。

- 只有脚本自己启动的实例才会隐藏窗口、`Quit()`（且仅在没有其他文档时）；附着到的实例永不 `Quit()`，不改窗口可见性，临时关闭的 `DisplayAlerts` 等设置会在结束时还原。
- 目标文档已在该实例中打开时，不会被关闭；有未保存修改的表格/文字文档拒绝变更。**演示文稿**在已打开时一律拒绝变更（WPS 不能可靠报告演示的未保存状态），请先关闭。
- 冒烟/转换命令的输入文档已在 WPS 中打开时同样拒绝，避免被另存为其他名称或关闭。
- 路径比较会把 `\\localhost\C$\...`、`\\<本机名>\C$\...` 与 `\\?\` 前缀归一为本地路径，并在 Windows 上展开 8.3 短路径。
- 文档**尚未打开**时，脚本必须在用户的 WPS 里打开它才能读写，因此附着模式下它会在用户的实例里短暂出现（窗口可能一闪），结束后只关闭**自己打开的**那份。这一点无法完全避免（COM 只能通过打开文档来读写）。**WPS 对已打开的文档再调 `Open()` 会静默把它从磁盘重载**（脚本关闭了弹窗，ET 不会询问），内存里未保存的修改随之丢失，之前拿到的对象也会变成空壳；`Count` 不增加。所以脚本不会对可能已打开的文件调用 `Open()`：先在集合里再查一次（用户可能在调用方检查之后打开了它），再对文件做一次**独占文件锁探测**（会修改文档的命令要求独占访问，任何其它句柄都算冲突；只读命令只要求能与其它读者并存，写入者或独占持有者算冲突）。按已有观察 WPS 通常对它打开的文档持有（常为独占的）文件句柄，探测遇到共享冲突就拒绝，并说明"文件被另一个句柄占用，多半是在 WPS 中打开；未调用 `Open()`，因为它会静默重载并丢掉未保存的修改"，此时没有写入、保存或关闭任何东西。无法探测的路径（拒绝访问、路径异常等）同样保守拒绝并说明原因；文件不存在则交给 `Open()` 报错。代价：别的程序（同步盘、杀毒、预览）占着文件时会被误拒，错误信息里已写明，保存/关闭后重试即可。探测与 `Open()` 之间仍有极短窗口：如果文档正好在这一瞬间被打开，`Open()` 之后发现集合数量没有增加，会拒绝所有会改文档的命令，错误信息如实说明"`Open()` 已被调用，未保存的修改可能已经丢失"；只读 `spreadsheet-inspect` 仍返回读到的值（来自已保存的文件），并在 `warnings` 里给出同样的提示。探测是否真能拦住真实 WPS 持有的文档，**尚待在真实 WPS 上复测确认**（仓库 PR #8 的 `scripts/real_wps_verify_c2/c2-post-open.ps1`）。`com-smoke` 也走同一个 PowerShell 脚本和同样的探测；以前装了 pywin32 时它走一条没有探测的 pywin32 分支，已移除。
- `spreadsheet-inspect` 的强制全量重算（`CalculateFullRebuild`）会重算该实例里**所有**已打开的工作簿，并可能让用户的文档变成"已修改"，所以只在脚本自己启动的实例里执行。附着到用户实例时跳过重算，返回 WPS 当前显示的值，结果里 `calculation_performed_in_memory=false`、附带 `recalculation_skipped_reason`，`cache_matches_recalculated` 与 `cache_mismatch_count` 为 `null`（没有比较已保存缓存）。
- `GetActiveObject` 只能取到一个实例。同一组件有**多个带主窗口的 WPS 进程**（当前用户会话里 `wps`/`et`/`wpp` 进程且 `MainWindowHandle` 非 0 的个数大于 1）、且目标文档不在已附着的实例里时，无法判断文档是否在另一个实例中打开，因此变更命令（含演示和冒烟/转换）会拒绝，错误信息里列出被计入的进程 PID 和窗口标题；请先关闭多余的 WPS 窗口。只是多出**没有主窗口的后台/辅助进程**（`wps` 常见多个）时不拒绝，只在命令返回的 `data.warnings` 里提示（所有变更命令、`spreadsheet-inspect` 与冒烟/转换命令的返回信封都带该字段，MCP 输出相同）（因为隐藏实例里的文档无法被排除）。确认安全时可设置环境变量 `WPS_AGENT_ALLOW_MULTI_INSTANCE=1` 完全跳过。文档已在附着实例里打开时不受影响，只读的 `spreadsheet-inspect` 也不检查。进程名按 ProgID 推断（Writer→`wps`、表格→`et`、演示→`wpp`）；没有遍历 ROT 去匹配其他实例（未经真实 WPS 验证，风险较大）。已知盲区：没有主窗口的隐藏实例不会被计入。
- **常规打开的 WPS（P5-011 发现，Phase 6 处理）**：在 WPS 12.8.2.18913 上，双击 `.docx` 这样常规打开的 WPS 文字（`wps.exe "%1"`）不注册 `kwps.Application`，`GetActiveObject` 拿不到它；用 `wps.exe /Automation` 启动的文字可以拿到。表格在 P4-011 里常规打开是能看到的；演示还没有验证。所以 `GetActiveObject` 拿不到时，已打开文档命令会再查运行对象表（ROT）：如果有本组件扩展名的文档登记在里面，就通过它的 `Application` 附着（只认名字或路径里带 WPS/Kingsoft/金山 的程序，不会附着到别的办公软件）。查 ROT 只读取已经登记的对象，不会启动 WPS。还是拿不到、但本组件有带窗口的 WPS 进程时，返回 `WPS_INSTANCE_NOT_AUTOMATABLE`，错误信息说明原因，并给出处理办法：保存后关闭该组件的所有窗口，再用 `wps.exe /Automation "<文档路径>"` 重新打开。不再报成 `NO_RUNNING_WPS_INSTANCE`。`open-documents` 在列出其他组件文档的同时，用 `data.not_automatable` 和 `data.warnings` 标出拿不到的组件。ROT 这条路能否拿到双击打开的文字，要等 Windows 实测（P6-002、P6-004）。
- 这些行为只有 pwsh 假 COM 测试覆盖；真实 WPS 上的复测步骤见 PR 说明。

## 测试

```bash
pip install -e ".[test]"
PYTHONPATH=src python3 -m unittest discover -s tests
```

必须先安装 `test` extra（`python-docx`、`Pillow`、`pypdfium2`、`openpyxl`、`python-pptx`）；缺少这些依赖时，相关测试模块会在导入阶段报错，而不是被跳过。

在没有 WPS 的环境中，依赖 COM 的用例会被跳过。要运行 PowerShell 假 COM 对象用例和生成脚本的语法检查，设置 `WPS_TEST_PWSH` 指向 `pwsh` 可执行文件（PowerShell 7 即可，Linux/macOS/Windows 均可）。

持续集成见 `.github/workflows/tests.yml`：Python 3.10 与 3.12 各跑一遍完整单测，另有一个带 `pwsh` 的任务运行假 COM 用例；真实 WPS 回归需要交互式 Windows 运行器，见 [docs/REGRESSION_CI_HANDOFF.md](docs/REGRESSION_CI_HANDOFF.md)。

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
- 版本与发布：[docs/RELEASING.md](docs/RELEASING.md)、[CHANGELOG.md](CHANGELOG.md)
- 转换能力：[docs/CONVERSION_MATRIX.md](docs/CONVERSION_MATRIX.md)；WPS 版本兼容：[docs/COMPATIBILITY_MATRIX.md](docs/COMPATIBILITY_MATRIX.md)
- 代码审查：[批次 1-2](docs/CODE_REVIEW_BATCH_1_2.md)、[批次 3](docs/CODE_REVIEW_BATCH_3.md)、[批次 4-5](docs/CODE_REVIEW_BATCH_4_5.md)、[批次 6](docs/CODE_REVIEW_BATCH_6.md)
- 阶段报告：`docs/PHASE*.md`；迭代流水记录（已归档）：`docs/archive/P3_*.md`、`docs/TASK_BOARD.md`（按迭代追加，是历史记录，可能提到已删除的命令，见批次 6 报告 G-07）

## 当前阶段

- Phase 0/1/2: 已完成可行性验证、核心 CLI、恢复能力和 MCP server 原型
- 已实现: 环境探测、WPS ProgID 注册检测、结构化响应、任务清单、文档注册、备份/恢复、Writer/Spreadsheet/Presentation 修改命令、MCP adapter/server、回归套件和本地复现脚本
- MCP: legacy `2025-11-25` initialize 生命周期、分页工具发现、ping、参数/schema 校验和配置客户端持久 stdio 审计；审计会校验工具描述/schema，并限制子进程输出，当前工具面 85 项
- 最近验证: 默认测试套件共 1021 项，Linux 无 WPS 环境下全部通过，157 项跳过（需要真实 WPS 或 PowerShell 的用例；装了 pwsh 时只跳过 69 项）；MCP adapter 会在参数比较前校验 schema 约束元数据
- 当前实测: WPS Writer、Spreadsheets、Presentation 均已通过 PowerShell COM fallback 完成打开、保存副本和关闭；表格公式计算验证和 DOCX 到 PDF 转换验证已通过
- Phase 1: 已完成 release candidate 审计，详见 `docs/PHASE1_RELEASE_CANDIDATE_REPORT.md`
- Phase 3: 已完成，5 项出口标准均已满足，证据见 `config/project_plan.json`。原子事务有一个例外：WPS 打开着文档时自动回滚被文件锁拒绝，需按提示恢复（Phase 4 起可用 `restore-backup --close-in-wps` 在 CLI 内完成）。遗留的三项 Windows 验证已在 Phase 4 完成（`scripts/real_wps_verify_remaining/RESULTS-82c7a88.md`）
- Phase 4: 已完成（多环境与 Agent 工作流就绪），6 项出口标准均已达成，例外见 `docs/PHASE4_PLAN.md` 开头：兼容矩阵只有一个 WPS 版本（12.8.2.18913），安装检查不是在全新机器上做的
- Phase 5: 已完成（首个正式版本与覆盖扩展），4 项出口标准均已达成：85 个工具的失败都能被 Agent 看到，评测增至 19 个任务，`v0.2.0` 已发布到 GitHub Release（只装 wheel 即可跑 safe 档回归）。例外和遗留缺口（P5-010 第二个 WPS 版本、P5-011 常规打开的 WPS 文字不注册 COM）见 `docs/PHASE5_PLAN.md` 开头
- 当前 Phase 6（active）: 用户打开的文档，出口标准与任务见 `docs/PHASE6_PLAN.md`，`wps-agent tasks --phase phase6` 可列出任务

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
python -m wps_ai_agent_cli html-editable --input page.html --output page.xlsx --format xlsx
python -m wps_ai_agent_cli html-editable --input deck.html --output deck.pptx --format pptx
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
