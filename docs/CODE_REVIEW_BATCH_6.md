# 代码审查报告：批次 6（工程化与仓库卫生）

范围沿用 `CODE_REVIEW_BATCH_3_6.md`：G-02 到 G-07，以及批次 1 到 2 遗留的 F-12、F-13。环境与限制同前：Linux，没有 WPS、真实 Edge 和 Playwright。

## 处理结果

| 编号 | 状态 | 说明 |
| --- | --- | --- |
| F-12、F-13 | 已在此前完成 | `--strict-exit` 与 resolver 注入，见 `CODE_REVIEW_BATCH_1_2.md` 修复状态 |
| G-06 | 已完成 | 见下 |
| G-05 | 已完成 | 补全 `README.md`；`docs/P3_*.md` 已移至 `docs/archive/` |
| G-04 | 已完成 | 清理 631 个产物与根目录一个游离文件，`artifacts/` 从 653 个文件 13 MB 降到 22 个文件 404 KB，见 `ARTIFACT_INVENTORY.md` |
| G-02 | 已完成 | 注册表 + `cli_parser.py`；`_handle_*` 已移到 `cli_handlers.py`（经 `build_command_handlers(cli)` 绑定，保留对 `cli` 命名空间的打桩） |
| G-03 | 已完成（待真实 WPS 验证） | 操作路径 12 处 + inspect/parity/process-audit/capabilities 均走共享运行器；`convert_html_editable` / `export_controlled_html` 抽出路径校验辅助函数 |
| G-07 | 已完成 | 删除 15 个自我汇报命令与对应模块，MCP 工具 85 个降到 70 个，见下 |

## G-06：依赖声明

实验：屏蔽 `openpyxl` 后导入 `wps_ai_agent_cli.cli` 失败（`spreadsheet_ops`、`spreadsheet_inspect`、`spreadsheet_ranges` 在模块级导入它）。也就是说 `pip install .` 之后，`wps-agent` 在没有手动装 `openpyxl` 时连 `--help` 都跑不起来，而 `pyproject.toml` 写的是 `dependencies = []`。这比报告原来说的"依赖不完整"更严重，应视为打包缺陷。

修改：

1. `pyproject.toml`：`dependencies = ["openpyxl>=3.1"]`。`python-docx` 在函数内延迟导入，且失败时返回 `CONVERTER_UNAVAILABLE`，保留在 `html` extra。
2. 删除 `[tool.unittest]`，unittest 不读取它。
3. 新增根目录 `package.json`，声明渲染脚本需要的 `playwright`。`html_render_playwright.cjs` 位于 `src/wps_ai_agent_cli/`，Node 会向上查找到仓库根的 `node_modules`，源码目录运行时有效。通过 `pip install` 安装到 site-packages 后找不到这份 `node_modules`，需要设置 `NODE_PATH` 或全局安装 Playwright。这一点未在真实环境验证，README 只描述了源码目录的方式。
4. `.gitignore` 增加 `node_modules/`。
5. 新增 `tests/test_packaging_metadata.py`：用 AST 扫描 `src/` 的模块级第三方导入，必须都在 `dependencies` 中声明；`[tool.unittest]` 不得回归；`package.json` 与渲染脚本的 `require` 保持一致。以后新增模块级第三方导入会让测试失败，提醒同步 `pyproject.toml`。

## G-05：README 与文档

`README.md` 原来只有一行标题。现在包含安装各 extra、Node 与 Edge 依赖、快速开始、测试、目录说明和文档索引。

没有把 112 个 `P3_*.md` 流水文档移到 `docs/archive/`：`documentation_freshness`、`TASK_BOARD.md` 和 `P3_*` 文档之间互相引用路径，移动需要同步检查，收益只是整洁，风险不为零，留待确认。

## G-04：仓库产物

清理已执行，结果与保留规则见 `docs/ARTIFACT_INVENTORY.md`。要点：删除 `p3-184-extracted` 解压副本、三个同步包 zip、被后续通过结果取代的回归运行、较早的一致性审计结果，以及根目录的 `smoke_writer_copy.docx`；保留真实 WPS 的回归证据、最新结果、失败运行（按 CI 交接文档的保留规定）和 `p3-181-final`。删除的文件都在 git 历史中。

## G-07：删除自我汇报模块

范围按 `CODE_REVIEW_BATCH_3_6.md` 的 G-07 清单，并包含只为它们服务的下游：

