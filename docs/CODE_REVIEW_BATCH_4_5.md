# 代码审查报告：批次 4（CLI 与 MCP 层）和批次 5（HTML 转换与批处理）

范围划分沿用 `CODE_REVIEW_BATCH_3_6.md` 的顺序：批次 4 是 CLI 与 MCP 层，批次 5 是 HTML 转换与批处理。批次 6（工程化与仓库卫生）未处理。

方法：静态阅读加最小复现。Linux 环境，没有 WPS；为验证生成的脚本临时安装了 PowerShell 7，仅用于解析和假对象测试，不属于仓库。

阅读范围：`mcp_server.py`、`mcp_adapter.py`、`mcp_config_audit.py`、`mcp_smoke.py`、`security_audit.py`、`regression.py`、`html_render.py` 与 `html_render_playwright.cjs`、`html_editable.py`、`html_roundtrip.py`（解码入口）、`batch_conversion.py`。

## 批次 4：CLI 与 MCP 层

### H-10（P1，已修复）`mcp-config-audit` 可被用来执行任意命令

位置：`mcp_config_audit.py`。

审计会执行配置里的 `command` 加 `args`，只要求 `args` 里含 `mcp-server`。`wps_agent_mcp_config_audit` 是公开的 MCP 工具，`config` 路径由调用方给出。

复现：写一个配置，`command` 为 `/bin/sh`，`args` 为 `["-c", "touch /tmp/pwned; ...", "mcp-server"]`，通过 `call_mcp_tool("wps_agent_mcp_config_audit", {"config": ...})` 调用，`/tmp/pwned` 被创建。同理可用 `python -c`、额外环境变量（`PYTHONSTARTUP`）或指向自己目录的 `cwd` 与 `PYTHONPATH` 执行代码。这直接违反 PRD 2.4「不默认开放任意代码执行」。

修复：只执行本项目自己的启动行。命令必须是 Python 解释器，`args` 必须正好是 `-m wps_ai_agent_cli mcp-server`，`env` 只能含 `PYTHONPATH` 且必须解析到正在运行的这个包。不满足时新增检查 `launch_line_is_this_package` 失败，`smoke` 为 `null`，不执行任何命令。测试覆盖 shell、`python -c`、额外环境变量、外部包、外部 `cwd` 五种情况，并断言标记文件没有被创建。

### H-11（P1，已修复）`regression-run` 可通过自带清单运行任意 CLI 命令

位置：`regression.py`。

`regression-run --manifest` 会对清单里每个场景执行 `cli.run(command)`。该工具在 MCP 中被标记为非修改类，但自带清单可以运行 `restore-backup`、`writer-replace` 等修改类命令，也可以递归运行 `regression-run`。这是越过工具声明的权限提升。

修复：场景命令只能是随仓库发布的清单已使用的 22 个只读和冒烟命令（`REGRESSION_ALLOWED_COMMANDS`），其他命令返回 `REGRESSION_COMMAND_NOT_ALLOWED` 且不执行。测试检查白名单覆盖现有清单，并检查修改类、递归、空命令、类型错误的场景不会运行。代价：给默认清单新增使用新命令的场景时要同步更新白名单（已写入 `docs/REGRESSION_MANIFEST.md`）。

### H-12（P1，已修复）MCP 服务器会被一次错误参数或一次内部异常终止

位置：`mcp_adapter.py`、`mcp_server.py`。

复现：

1. `tools/call` 传 `table_index: "abc"`，适配器只检查必填和未知参数，直接交给 `cli.run`，argparse 报错后 `SystemExit(2)` 向上抛出。`SystemExit` 不是 `Exception`，服务器进程直接退出，整个 stdio 会话中断。
2. 字符串参数以 `-` 开头（例如 `text: "--dry-run"`）会被 argparse 当作标志，同样导致退出，或者在更坏的情况下改变其他标志的含义。
3. `call_mcp_tool` 之外的任何异常（例如 CLI 抛出未处理异常）会让 `serve_stdio` 的主循环抛出，服务器退出。

修复：

- 适配器按 schema 校验类型、整数范围和枚举（布尔必须是真正的布尔，整数不接受布尔），失败返回 `MCP_ARGUMENTS_INVALID`。
- 以 `-` 开头的字符串值改用 `--flag=value` 形式传递，只在这种情况下改变 argv，现有 argv 形态不变。
- `call_mcp_tool` 捕获 `SystemExit`（`MCP_CLI_ARGUMENTS_REJECTED`）和其他异常（`MCP_TOOL_EXECUTION_FAILED`）。没有用 `redirect_stderr`，因为它是进程全局的，HTML 批处理线程并发时会把 stderr 永久留在错误的对象上。
- `handle_mcp_request` 对 `tools/call` 兜底，返回 JSON-RPC `-32603`。

### H-13（P2，已修复）MCP 服务器行为不符合 JSON-RPC 通知语义，且没有请求大小限制

位置：`mcp_server.py`。

- 除 `notifications/initialized` 外，其他通知（例如 `notifications/cancelled`）会收到 `-32601` 错误响应，而通知不应有响应，会让客户端困惑。现在所有 `notifications/*` 都不响应。
- 每行请求没有大小上限，`for line in input_stream` 会把任意长的一行读进内存。现在上限 4 Mi 字符，超出的行被丢弃（读到换行为止），返回 `-32600` 且后续请求仍可处理。没有 `readline` 的可迭代流（测试用的假流）退回逐行迭代，行为不变。

