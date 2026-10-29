# WPS AI Agent CLI 使用说明

`wps-agent` 让 AI 助手（Claude Desktop、Claude Code 等支持 MCP 的客户端）读写和转换 WPS 文档：查看文字、表格、演示的内容，修改后自动核对，出错时自动恢复；在 HTML、Word、Excel、PowerPoint、PDF、Markdown、CSV 之间转换，并用同一个保真度检查给出评分。也可以直接在命令行里用。

本说明面向使用者。开发和测试见 [CONTRIBUTING.md](../CONTRIBUTING.md)，各版本的变化见 [CHANGELOG.md](../CHANGELOG.md)。

## 1. 准备

| 需要 | 用途 | 没有时 |
| --- | --- | --- |
| Windows 10 或 11 | 修改文档和经 WPS 转换都靠 Windows 上的 COM 自动化 | 只能读取文档、做不经 WPS 的转换 |
| WPS Office（个人版或专业版） | 打开、修改、另存、导出 PDF | 同上 |
| Python 3.10 及以上 | 运行 `wps-agent` | 无法安装。到 <https://www.python.org/downloads/> 安装，勾选 “Add python.exe to PATH” |
| Node.js 18 及以上、Microsoft Edge | HTML 转 PDF/PNG，以及按浏览器排版把 HTML 转成可编辑文档 | HTML 转 Office 退回内置的 CSS 计算，版面不如浏览器准确；HTML 转 PDF/PNG 不可用 |

WPS 第一次使用时，请以管理员身份运行一次 WPS 的“配置工具”，在“高级”里勾选“兼容第三方系统和软件”，否则外部程序无法驱动 WPS（`inspect-env` 会报告没有注册的 COM 组件）。

## 2. 安装

在 PowerShell（开始菜单搜索 “PowerShell”）里运行：

```powershell
irm https://github.com/oops11111/WPS-cli/releases/latest/download/install.ps1 -OutFile install.ps1
powershell -ExecutionPolicy Bypass -File .\install.ps1 -McpClient claude-desktop
```

安装脚本会：

1. 找到 Python 3.10 及以上；
2. 从 GitHub Release 下载最新的 wheel，并核对它的 SHA-256；
3. 在 `%LOCALAPPDATA%\wps-agent` 建一个独立的 Python 环境，装好 `wps-agent` 和全部可选功能（OCR 除外）；
4. 有 Node.js 时装好 Playwright（使用本机的 Edge，不另下载浏览器），并把它放在 `NODE_PATH` 最前面（你原有的条目保留）；
5. 把 `wps-agent` 加到当前用户的 PATH（新开的终端里生效）；
6. 运行 `wps-agent inspect-env`，告诉你 WPS 的 COM 自动化是否可用；
7. 按 `-McpClient` 连接 AI 客户端（见第 3 节）。

常用参数：

| 参数 | 作用 |
| --- | --- |
| `-McpClient claude-desktop` | 把服务器写进 Claude Desktop 的配置（先备份原文件），重启 Claude Desktop 生效 |
| `-McpClient claude-code` | 用 `claude mcp add` 注册到 Claude Code（当前用户范围） |
| `-McpClient none`（默认） | 只打印配置，自己粘贴到其他客户端 |
| `-Ocr` | 加装扫描件 PDF 的 OCR（RapidOCR，较大） |
| `-Version 0.11.0` | 安装指定版本，默认最新 |
| `-WheelPath <文件>` | 用已下载的 wheel 离线安装 |
| `-SkipBrowser` | 不装 Playwright |
| `-NoPath` | 不改 PATH |
| `-InstallDir`、`-DataDir` | 安装目录（默认 `%LOCALAPPDATA%\wps-agent`）、数据目录（默认 `%LOCALAPPDATA%\wps-agent-data`） |
| `-Uninstall` | 卸载 |

**升级**：先退出 Claude Desktop（或其他正在用 wps-agent 的 AI 客户端），再运行一次安装脚本即可，Python 环境会重建，数据目录不动。客户端还开着时脚本会提示先退出，不会删到一半。

**卸载**：`powershell -ExecutionPolicy Bypass -File .\install.ps1 -Uninstall`。会删除安装脚本放进安装目录的内容（目录空了就一并删除）、PATH 里的那一条和 `NODE_PATH` 里指向安装目录的那一条，PATH 和 `NODE_PATH` 里的其他条目不动；数据目录（备份和操作记录）保留，不需要时自己删除；AI 客户端里的 `wps-agent` 条目也请自己删掉。

不想用脚本时，也可以手动安装：

