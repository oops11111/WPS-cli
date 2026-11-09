# Phase 14 计划：一键安装和使用说明

状态：**done**（2026-10-23 你提出“下一步打包，发布使用说明”并激活，2026-11-09 完成）。发布了 0.11.0～0.11.3；第二次上机（0.11.3）按使用说明的原样命令一次装好，经 MCP 读写和 wheel 检查通过，结果见下面“上机结果”。

## 目标

Phase 13 结束时，`wps-agent` 的功能已经齐全，但交给一个只装了 WPS 的 Windows 用户还很费劲：

1. **安装要懂 Python。** Release 只有 wheel 和源码包，要自己建环境、挑可选依赖（`[wps]`、`[html]`、`[pdf]`……）；HTML 渲染还要自己装 Playwright、设 `NODE_PATH`。
2. **接入 AI 客户端要手写配置。** 现有的 `docs/MCP_SERVER_CLIENT_CONFIG.md` 是开发时的写法（`PYTHONPATH=src`、指定工作目录），而 MCP 客户端启动服务器的目录不一定可写，备份和操作记录会落到不该去的地方。
3. **没有给使用者看的说明。** README 是开发文档（从源码安装、测试、ruff、实现细节）。

Phase 14 补上这三块，发布 0.11.0。

## 出口标准

| 标准 | 内容 |
| --- | --- |
| G1 | 离线：`[all]` 可选依赖等于各用户可选依赖（OCR 除外）的并集，有测试防止两者走样 |
| G2 | 离线：`python -m wps_ai_agent_cli.client_config` 生成 Claude Desktop（写入前备份、保留其他服务器）、Claude Code（`claude mcp add` 命令）和通用 JSON 的配置；`mcp-server` 在设置了 `WPS_AGENT_WORKSPACE` 时在那个目录工作；都有测试 |
| G3 | `scripts/install/install.ps1` 在 GitHub 的 Windows 运行器上用 Windows PowerShell 5.1 跑通：装 wheel 和 `[all]`、装 Playwright 并用 Edge 渲染一份 HTML、PATH 上的 `wps-agent` 可用、写入 Claude Desktop 配置，`-Uninstall` 清理干净；每次 CI 都跑 |
| G4 | 每个 GitHub Release 附带 `install.ps1`，发布说明里有安装步骤 |
| G5 | `docs/USER_GUIDE.md`：准备、安装、连接客户端、能做什么、命令行、备份和恢复、已知限制、故障排查；文中的错误码和安装参数都有测试核对；README 以使用者为入口，开发内容移到 `CONTRIBUTING.md` |
| G6 | 在装了 WPS 的 Windows 上，从 0.11.3 的 Release 用 `install.ps1 -McpClient claude-desktop` 安装：`inspect-env` 检测到 WPS，Claude Desktop 里能列出工具并完成一次读取和一次带备份的写入；`-Uninstall` 后不留安装目录和 PATH 条目；wheel 检查通过 |

## 已做的决定

| 决定 | 内容 | 理由 |
| --- | --- | --- |
| 1. 打包形式 | 一键安装脚本：Release 里继续发 wheel，另附 PowerShell 安装脚本；不做免安装 zip 和独立 exe | 你在 2026-10-23 选定。依赖 Python 和 Node.js，但脚本小、能升级、COM 和 OCR 不用重新打包 |
| 2. 使用说明 | 仓库里的 `docs/USER_GUIDE.md`，Release 说明附安装步骤并链接它 | 你在 2026-10-23 选定 |
| 3. 客户端配置放哪里 | 放在包里的模块 `wps_ai_agent_cli.client_config`，不加 CLI 命令或 MCP 工具 | 能离线测试；对外接口清单和 MCP 工具目录不变（让 AI 改自己的客户端配置也不合适） |
| 4. 数据放哪里 | `WPS_AGENT_WORKSPACE`，安装脚本设为 `%LOCALAPPDATA%\wps-agent-data`，和安装目录分开 | 客户端启动服务器的目录不确定；卸载或升级不删除备份 |
| 5. OCR | 不进 `[all]`，安装时加 `-Ocr` | onnxruntime 较大，多数用户用不到 |
| 6. 版本号 | 0.11.0 | 新增可选依赖、安装脚本和环境变量，按 `docs/RELEASING.md` 升次版本；CLI 和 MCP 接口没有变 |