- 模块（15 个）：`project_status`、`workspace_health`、`local_handoff`、`validation_runbook`、`documentation_freshness`、`regression_history`、`regression_evidence`、`recovery_drill_evidence`、`sync_package_inspect`、`sync_package_summary`、`sync_package_manifest`、`sync_package_coverage`、`sync_package_readiness`、`cloud_sync`、`artifact_retention`。
- 命令与 MCP 工具（15 个）：`project-status`、`workspace-health`、`local-handoff-summary`、`validation-runbook`、`documentation-freshness`、`regression-history`、`regression-evidence`、`cloud-sync-package`、`sync-package-inspect|summary|manifest|coverage|readiness`、`local-release-gates`、`artifact-retention-summary`。`local-release-gates` 是把同步包、回归和就绪检查串起来的编排命令，所有步骤都依赖被删除的模块，所以一并删除。
- 配套修改：`cli.py` 的响应函数与处理函数、`cli_parser.py` 的子命令、`mcp_schema.py` 的工具、`regression.py` 的命令白名单、`config/regression_manifest.json`（删除 11 个场景，`release` 档现在为空）、`config/mcp_catalog_guard.json`（85 个工具降到 70 个，只读 63 降到 48，去掉 `sync` 分类，`project`、`maintenance`、`regression` 分类各自下调）、`scripts/local_repro_bundle.ps1`（去掉同步包步骤）、各文档中的工具数量，以及 15 个对应的测试文件。
- 文档：`docs/CLOUD_SYNC_READINESS_HANDOFF.md` 整篇描述被删除功能，已删除。`TASK_BOARD.md`、`PHASE3_RELEASE_READINESS_REFRESH.md` 加了历史记录说明，`REGRESSION_MANIFEST.md` 与 `REGRESSION_CI_HANDOFF.md` 更新了 release 档的描述。其余 `docs/P3_*.md` 是迭代流水记录，保持原样，README 里写明了它们是历史记录。
- 新增 `tests/test_mcp_schema.py` 中的断言：已删除的命令不得再出现在 MCP 目录里。

保留、没有删除的"自报"类命令，以及原因：

- `security-audit`、`mcp-catalog-drift`、`mcp-config-audit`、`mcp-smoke`：校验的是 MCP 目录与客户端配置，Agent 用户会用到，且 `security-audit` 在批次 4 已改为 schema 与解析器一致性检查。
- `regression-manifest`、`regression-run`、`performance-baseline`：回归与性能基线。
- `plan`、`tasks`：路线图与任务清单，是回归清单中的场景，`tasks.py` 是纯数据。
- `cleanup-plan`、`cleanup-approval-manifest`：产物清理的"先计划再批准"流程。

影响：

- `regression-run --profile release` 对随仓库发布的清单现在没有场景，会直接通过。这是空档位的自然结果，已在文档里写明；如果以后用它做发布门槛，需要先在清单里补上场景。
- 删除 `documentation_freshness` 后，文档里的工具数量不再有自动检查。本次已手动把 `MCP_SERVER_CLIENT_CONFIG.md`、`MCP_TOOL_SCHEMA_DRAFT.md`、`REGRESSION_MANIFEST.md` 与清单里的 85 改为 70，`mcp-catalog-drift` 仍然守护目录本身的数量。
- `regression-run --profile safe` 在 Linux 上仍有 1 个场景失败（`mcp-config-audit`，示例配置里是 Windows 路径），这是此前就存在的，与本次无关。

## G-02：命令分发注册表与解析器拆分

`_run_command` 原来是 85 路 if/elif，约 530 行，每个分支内联了参数到 `*_response` 的映射。现在：

- 每个分支原样搬成模块级函数 `_handle_<command>(args, request_id, output_stream)`，函数体逐字保留（由 AST 脚本机械生成，没有手改业务逻辑），最后返回 `response`。
- `COMMAND_HANDLERS` 把命令名映射到处理函数，`_run_command` 只做解析、查表、输出和退出码。
- `mcp-server` 处理函数返回整数退出码（它自己写 stdout），`_run_command` 遇到整数直接返回。
- 新增 `tests/test_cli_dispatch.py`：解析器里的命令集合必须与注册表完全一致；信封输出与 `mcp-server` 的退出码路径各一个用例。以后新增命令忘记注册会立刻失败。

这一步没有移动文件，也没有改变任何命令的行为，`cli.py` 行数反而略增（4244 行）。它的价值是把后续按域拆成 `cli/` 子模块变成纯搬运：处理函数可以整组移走，注册表按域合并。`build_parser` 也已拆分：公共部分（程序名、`--request-id`、子命令容器）留在 `build_parser`，其余按域拆成 9 个 `_add_<域>_commands(subparsers)` 函数（环境与状态、转换、文档、操作与任务、MCP、回归与发布、文件扫描、表格、演示）。拆分用脚本在语句边界切分，各域之间除 `parser` 与 `subparsers` 外没有共享变量（用 AST 检查过）。验证：拆分前后递归导出全部 85 个子解析器的参数（名称、默认值、类型、选项、帮助文本、顺序），哈希完全一致。