```powershell
py -3 -m venv %LOCALAPPDATA%\wps-agent\venv
%LOCALAPPDATA%\wps-agent\venv\Scripts\pip install "wps_ai_agent_cli-<版本>-py3-none-any.whl[all]"
```

## 3. 连接 AI 客户端

`wps-agent` 通过 MCP（stdio）提供八十多个工具。服务器的启动命令是 `wps-agent mcp-server`。

**Claude Desktop**：安装时加 `-McpClient claude-desktop`，然后完全退出并重新打开 Claude Desktop。手动配置时，编辑 `%APPDATA%\Claude\claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "wps-agent": {
      "command": "C:\\Users\\<你>\\AppData\\Local\\wps-agent\\venv\\Scripts\\wps-agent.exe",
      "args": ["mcp-server"],
      "env": {
        "WPS_AGENT_WORKSPACE": "C:\\Users\\<你>\\AppData\\Local\\wps-agent-data",
        "NODE_PATH": "C:\\Users\\<你>\\AppData\\Local\\wps-agent\\node\\node_modules"
      }
    }
  }
}
```

**Claude Code**：安装时加 `-McpClient claude-code`，或手动运行安装结束时打印的 `claude mcp add ...` 命令。

**其他 MCP 客户端**：用 `-McpClient none` 安装，把打印出的 `mcpServers` 条目粘贴到客户端的配置里。

`WPS_AGENT_WORKSPACE` 指定服务器存放文档登记、操作记录和备份的目录（其中的 `.wps-agent` 文件夹）。不设置时用服务器启动时的当前目录，而客户端启动服务器的目录不一定可写，所以请保留这一项。

连上之后，可以这样试：“列出 WPS 里打开的文档”“读一下 D:\报表\三季度.xlsx 的 Sheet1 前 10 行”。

## 4. 能做什么

下面每一类都能用自然语言让 AI 去做；括号里是对应的工具或命令，便于在 AI 的回答里核对它用了什么。

### 读取和检查

- 文字：标题、样式、书签的结构和文字（`writer_structure`），选中的内容（`writer_selection_read`）；
- 表格：工作表列表、单元格值和公式（`spreadsheet_sheets`、`spreadsheet_read`、`spreadsheet_inspect`）；
- 演示：选中的文字（`presentation_selection_read`），以及导出的全文（`export_open_document_text`）；
- 核对：文档里是否有某段文字、某个单元格是否等于某个值（`validate_document`）。

按文件读取（`writer_structure`、`spreadsheet_read`、`validate_document`）不需要 WPS，在任何电脑上都能用；读取选中内容和已打开的文档需要 WPS。

### 修改文件

替换文字、填书签、写表格单元格和公式、写文字里的表格、改演示文字、重命名或新建工作表等。每次修改：

1. 先登记文档（`register_document`），得到 `document_id`；
2. 写入前自动备份（备份在数据目录的 `.wps-agent\backups` 里）；
3. 可以先加 `dry_run` 看会改什么，不写入；
4. 写入后读回核对，结果里的 `verified_state` 说明写进去的是什么；
5. 核对失败时自动从备份恢复（`MUTATION_ROLLED_BACK`）。

同一个 `request_id` 重复提交不会重复执行，所以 AI 在网络中断后重试是安全的。

### 修改已在 WPS 里打开的文档

用户正打开着的文档不能按文件改（WPS 占着文件）。这时改用选区工具：先在 WPS 里选中要改的文字、单元格、图形或图表，再让 AI “把选中的内容改成……”（`writer_selection_replace`、`presentation_selection_replace`、`spreadsheet_selection_replace` 等），也可以保存（`save_open_document`）或导出（`export_open_document_pdf`）。写入失败时会在 WPS 里撤回，不会覆盖你在此期间做的修改。

### 格式转换

一个 `convert` 工具按两端的扩展名选转换方式：

| 方向 | 说明 |
| --- | --- |
| HTML → Word、Excel、PowerPoint | 按浏览器的排版生成可编辑文档；演示可加 `fidelity: appearance` 保留外观 |
| HTML → PDF、PNG | 用 Edge 渲染 |
| Word、Excel、PowerPoint → HTML、Markdown | 干净的 HTML（内联样式），图片内嵌或放在旁边的文件夹里 |
| Markdown ↔ HTML、Word、PowerPoint | |
| CSV/TSV ↔ Excel | 自动识别 GBK/UTF-8 编码和分隔符，`007` 保持为文本 |
| Word ↔ PowerPoint，Excel 区域 → Word/PowerPoint 表格 | 演示按一、二级标题分页 |
| PDF → Word、Excel、PowerPoint | 标题、列表、表格、图片、页眉页脚；扫描件需要 `-Ocr` 安装并在转换时打开 `ocr` |
| .doc/.xls/.ppt、.wps/.et/.dps ↔ docx/xlsx/pptx，以及 PDF、每页 PNG | 经 WPS 转换，需要 WPS |