## 任务拆分

| 任务 | 对应标准 | 内容 | 在哪做 | 状态 |
| --- | --- | --- | --- | --- |
| P14-001 | G1 | `[all]` 可选依赖和测试 | 本地 | 完成 |
| P14-002 | G2 | `client_config` 模块、`WPS_AGENT_WORKSPACE`、测试 | 本地 | 完成 |
| P14-003 | G3、G4 | `install.ps1`、Windows CI 任务、Release 附带安装脚本和安装说明 | 本地 | 完成，Windows CI 任务每次都跑 |
| P14-004 | G5 | `USER_GUIDE.md`、README 改写、`CONTRIBUTING.md`、一致性测试 | 本地 | 完成 |
| P14-005 | G6 | 发布 0.11.0；在 Windows 上用安装脚本装 Release、接 Claude Desktop 做一次读取和写入、卸载；wheel 检查 | Windows + 你 | 0.11.0 已发布（2026-10-23）。上机前做了一次全仓代码审查，安装脚本、回滚、HTML 转换的问题在 0.11.1 修复（PR #133～#136），上机检查改用 0.11.1。2026-11-09 第一次上机：两处安装问题（下面“上机结果”），在 0.11.2 修复；幻灯片修复随 0.11.3 发布。第二次上机（0.11.3）通过，完成 |

## 上机步骤（P14-005）

1. 按 `docs/RELEASING.md` 发布 0.11.3（版本号和 CHANGELOG 由发布准备的 PR 改）。
2. 在装了 WPS 的 Windows 上，新开 PowerShell：

   ```powershell
   irm https://github.com/oops11111/WPS-cli/releases/latest/download/install.ps1 -OutFile install.ps1
   powershell -ExecutionPolicy Bypass -File .\install.ps1 -McpClient claude-desktop
   ```

   记录输出，确认 `inspect-env` 报告 WPS 的 COM 组件已注册。
3. `python scripts/windows_check/mcp_client_smoke.py --out <结果目录>`：按 Claude Desktop 配置里的 `wps-agent` 条目启动服务器（从另一个目录启动），列出工具，读 `book.xlsx` 的一块区域，写一个单元格并读回，确认留下了备份、备份在 `WPS_AGENT_WORKSPACE` 下、启动目录里没写东西。再重启 Claude Desktop，确认工具列表里有 `wps-agent`，让它读一个 xlsx 的前几行、改一个单元格，核对结果和数据目录里的备份。
4. 新开终端运行 `wps-agent inspect-env`（确认 PATH 生效）。
5. `powershell -ExecutionPolicy Bypass -File .\install.ps1 -Uninstall`，确认安装目录和 PATH 条目已删除、数据目录还在。
6. `python scripts/windows_check/run_windows_check.py wheel --version 0.11.3`。

## 上机结果

### 第一次（0.11.1，2026-11-09，main@8fd1db2）

结果在 `scripts/windows_check/results/20261109T020158Z-8fd1db2-install-0.11.1/`（按说明直接装）和 `20261109T021439Z-8fd1db2-install-0.11.1/`（绕过后重装），wheel 检查在 `20261109T023917Z-wheel-0.11.1/`。机器：Windows 10 19045，WPS 12.8.2.18913，Node.js 22，Edge；之前装过 0.11.0。

