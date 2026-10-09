# 代码审查报告：批次 3 到 6

处理状态：批次 3 见 `CODE_REVIEW_BATCH_3.md`，批次 4 与 5 见 `CODE_REVIEW_BATCH_4_5.md`，批次 6 见 `CODE_REVIEW_BATCH_6.md`。G-01、G-04、G-06、G-07、G-08 已处理，G-02（命令注册表与解析器按域拆分，解析器已移到 cli_parser.py，处理函数尚未拆分）、G-03（PowerShell 样板去重）、G-05 部分处理。

范围：文档读写核心、CLI 与 MCP 层、HTML 转换与批处理、工程化与仓库卫生。

方法与限制同批次 1 与 2：Linux 环境，静态阅读加局部实验，没有 WPS。批次 3 与 4 的深度低于批次 1 与 2，只覆盖最高风险的切面，未逐函数审查 `spreadsheet_ops.py`、`writer_ops.py` 的全部业务分支。这两处只依赖现有 424 个用例的覆盖，没有额外验证。

## 发现清单

### G-01（P2）解析 OOXML 时没有解压大小限制，小文件可耗尽内存

位置：`document_text.py`、`writer_structure.py`、`presentation_text.py`、`html_roundtrip.py`、`spreadsheet_ops.py` 中约 30 处 `ET.fromstring(archive.read(name))`。

实验：构造一个 398 KB 的 docx，其 `word/document.xml` 解压后 400 MB（全是空格）。调用 `read_writer_structure` 时进程峰值内存约 1.6 GB，耗时约 2.5 秒。没有任何大小检查。

Python 3.12 自带的 expat 对实体膨胀有防护，外部实体也不会被解析，所以 XXE 和"十亿笑声"不是问题。实际风险只有解压膨胀。这个 CLI 的输入通常是用户自己的文档，所以优先级是 P2。但 Agent 可能处理来自邮件或下载的文件。

建议：抽出一个 `read_zip_part(archive, name, max_bytes)`，先检查 `ZipInfo.file_size`，超限返回结构化错误，替换全部 `archive.read` 调用。`spreadsheet_ops` 对 xlsx 用 `openpyxl` 读取，也有同类风险，可以在打开前检查压缩包总解压大小。

### G-02（P2）`cli.py` 过大且 `run` 是 523 行的 if/elif 链

位置：`cli.py` 共 3764 行。`build_parser` 单函数 772 行，`run` 单函数 523 行。

每个新命令要同时改三处（解析器、`*_response` 函数、`run` 的分发），而且 `run` 中大量重复的 `_with_optional_task_status(lambda: ..., task_id=..., tracked_command=..., operation_request_id=..., document_id=...)` 模板。批次 1 中的任务状态异常漏洞（F-01）正是这种模板里没有统一错误处理造成的。

建议：按命令域拆成 `cli/` 子模块（文档会话、Writer、表格、演示、HTML、MCP、回归和交付），用注册表把命令名映射到处理函数，`run` 退化为查表加统一异常处理。可以分多个小 PR 逐域迁移，每步用现有用例做回归。

### G-03（P2）超长函数集中在核心业务路径

按行数排序（均超过 150 行）：`html_editable.convert_html_editable`（256）、`html_roundtrip.export_controlled_html`（244）、`writer_structure.read_writer_structure`（228）、`document_text.docx_body_drawing_semantics`（226）、`presentation_ops._run_presentation_replace_com`（216）、`com_backend.run_spreadsheet_calc_smoke`（189）、`writer_ops._run_writer_replace_com`（181）、`writer_ops.writer_replace`（176）。

其中 `_run_*_com` 函数是"大段 PowerShell 字符串加 Python 样板"，约 20 处重复了落盘、执行、清理、JSON 解析的逻辑。批次 1 的 F-01 建议的共享 `run_powershell_script()` 可以同时解决这里的重复。

### G-04（P3）仓库中提交了大量产物

- `artifacts/` 共 653 个文件、13 MB，包含 3 个 zip、`p3-184-extracted/` 这类解压副本、`recovery-drill` 下的 308 个文件。
- 按内容哈希统计，`artifacts/` 与 `fixtures/` 中有 34 个文件是完全重复的副本。
- 这些产物既是测试夹具又是"证据"，但没有区分哪些被测试引用，哪些只是历史记录。`.gitignore` 里没有忽略 `artifacts/`。

