# Phase 14 计划：一键安装和使用说明

状态：**active**（2026-10-23 你提出“下一步打包，发布使用说明”，选定一键安装脚本、仓库文档加 Release；同日本地任务完成，Windows 检查和发布待做）。

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
| G6 | 在装了 WPS 的 Windows 上，从 0.11.0 的 Release 用 `install.ps1 -McpClient claude-desktop` 安装：`inspect-env` 检测到 WPS，Claude Desktop 里能列出工具并完成一次读取和一次带备份的写入；`-Uninstall` 后不留安装目录和 PATH 条目；wheel 检查通过 |

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
| P14-003 | G3、G4 | `install.ps1`、Windows CI 任务、Release 附带安装脚本和安装说明 | 本地 | 完成，CI 待在 PR 上跑通 |
| P14-004 | G5 | `USER_GUIDE.md`、README 改写、`CONTRIBUTING.md`、一致性测试 | 本地 | 完成 |
| P14-005 | G6 | 发布 0.11.0；在 Windows 上用安装脚本装 Release、接 Claude Desktop 做一次读取和写入、卸载；wheel 检查 | Windows + 你 | 待做 |

## 上机步骤（P14-005）

1. 合并后按 `docs/RELEASING.md` 发布 0.11.0（版本号和 CHANGELOG 由发布准备的 PR 改）。
2. 在装了 WPS 的 Windows 上，新开 PowerShell：

   ```powershell
   irm https://github.com/oops11111/WPS-cli/releases/latest/download/install.ps1 -OutFile install.ps1
   powershell -ExecutionPolicy Bypass -File .\install.ps1 -McpClient claude-desktop
   ```

   记录输出，确认 `inspect-env` 报告 WPS 的 COM 组件已注册。
3. 重启 Claude Desktop，确认工具列表里有 `wps-agent`；让它读一个 xlsx 的前几行，再改一个单元格（带备份），核对结果和数据目录里的备份。
4. 新开终端运行 `wps-agent inspect-env`（确认 PATH 生效）。
5. `powershell -ExecutionPolicy Bypass -File .\install.ps1 -Uninstall`，确认安装目录和 PATH 条目已删除、数据目录还在。
6. `python scripts/windows_check/run_windows_check.py wheel --version 0.11.0`。

## 主要风险

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 用户的 Python 是 Microsoft Store 的占位符 | 找不到解释器 | 脚本只认能运行并报告 `sys.executable` 的 Python，报错时说明去哪里装、怎么用 `-Python` 指定 |
| 执行策略禁止运行脚本 | 脚本不运行 | 说明里统一写 `powershell -ExecutionPolicy Bypass -File` |
| GitHub 不可达或限速 | 下载失败 | `-WheelPath` 离线安装 |
| Claude Desktop 配置文件格式改变 | 写入失败 | 只改 `mcpServers` 里的一项，先备份；文件不是 JSON 对象时不动它并报错 |