这 9 个函数和 `build_parser` 已移到独立模块 `cli_parser.py`（843 行），`cli.py` 通过 `from .cli_parser import build_parser` 继续导出，`security_audit` 等原有导入路径不变。解析器只依赖 `DEFAULT_MCP_CATALOG_GUARD` 与 `DEFAULT_SYNC_PACKAGE` 两个常量，所以搬运没有副作用；搬运后同一哈希校验仍然一致。`cli.py` 降为 3522 行。

`_handle_*` 处理函数和 `*_response` 函数没有搬走。原因：`tests/test_cli.py` 等用例通过 `patch("wps_ai_agent_cli.cli.<名称>")` 打桩，名称解析发生在 `cli` 模块命名空间。把处理函数移到其他模块会让这些打桩失效，必须同步改写测试，这样"测试不变即无回归"的证据就没有了。要继续拆分，建议先让处理函数通过 `cli` 模块属性访问依赖，或者逐域改写打桩目标并分别评审。

## G-03：PowerShell 运行样板去重

`writer_ops`、`presentation_ops`、`spreadsheet_ops` 中 12 个 `_run_*_com` 函数各自复制了约 25 行"写临时脚本、`subprocess.run`、清理、解析 JSON、拼错误"的样板，三种写法互不相同。现在全部走 `powershell_runner.run_powershell_script`，净减少约 345 行。

两种调用方式，分别保持原有契约：

1. 经 `guarded_com_mutation` 且原来让 `TimeoutExpired`/`OSError` 向上抛出的函数（Writer 三个、演示一个、表格写入与公式写入）：运行器新增 `raise_process_errors=True`，超时与启动失败仍然抛给 `guarded_com_mutation`，由它统一生成带 `timed_out` 的结果和 `mutation-request-inspect` 提示。
2. 原来自己捕获异常的六个表格工作表函数（重命名、新建、显隐、删除、复制、标签颜色）：用运行器默认行为。行为变化只有一处：超时原来返回通用的 `COM_OPERATION_FAILED` 且 `data` 为空，现在返回 `COM_OPERATION_TIMEOUT` 并带 `timed_out: true`，与其他命令一致。

保护这次改动的测试：`tests/test_wps_quit_guard.py` 会对这 12 个函数加上 `com_backend` 的 3 个函数逐个捕获生成的脚本，断言每个函数恰好运行一次脚本且只在 WPS 空闲时 `Quit()`；`tests/test_powershell_runner.py` 新增 `raise_process_errors` 与两种超时契约用例。因为这些函数不再自己导入 `subprocess`，两个测试的打桩目标改为全局 `subprocess.run`（作用相同）。

没有改的：`spreadsheet_inspect`、`writer_structure_parity`（8 个用例按其模块打桩）、`process_audit`、`capabilities` 的内联调用。它们是只读命令，错误处理方式各不相同，改动收益小。真实 WPS 上的行为未验证，包括 `-File` 参数与临时文件清理在 Windows 上与之前一致这一点；运行器与此前的实现完全相同，之前已在 `com_backend` 的三个函数上使用。

## 未处理项说明

- G-03 中超长的业务函数（`convert_html_editable` 262 行、`export_controlled_html` 244 行等）：没有拆分，纯结构调整收益小。重复的 PowerShell 样板已在上面的 G-03 一节处理。

## 验证

`PYTHONPATH=src python3 -m unittest discover -s tests`：505 个用例通过（用例数从 542 降到 505，减少的是被删除模块的测试）；设置 `WPS_TEST_PWSH` 后同样通过。`mcp-catalog-drift` 与 `security-audit` 通过。`documentation-freshness` 已删除，不再运行。

## 后续补完（原审查未改项）

| 编号 | 状态 | 说明 |
| --- | --- | --- |
| H-03 | 有意保留 | `table_count_preserved: false` 仍成功返回（与现有 WPS 归一化契约一致） |
| H-04 | 已完成 | `docx_table_cell_rich_content` 预检；默认拒绝，`--allow-rich-content` / `allow_rich_content` 可覆盖 |
| H-05 | 已完成 | `find_text` 超过 255 字符返回 `FIND_TEXT_TOO_LONG` |
| H-06 | 已完成 | 工作表限定与整列/整行范围给出明确 `INVALID_RANGE` 说明 |
| 渲染超时残留进程 | 已完成 | `html_render` 用进程组/`taskkill /T` 清理 Node+Edge |
| JS 下 WebSocket | 已完成 | Playwright 关闭/中止 WebSocket；结果带 `websocket_blocked: true` |