- **按说明直接装失败**：`Python 3.10 or later was not found`。这台机器的 `python` 是 Microsoft Store 占位程序，没有 `py`，Python 3.12 是 uv 装的、不在 PATH 上。安装脚本在动任何东西之前停下，0.11.0 没受影响。
- **GitHub API 被限流**：安装脚本要先查 API 拿 wheel 的地址，未登录调用被拒时无法安装。
- **绕过后（`-Python` 指向 uv 的 Python，`-WheelPath` 用手动下载的 wheel）全部通过**：0.11.0 原地升级到 0.11.1；shim 是相对路径；用户 PATH 只有一条 `wps-agent\bin`，其他条目和类型与安装前相同；`NODE_PATH` 以安装目录的 `node_modules` 开头；Claude Desktop 配置先备份再写入；新终端里 `wps-agent` 指向安装目录，`inspect-env` 检测到三个 WPS 组件；`mcp_client_smoke.py` 按 Claude Desktop 的方式读写通过（87 个工具，备份在数据目录下，启动目录里没写东西）；`-Uninstall` 只删自己的东西、数据目录保留；重装成功；wheel 检查 SHA-256 一致，安全档 7/7。
- 这台机器的用户 PATH 在检查前已是 REG_SZ、条目全部展开，应是 0.11.0 的安装脚本留下的（0.11.1 修复了这一点，但不能还原）。

两处安装问题在 0.11.2 修复：找 Python 时也试上次安装用的 Python、`uv python find` 和 python.org、uv 的默认目录；API 被拒时从 Release 页面下载，用 Release 附带的 `SHA256SUMS.txt` 核对。

### 第二次（0.11.3，2026-11-09，main@e0cdf0b）

结果在 `scripts/windows_check/results/20261109T162108Z-e0cdf0b-install-0.11.3/`，wheel 检查在 `20261109T163806Z-wheel-0.11.3/`。同一台机器，从 0.11.1 升级；开始时 `python` 仍是 Microsoft Store 占位程序（退出码 9009），没有 `py`。

- **按说明原样一条命令装好**（不加 `-Python`、`-WheelPath`），退出码 0。下载的 `install.ps1` 与 `v0.11.3:scripts/install/install.ps1` 一致。
- 找到的是 uv 装的 Python 3.12（上次安装记下的那个）。
- GitHub API 又一次拒绝（403），安装脚本改从 Release 页面下载 wheel，并报告 “SHA-256 matches the Release”。
- `install.json` 为 0.11.3、`installed`；安装脚本没有改 PATH（“Already on PATH”）和 `NODE_PATH`，PATH 里只有一条 `wps-agent\bin`；新终端里 `wps-agent` 指向安装目录的 `wps-agent.cmd`，`inspect-env` 检测到三个 WPS 组件；Claude Desktop 配置先备份再写入。
- `mcp_client_smoke.py` 用安装环境里的 Python、按 Claude Desktop 的方式启动服务器：0.11.3、87 个工具，读 `sales_gbk!A1:F3`、写 `F2` 并读回，备份在 `WPS_AGENT_WORKSPACE` 下，启动目录里没写东西，通过。
- wheel 检查：SHA-256 与 Release 一致，从 site-packages 加载 0.11.3，安全档 7/7。
- 另把 `fixtures/html_complex/report.html` 转成 PPTX（可编辑模式，5 页），在 WPS 里打开正常。
- 与步骤的出入：安装做完后，按你的要求另装了 Python 3.13 修好 `python` 命令（原 3.12 的 MSI 注册已坏），并整理了 PATH 的重复条目，所以安装后的 PATH 与安装前不逐字相同；这不是安装脚本改的。这次按你的要求装好后保留、没有卸载；`-Uninstall` 已在第一次上机和每次的 Windows CI 里验证过。

## 主要风险

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 用户的 Python 是 Microsoft Store 的占位符 | 找不到解释器 | 脚本只认能运行并报告 `sys.executable` 的 Python，报错时说明去哪里装、怎么用 `-Python` 指定 |
| 执行策略禁止运行脚本 | 脚本不运行 | 说明里统一写 `powershell -ExecutionPolicy Bypass -File` |
| GitHub 不可达或限速 | 下载失败 | `-WheelPath` 离线安装 |
| Claude Desktop 配置文件格式改变 | 写入失败 | 只改 `mcpServers` 里的一项，先备份；文件不是 JSON 对象时不动它并报错 |