转换后可以用 `fidelity_check` 给结果打分：文字、结构、格式、动画、数据和版面相似度，并说明哪里不一样。

## 5. 在命令行里用

所有命令都输出同样结构的 JSON：`ok` 表示成败，`data` 是结果，`errors` 是错误码和说明。

```powershell
wps-agent inspect-env
wps-agent convert --input 报告.html --output 报告.docx --check
wps-agent convert --input 销售.csv --output 销售.xlsx
wps-agent register-document --component spreadsheets --path D:\报表\三季度.xlsx
wps-agent spreadsheet-read --document-id doc_xxx --sheet Sheet1 --range A1:D10
wps-agent spreadsheet-write --document-id doc_xxx --sheet Sheet1 --range B2 --values-json "[[42]]" --request-id r1
wps-agent open-documents
```

命令失败时进程默认仍以 0 退出，请看 JSON 里的 `ok`；脚本里需要非零退出码时加 `--strict-exit`。完整的命令列表：`wps-agent --help`，某个命令的参数：`wps-agent <命令> --help`。

## 6. 备份和恢复

- 列出某个文档的备份：`wps-agent list-backups --document-id doc_xxx`
- 恢复：`wps-agent restore-backup --document-id doc_xxx --backup-name <备份文件名> --request-id r2`（先加 `--dry-run` 看会恢复什么）
- 文档在 WPS 里打开着、自动恢复被文件锁挡住时（`MUTATION_ROLLBACK_BLOCKED`），先在 WPS 里不保存地关闭文档再恢复，或给 `restore-backup` 加 `--close-in-wps`。

## 7. 已知限制

- **ODF（.odt/.ods/.odp）**：WPS 12.8 不能打开其他程序写的 ODF 文件，“另存为 .odt”写出的也不是 ODF。`convert` 会在一分钟内报 `FORMAT_NOT_SUPPORTED_BY_WPS`，请先在生成它的程序里另存为 .docx/.xlsx/.pptx。
- **已打开的演示文稿**不能按文件修改（WPS 不报告演示的未保存状态），请用选区工具，或先关闭。
- **多个 WPS 窗口**：同一组件开了多个 WPS 主窗口、而目标文档不在可连接的那个里时，修改会被拒绝，错误信息列出窗口；关掉多余的窗口再试。
- **HTML 转 Word 的版面**：大多数页面与浏览器的相似度在 0.90 以上；文字很密的页面因为 WPS 和浏览器绘制字形不同，可能在 0.85 左右，排版位置是一致的。

## 8. 遇到问题

| 现象或错误码 | 原因和处理 |
| --- | --- |
| 安装时 “Python 3.10 or later was not found” | 装 Python 3.10+ 并勾选加入 PATH，或用 `-Python C:\...\python.exe` 指定 |
| 运行脚本时提示“禁止运行脚本” | 按上面的写法用 `powershell -ExecutionPolicy Bypass -File .\install.ps1` 运行 |
| `inspect-env` 里没有任何组件 `detected: true`，或 `COM_BACKEND_UNAVAILABLE` | WPS 没装，或没有开启“兼容第三方系统和软件”（第 1 节） |
| `WPS_INSTANCE_NOT_AUTOMATABLE` | 双击打开的 WPS 不能被外部程序连接。保存后关闭该组件的所有窗口，再用 `wps.exe /Automation "<文档路径>"` 打开 |
| `DOCUMENT_HELD_OPEN` | 文档正在 WPS 里打开。保存并关闭后重试，或改用已打开文档的选区工具 |
| `BROWSER_BACKEND_UNAVAILABLE`，HTML 转 PDF 失败 | 没有 Node.js 18+、Playwright 或 Edge。装好 Node.js 后重新运行安装脚本 |
| `PDF_NEEDS_OCR` | 扫描件 PDF。用 `-Ocr` 重新安装，转换时打开 `ocr` |
| `FORMAT_NOT_SUPPORTED_BY_WPS` | WPS 不支持这个方向（例如 ODF，见第 7 节），信息里列出 WPS 能写的格式 |
| `OUTPUT_ALREADY_EXISTS` | 不会覆盖已有文件，换一个输出路径 |
| Claude Desktop 里看不到工具 | 完全退出 Claude Desktop（托盘图标也退出）再打开；检查配置文件里 `command` 指向的 `wps-agent.exe` 是否存在 |

问题和建议请提交到 <https://github.com/oops11111/WPS-cli/issues>，附上 `wps-agent inspect-env` 的输出。