建议：只保留被 `tests/` 或 `config/regression_manifest.json` 引用的夹具，把历史证据移到发布附件或单独的分支，并在 README 里说明产物的生成方式。清理前先用 `cleanup_plan` 产出候选清单。

### G-05（P3）文档冗余

`docs/` 有 128 个文件，其中 15 个是 `P3_POST_*_LOCAL_PACKAGE_REFRESH.md`，12 个是 `P3_NEXT_*_SCOPE.md`。它们是按迭代追加的流水记录，内容高度相似。`README.md` 只有一行标题，没有安装、运行、测试、目录说明。

建议：在 README 中补充快速开始（安装、`wps-agent inspect-env`、运行测试）、依赖说明（Windows、WPS、pywin32、Node 与 Playwright、Edge）、文档索引。流水记录归档到 `docs/archive/`，`documentation_freshness` 的检查对象同步调整。

### G-06（P3）依赖声明不完整

- `html_render_playwright.cjs` 依赖 `require('playwright')`，仓库里没有 `package.json`，也没有说明如何安装。
- 核心运行时没有依赖，但 `spreadsheet_ops`、`document_text` 实际需要 `openpyxl`、`python-docx`（`html` extra 只列了 `python-docx`）。PR #2 已补全 `test` extra，运行时 extra 仍需整理。
- `pyproject.toml` 里的 `[tool.unittest]` 不是 unittest 支持的配置，不起作用。

### G-07（P3）自我汇报型模块的维护成本

`project_status`、`workspace_health`、`local_handoff`、`validation_runbook`、`documentation_freshness`、`regression_history`、`sync_package_*`（6 个模块）、`recovery_drill_evidence`、`security_audit` 等约 20 个模块是项目对自身状态的审计与汇报，而不是对 WPS 的能力。它们各自带 CLI 命令、MCP 工具、文档和测试，增加了 `cli.py` 和 MCP 目录的体积。

`security_audit.py` 见 G-08。

建议：评估哪些对 Agent 用户有价值（回归、健康检查），把其余收敛为一个 `dev` 子命令组，不暴露为 MCP 工具。

### G-08（P2）`security_audit` 检查的是 schema 文案，不是行为，容易给出虚假的安全感

位置：`security_audit.py`。

7 项检查（`backup_or_protection_boundary`、`file_system_boundary_documented`、`idempotency_mentions_request_id` 等）通过在工具 schema 的 `description`、`safety_notes`、`idempotency` 字符串里搜索 "backup"、"protect"、"file"、"request_id" 等关键词来判定。它验证的是"文档里提到了"，不是"代码里做了"。

例如批次 1 发现的 F-01（超时导致任务卡死）、F-02（恢复非原子）、F-03（不校验备份）都不会被它发现，只要 schema 描述里写了 "backup" 就会通过。把它叫做 "security boundary audit" 并放进发布门槛，会让人误以为已经覆盖了行为层面的安全。

建议：改名为 schema 文案检查（例如 `mcp-schema-lint`），或补充行为类检查，比如对每个修改类工具的 mock 超时与失败注入用例，把"已验证的失败模式"作为门槛项。

## 已确认没问题的点

1. HTML 批处理（`batch_conversion.py`）：对符号链接目录、记录大小、文件数量、总输入字节数都有限制，请求记录用哈希命名，失败状态可回放。
2. 整个包中没有 `rmtree`、`os.remove` 等破坏性删除，清理相关模块（`cleanup_plan`、`cleanup_approval`、`artifact_retention`）只产出计划与清单，符合"先批准再执行"的设计。
3. `file_scan.py` 用 `rglob`，Python 3.12 下不会跟随符号链接目录。
4. `html_roundtrip.py`：对象 ID 有格式与唯一性校验，映射文件用 `os.link` 避免覆盖，导入失败时只在目标文件身份未变时才删除半成品。
5. MCP 层：目录快照与漂移守卫用例在装齐依赖后全部通过，批量取消用例也通过。

## 未覆盖

- `spreadsheet_ops.py` 与 `writer_ops.py` 的逐分支审查、`spreadsheet_ranges.py` 的 A1 解析边界。
- `mcp_server.py` 的 stdin 行大小限制与并发取消的竞态。
- `tasks.py`（2092 行）只有一个函数 `list_tasks`，其余全是任务清单数据，没有逻辑，不需要审查。

这些可作为下一轮审查对象。

> 更新：原「未改动」项中除 H-03（有意保留）外，已在后续提交中处理，见 `CODE_REVIEW_BATCH_6.md` 的「后续补完」一节。
