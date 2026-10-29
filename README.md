# WPS AI Agent CLI

`wps-agent` 让 AI 助手读写和转换 WPS 文档。它通过 MCP 把八十多个工具交给 Claude Desktop、Claude Code 等客户端，也可以直接在命令行里用。

- **读取和检查**：文字的结构、表格的单元格和公式、核对文档内容，按文件读取不需要 WPS。
- **安全地修改**：写入前自动备份，写入后读回核对，失败时自动恢复；同一个请求重复提交不会重复执行。
- **已打开的文档**：在 WPS 里选中内容，让 AI 替换、插入、删除，失败时在 WPS 里撤回。
- **格式转换**：HTML、Word、Excel、PowerPoint、PDF（含扫描件 OCR）、Markdown、CSV，以及 .doc/.xls/.ppt 和 WPS 格式（经 WPS），并用 `fidelity-check` 给转换结果打分。

## 安装

需要 Windows 10/11、WPS Office 和 Python 3.10 及以上；HTML 渲染另需 Node.js 18 及以上和 Microsoft Edge。在 PowerShell 里运行：

```powershell
irm https://github.com/oops11111/WPS-cli/releases/latest/download/install.ps1 -OutFile install.ps1
powershell -ExecutionPolicy Bypass -File .\install.ps1 -McpClient claude-desktop
```

脚本会建独立的 Python 环境、装好全部功能、配置 HTML 渲染（`NODE_PATH`）、把 `wps-agent` 加到 PATH，并把服务器写进 Claude Desktop 的配置。`-McpClient claude-code` 改为注册到 Claude Code，`-Ocr` 加装 OCR，`-Uninstall` 卸载。

**完整的使用说明见 [docs/USER_GUIDE.md](docs/USER_GUIDE.md)**：安装参数、连接各种 AI 客户端、能做什么、备份和恢复、已知限制、故障排查。

## 命令行

所有命令输出同样结构的 JSON（`ok`、`data`、`validation`、`errors`、`warnings`）：

```powershell
wps-agent inspect-env                                   # 检查 WPS 的 COM 自动化是否可用
wps-agent convert --input 报告.html --output 报告.docx --check
wps-agent open-documents                                # 列出 WPS 里打开的文档
wps-agent mcp-server                                    # 启动 stdio MCP 服务器
```

命令失败时默认仍以退出码 0 结束，请看 JSON 里的 `ok`；脚本里需要非零退出码时加 `--strict-exit`。

## 文档

- 使用说明：[docs/USER_GUIDE.md](docs/USER_GUIDE.md)
- 支持的转换和实测结果：[docs/CONVERSION_MATRIX.md](docs/CONVERSION_MATRIX.md)；WPS 版本兼容：[docs/COMPATIBILITY_MATRIX.md](docs/COMPATIBILITY_MATRIX.md)
- MCP 客户端配置的细节：[docs/MCP_SERVER_CLIENT_CONFIG.md](docs/MCP_SERVER_CLIENT_CONFIG.md)
- 版本变化：[CHANGELOG.md](CHANGELOG.md)；版本号和发布：[docs/RELEASING.md](docs/RELEASING.md)
- 开发、测试和运行时行为的细节：[CONTRIBUTING.md](CONTRIBUTING.md)；路线图：[docs/ROADMAP.md](docs/ROADMAP.md)

## 状态

当前版本 0.11.1。Phase 0 到 13 已完成，各阶段的结果见 [CONTRIBUTING.md](CONTRIBUTING.md#各阶段) 和 [docs/ROADMAP.md](docs/ROADMAP.md)。问题和建议请提交到 <https://github.com/oops11111/WPS-cli/issues>。
