
## 安装（Windows）

需要 Windows、WPS Office 和 Python 3.10 及以上；HTML 渲染另需 Node.js 18 及以上和 Microsoft Edge。在 PowerShell 里运行：

```powershell
irm https://github.com/oops11111/WPS-cli/releases/latest/download/install.ps1 -OutFile install.ps1
powershell -ExecutionPolicy Bypass -File .\install.ps1 -McpClient claude-desktop
```

`-McpClient claude-code` 改为注册到 Claude Code，`-Ocr` 加装扫描件 OCR，`-Uninstall` 卸载。完整的使用说明见 [docs/USER_GUIDE.md](https://github.com/oops11111/WPS-cli/blob/main/docs/USER_GUIDE.md)。