### H-14（P2，已修复）`security-audit` 检查的是文案，容易给出虚假的安全感（原 G-08）

位置：`security_audit.py`。

没有改名（改名会改变 MCP 目录和基线），改为如实标注并补一项结构检查：

- 结果新增 `scope`、`behavioral_verification: false`、`scope_note`，CLI 摘要改为「Schema text and parser consistency audit」，MCP 工具描述同步说明这不是行为测试。
- 新增 `schema_matches_cli_parser`：对每个工具核对 schema 的属性与 CLI 子命令的 `--flag` 是否一一对应，必填、布尔、整数、数组类型是否一致。它覆盖全部 85 个工具，对修改类工具计入失败项。现状没有发现不一致。H-12 的参数校验正是依赖 schema 与解析器一致。

没有做：把超时注入、恢复失败等行为用例作为门槛项。这些仍然只由单元测试保证。

### 批次 4 其余观察（未改动）

- `mcp_smoke.py`：只对白名单内的只读命令允许带参数，写法稳妥，未发现问题。
- `mcp-call` 的递归保护只拦 `mcp-call` 与 `mcp-server`，在 H-11 修复后不再能经 `regression-run` 间接递归。
- G-02（`cli.py` 过大、`run` 是长 if/elif 链）本次未处理。它是可维护性问题，不是缺陷。建议按命令域分多个小 PR 迁移，每步用现有 529 个用例回归，避免与功能修复混在一起。

## 批次 5：HTML 转换与批处理

### H-15（P1，已修复）非 UTF-8 的 HTML 被静默转成乱码并报告成功

位置：`html_editable.py`、`html_roundtrip.py`。

两处都用 `utf-8-sig` 加 `errors="replace"` 读取。复现：一个 `<meta charset="gb2312">` 的 GBK 文件转换后，成功返回，DOCX 段落是 `��ã�����`。这个项目的用户以中文为主，GBK 或 GB2312 的 HTML 很常见，结果是静默的数据损坏。

修复：新增 `html_text.decode_html_bytes`，顺序为 BOM、严格 UTF-8、前 2 KiB 内声明的 charset、最后才是带替换的 UTF-8。最后一种情况在结果里加警告「text may be corrupted」，并返回 `source_encoding`。不做编码猜测。浏览器渲染路径（`html_render`）由浏览器自己处理编码，不受影响。

### H-16（P2，已修复）每次转换都带一个无意义的警告

`<document>`（解析器内部的合成根节点）被当成「不支持的元素」，每次转换都会出现 `Unsupported element <document> omitted or flattened to text.`。已排除根节点。

### H-17（P2，已修复）超链接允许 UNC 路径和控制字符

`_safe_link_target` 对没有 scheme 的值一律放行，`\\server\share\x` 会被写成可点击的超链接，点击时可能触发 SMB 认证泄露。现在含反斜杠或控制字符的目标一律不生成链接，并给出警告。

### H-18（P2，已修复）渲染结果发布存在覆盖竞态

位置：`html_render.py`。

先检查目标不存在，渲染完成后用 `rename` 发布。在 POSIX 上 `rename` 会静默覆盖渲染期间新出现的文件，与「绝不覆盖」的承诺不一致。已改为 `os.link`（目标已存在时失败）加清理临时文件，与 `html_editable`、批处理清单的做法一致。限制：不支持硬链接的文件系统（如 FAT、exFAT）上会返回 `OUTPUT_WRITE_FAILED`，`html_editable` 已有同样限制。

### 批次 5 其余观察（未改动）

- **P2，仅记录：渲染超时会遗留浏览器进程。** `subprocess.run(timeout=...)` 只杀掉 `node`，Edge 子进程可能留下，与批次 1 的 F-06 同类。可靠的做法是在 Windows 上用作业对象或 `taskkill /T`，需要真实环境验证，本次未改。
- **P3，仅记录：启用 JavaScript 时 WebSocket 不在拦截范围内。** `page.route` 只拦截 HTTP 请求。默认关闭 JavaScript，所以默认安全；`allow_javascript=True` 时页面脚本理论上可以建立 WebSocket 连接。`network_access: false` 的声明在该模式下不完全成立，建议在文档中注明，或在 Playwright 侧加 `context.route_web_socket`（需要版本验证）。
- `batch_conversion.py`：符号链接目录、文件数、总字节、请求记录、清单回放都有校验，状态记录用事务。未发现新问题。进程在批处理中途被杀会让请求停在 `running`，之后只能换 `request_id`，这是已记录的设计（恢复指引里写明）。
- `html_editable.py`：图片限制在输入目录内（`resolve(strict=True)` 后 `relative_to`），数据 URL 只允许 owned schema，脚本、`iframe`、`svg` 等被忽略。未发现问题。

## 验证

`PYTHONPATH=src python3 -m unittest discover -s tests`：529 个用例通过，67 个跳过（含设置 `WPS_TEST_PWSH` 后运行的 7 个 PowerShell 假对象用例）。新增 `tests/test_review_batch_4_5.py` 共 24 个用例。`mcp-catalog-drift`、`documentation-freshness`、`security-audit` 仍然通过。

## 未覆盖

- 真实 Windows 与 WPS：H-10 到 H-18 的修复都在 Linux 上验证。`os.link` 在 NTFS 上可用，但没有实测。
- Playwright 和 Edge 的真实渲染没有运行（没有 Node 与 Edge）。`html_render` 的测试用打桩的子进程。
- 批次 6 与 G-02、G-03、G-04、G-05、G-06、G-07 仍未处理。
