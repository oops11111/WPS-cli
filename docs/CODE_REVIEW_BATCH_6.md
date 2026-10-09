# 代码审查报告：批次 6（工程化与仓库卫生）

范围沿用 `CODE_REVIEW_BATCH_3_6.md`：G-02 到 G-07，以及批次 1 到 2 遗留的 F-12、F-13。环境与限制同前：Linux，没有 WPS、真实 Edge 和 Playwright。

## 处理结果

| 编号 | 状态 | 说明 |
| --- | --- | --- |
| F-12、F-13 | 已在此前完成 | `--strict-exit` 与 resolver 注入，见 `CODE_REVIEW_BATCH_1_2.md` 修复状态 |
| G-06 | 已完成 | 见下 |
| G-05 | 部分完成 | 补全 `README.md`，未归档流水文档 |
| G-04 | 只做盘点，未删除 | 见 `ARTIFACT_INVENTORY.md` |
| G-02 | 两步完成，未拆模块 | 命令分发改为 `COMMAND_HANDLERS` 注册表，`build_parser` 按域拆成 9 个函数并移到 `cli_parser.py`，处理函数仍在 `cli.py`，见下 |
| G-03 | 未做 | 大型重构，需要单独的计划与确认 |
| G-07 | 未做 | 需要先决定哪些命令对用户有价值 |

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

盘点结果见 `docs/ARTIFACT_INVENTORY.md`。要点：

- `artifacts/recovery-drill/p3-184-extracted/` 是同步包的完整解压副本，302 个文件，只有一份文档提到它。
- 回归结果按时间戳累积了 277 份（`safe` 与 `release`），命令只读最新一份。
- `artifacts/regression/wps/` 是真实 WPS 的证据，不能重新生成，必须保留。
- 没有删除任何文件。删除是不可逆的仓库历史变更，应由你确认候选清单后执行。

## G-02：命令分发注册表与解析器拆分

`_run_command` 原来是 85 路 if/elif，约 530 行，每个分支内联了参数到 `*_response` 的映射。现在：

- 每个分支原样搬成模块级函数 `_handle_<command>(args, request_id, output_stream)`，函数体逐字保留（由 AST 脚本机械生成，没有手改业务逻辑），最后返回 `response`。
- `COMMAND_HANDLERS` 把命令名映射到处理函数，`_run_command` 只做解析、查表、输出和退出码。
- `mcp-server` 处理函数返回整数退出码（它自己写 stdout），`_run_command` 遇到整数直接返回。
- 新增 `tests/test_cli_dispatch.py`：解析器里的命令集合必须与注册表完全一致；信封输出与 `mcp-server` 的退出码路径各一个用例。以后新增命令忘记注册会立刻失败。

这一步没有移动文件，也没有改变任何命令的行为，`cli.py` 行数反而略增（4244 行）。它的价值是把后续按域拆成 `cli/` 子模块变成纯搬运：处理函数可以整组移走，注册表按域合并。`build_parser` 也已拆分：公共部分（程序名、`--request-id`、子命令容器）留在 `build_parser`，其余按域拆成 9 个 `_add_<域>_commands(subparsers)` 函数（环境与状态、转换、文档、操作与任务、MCP、回归与发布、文件扫描、表格、演示）。拆分用脚本在语句边界切分，各域之间除 `parser` 与 `subparsers` 外没有共享变量（用 AST 检查过）。验证：拆分前后递归导出全部 85 个子解析器的参数（名称、默认值、类型、选项、帮助文本、顺序），哈希完全一致。

这 9 个函数和 `build_parser` 已移到独立模块 `cli_parser.py`（843 行），`cli.py` 通过 `from .cli_parser import build_parser` 继续导出，`security_audit` 等原有导入路径不变。解析器只依赖 `DEFAULT_MCP_CATALOG_GUARD` 与 `DEFAULT_SYNC_PACKAGE` 两个常量，所以搬运没有副作用；搬运后同一哈希校验仍然一致。`cli.py` 降为 3522 行。

`_handle_*` 处理函数和 `*_response` 函数没有搬走。原因：`tests/test_cli.py` 等用例通过 `patch("wps_ai_agent_cli.cli.<名称>")` 打桩，名称解析发生在 `cli` 模块命名空间。把处理函数移到其他模块会让这些打桩失效，必须同步改写测试，这样"测试不变即无回归"的证据就没有了。要继续拆分，建议先让处理函数通过 `cli` 模块属性访问依赖，或者逐域改写打桩目标并分别评审。

## 未处理项说明

- G-03（8 个超过 150 行的函数）：`_run_*_com` 系列的 PowerShell 样板重复，需要逐个确认 COM 行为不变，没有真实 WPS 无法验证。
- G-07（约 20 个自我汇报型模块）：把它们从 MCP 目录移出会改变工具数量，牵动 `config/mcp_catalog_guard.json`、回归清单和多份文档，且对使用者是否可见是产品决策。

## 验证

见提交时的测试输出：`PYTHONPATH=src python3 -m unittest discover -s tests`，以及 `mcp-catalog-drift`、`documentation-freshness`、`security-audit`。
