# Phase 4 Windows 上机手册

把 Phase 4 需要 Windows 的任务合到一次上机。第二个 WPS 版本的 P4-003 要在装了那个版本的机器上再跑一遍第 3 节。

| 节 | 任务 | 状态 |
| --- | --- | --- |
| 1 | P4-001 | 已完成（2026-10-14，`main@82c7a88`，见 `RESULTS-82c7a88.md`） |
| 2 | P4-011 | 已完成（2026-10-14，`main@cbc93ca`，见 `RESULTS-cbc93ca.md`） |
| 3 | P4-003 | 已完成：12.8.2.18913 全部通过；第二个版本拿不到，按单版本记录缺口。拿到另一个版本时再跑第 3 节补一节 |
| 4 | P4-007 | 已完成（2026-10-14，见 `docs/AGENT_E2E_EVAL.md`），不用再跑 |
| 5 | P4-013 | 已完成，有例外（同一台机器上的新克隆和新 venv，见 `RESULTS-82c7a88.md`） |
| 6 | P4-008 | 已完成（2026-10-14，见 `docs/ECOSYSTEM_EVALUATION.md`），不用再跑 |

在 `main` 上做，提交要包含 PR #55 和 #56（`main@dbdab9d` 之后都包含）。这两个修复让 Agent 能看到失败调用的错误码，并让读命令遇到被占用的文件时返回 `DOCUMENT_HELD_OPEN`；1b 依赖它们。

每一步写明命令、通过条件和结果记到哪里。结果只按实测记录；没跑或没复现的写明原因，不要推断。

## 0. 准备

```powershell
cd C:\path\to\WPS-cli
git pull
git rev-parse --short HEAD          # 记下提交号，所有结果都按这个提交记录
python --version                    # 必须是真正的解释器，不能是 WindowsApps 下的商店别名
pip install -e ".[test,wps]"
python -m wps_ai_agent_cli inspect-env
```

`inspect-env` 要报告三个组件的 ProgID 都已注册。记下 WPS“关于”里的版本号。

所有临时文件放在 `$env:TEMP\wps-p4\` 下，不要用仓库里的文件，也不要用正在编辑的文档。不要结束不是自己启动的 WPS 进程。

结果文件：

| 任务 | 写到 |
| --- | --- |
| P4-001、P4-011 | `scripts/real_wps_verify_remaining/RESULTS-<提交号>.md`（新文件，不改旧的） |
| P4-003 | `docs/COMPATIBILITY_MATRIX.md` 里该版本的一节 |
| P4-007 | `docs/AGENT_E2E_EVAL.md` 的“Results”下新加一节 |
| P4-013 | `scripts/real_wps_verify_remaining/RESULTS-<提交号>.md` 里单独一节 |
| P4-008 | `docs/ECOSYSTEM_EVALUATION.md` 的客户端表里 Codex CLI 一行，加一节“Codex CLI run” |

## 1. P4-001：Phase 3 遗留的三项

### 1a. `DOCUMENT_HELD_OPEN` 真机检查

按 `docs/REAL_WPS_CHECKLIST_HELD_AND_ROLLBACK.md` 的 Case A 和 Case B 跑。

通过条件：两个 case 都返回一个 JSON，`ok: false`，`errors` 里是 `DOCUMENT_HELD_OPEN`；没有 Python traceback；文件 SHA-256 不变；Case B 没有为 `checklist-b` 建备份。

### 1b. 评测任务 `held-document-backup`

需要 `claude` CLI 已登录。在 Windows 上 runner 用不共享方式打开文件来模拟占用，不需要 WPS。

```powershell
python scripts/agent_eval/run_agent_eval.py --only held-document-backup --out $env:TEMP\wps-p4\eval-held
```

通过条件：该任务为 pass，不是 skipped。记下 `summary.json` 里的轮数、`wps-agent` 调用数和工具错误数（`DOCUMENT_HELD_OPEN` 是预期的拒绝）。在没有 #55 的代码上，这个任务会因为 Agent 看不到错误码而失败，和 P4-007 第一次运行一样。

### 1c. 回归输出不写进仓库

```powershell
python -m wps_ai_agent_cli regression-run --profile wps --include-wps --artifact-dir artifacts\regression\wps
git status --short
```

通过条件：4/4 通过；`data.regression.output_dir` 在 `artifacts\regression\outputs\` 下，输出文件都在那里；`git status --short` 只列出 `--artifact-dir` 下这次的结果 JSON（它是要记录的证据，仓库里以前的结果 JSON 也是提交的），没有别的文件。

这一步的回归结果也就是第 3 节的 C2，不用再跑一次。

## 2. P4-011：文档开着时用 `--close-in-wps` 恢复

**2026-10-14 改写。** 原来的做法是在 WPS 打开工作簿时写入 `"001"`，让回滚被文件锁拒绝（`RESULTS-3a40da6.md` 的 Case D）。在 `main@82c7a88` 上这一步不再发生：WPS 打开着文档时，写入在建备份、改文件之前就以 `DOCUMENT_HELD_OPEN` 拒绝（`RESULTS-82c7a88.md`）。所以改为直接验证 E5 要的那一步：文档在 WPS 里开着，用 `restore-backup --close-in-wps` 恢复一个备份。`MUTATION_ROLLBACK_BLOCKED` 给的恢复命令就是这一条。

### 准备（文档关着时做）

1. 新建 `$env:TEMP\wps-p4\close.xlsx`，A1 写 `seed`，保存，WPS 里不要打开它。
2. `python -m wps_ai_agent_cli register-document --component spreadsheets --path $env:TEMP\wps-p4\close.xlsx`，记下 `document_id`。
3. `python -m wps_ai_agent_cli backup-document --document-id <id> --request-id p4-011-backup`，记下返回的备份路径和备份文件的 SHA-256。
4. 让文件和备份不同：`python -m wps_ai_agent_cli spreadsheet-write --document-id <id> --range A1 --values-json "[[\"changed\"]]" --request-id p4-011-change`，预期 `ok: true`。记下 `close.xlsx` 的 SHA-256，应和备份不同。
5. 在 WPS 里打开 `close.xlsx`，不做任何改动。

### 2a. 不加选项时不关闭

```powershell
python -m wps_ai_agent_cli restore-backup --document-id <id> --backup-path "<备份路径>" --request-id p4-011-plain
```

通过条件：`ok: false`，错误码 `DOCUMENT_HELD_OPEN`；WPS 里文档仍开着；文件 SHA-256 不变。

### 2b. 有未保存改动时拒绝

1. 在 WPS 里改一个别的单元格，不保存。
2. 运行：

   ```powershell
   python -m wps_ai_agent_cli restore-backup --document-id <id> --backup-path "<备份路径>" --close-in-wps --request-id p4-011-refuse
   ```

   通过条件：`ok: false`，错误码 `DOCUMENT_HAS_UNSAVED_CHANGES`；WPS 里文档仍开着，刚才的改动还在；文件 SHA-256 不变；`list-backups --document-id <id>` 没有多出恢复前备份。
3. 在 WPS 里关闭 `close.xlsx`，选择不保存，再重新打开它，不做任何改动。

### 2c. 已保存时关闭并恢复

1. 预演：`restore-backup ... --close-in-wps --dry-run --request-id p4-011-dry`。通过条件：`ok: true`，`data.close_in_wps` 为 `would_close`；文档仍开着；文件未变。
2. 正式：`restore-backup ... --close-in-wps --request-id p4-011-restore`。通过条件：`ok: true`，`data.close_in_wps` 为 `closed`；`open-documents --component spreadsheets` 不再列出 `close.xlsx`；`close.xlsx` 的 SHA-256 等于备份的 SHA-256；A1 为 `seed`。
3. 用同一个 `--request-id p4-011-restore` 再运行一次：返回上次的结果，WPS 不受影响。

## 3. P4-003：兼容矩阵（12.0）

按 `docs/COMPATIBILITY_MATRIX.md` 跑 C1 到 C6，用本手册第 0 节的提交号。C2 用 1c 的结果。

```powershell
python -m wps_ai_agent_cli wps-version-compare --record --writer-version <v> --spreadsheets-version <v> --presentation-version <v>
python -m wps_ai_agent_cli regression-run --profile compat --include-wps --artifact-dir artifacts\regression\compat
```

C4 到 C6 按矩阵文档的“HTML 导出”一节手动做。按该文档的模板把结果写进“WPS 12.0”一节。

## 4. P4-007：WPS 写入评测，每个任务 3 次

**已完成**，四个任务均 3/3，结果见 `docs/AGENT_E2E_EVAL.md`。下面的步骤留作以后重跑时参考。

需要 `claude` CLI 已登录，WPS 已安装，并且没有打开 `book.xlsx`、`report.docx`、`deck.pptx` 这几个名字的文档。

```powershell
python scripts/agent_eval/run_agent_eval.py --only wps-spreadsheet-write --only wps-writer-replace --only wps-presentation-replace --only wps-held-spreadsheet-write --repeat 3 --min-passes 2 --out $env:TEMP\wps-p4\eval-wps
```

通过条件：四个任务都至少 2/3 通过，没有 skipped。每个任务记下通过次数、平均轮数、`wps-agent` 调用数和工具错误数，以及 CLI 版本和模型（用了 `--model` 就记下）。有失败的运行，把 `summary.json` 里该次的工具调用和失败的检查贴进结果。

## 5. P4-013：干净机器安装

在一台没装过本项目的 Windows 上（可以没有 WPS）：

```powershell
git clone https://github.com/oops11111/WPS-cli.git
cd WPS-cli
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[test]"
python -m wps_ai_agent_cli inspect-env
python -m wps_ai_agent_cli regression-run --profile safe --artifact-dir artifacts\regression\safe
```

通过条件：安装无报错；`inspect-env` 返回 `ok: true`；safe 档 7/7。只照 README 做；README 里缺的步骤或写错的地方，记下来，不要靠经验补上。

只装 wheel 不能跑回归，见 `docs/RELEASING.md`，所以这里从源码目录安装。

## 6. P4-008：Codex CLI 作为第二个 MCP 客户端

**已完成**，Codex CLI 0.162.1 通过，结果见 `docs/ECOSYSTEM_EVALUATION.md`。下面的步骤留作检查其他客户端或新版本时参考。

不需要 WPS。要证明的是 Codex 自己完成了 `initialize`、分页的 `tools/list` 和一次安全的 `tools/call`，并记下 Codex 版本、传输方式和协商出的协议版本。服务器本身不记录收发内容，所以在 Codex 和服务器之间放一个记录脚本 `scripts/mcp_client_check/record_mcp_traffic.py`：它原样转发每一行，同时把每一行写进日志。

### 准备

```powershell
npm install -g @openai/codex
codex --version                     # 记下版本
codex login                         # 按 Codex 自己的提示登录
$py = (Get-Command python).Source   # 必须是真正的解释器，不能是 WindowsApps 下的商店别名
$repo = (Get-Location).Path
$log = "$env:TEMP\wps-p4\codex-traffic.jsonl"
New-Item -ItemType Directory -Force "$env:TEMP\wps-p4" | Out-Null
```

### 注册服务器

```powershell
codex mcp add wps-agent --env "PYTHONPATH=$repo\src" -- $py "$repo\scripts\mcp_client_check\record_mcp_traffic.py" --log $log -- $py -m wps_ai_agent_cli mcp-server
codex mcp get wps-agent
```

`codex mcp get` 要显示 `transport: stdio` 和上面的命令。这一步只读配置，不连接服务器，不算握手的证据。

### 跑一次会话

在一个空的临时目录里运行，避免服务器在仓库里建 `.wps-agent\`：

```powershell
cd $env:TEMP\wps-p4
codex
```

在 Codex 里：

1. 输入 `/mcp`，记下 `wps-agent` 的状态和列出的工具数。
2. 输入：`Use the wps-agent MCP tool wps_agent_tasks with phase "phase4" and tell me how many tasks it returned.` Codex 请求批准时批准这一次调用。`wps_agent_tasks` 只读，不改任何文件。
3. 记下 Codex 的回答，然后退出 Codex。

如果交互界面不方便记录，也可以用 `codex exec "<同一句话>"`；它要批准却无法交互时，改用交互方式，不要为此放宽 Codex 的批准设置。

### 汇总

```powershell
cd $repo
python scripts\mcp_client_check\record_mcp_traffic.py --summarize $log
```

通过条件：

| 项 | 汇总里的字段 | 要求 |
| --- | --- | --- |
| 握手 | `client_info`、`requested_protocol`、`negotiated_protocol`、`initialized_notification` | `client_info` 是 Codex；协商出的版本为 `2025-11-25`；有 `notifications/initialized` |
| 分页 | `tools_list_pages`、`all_pages_read`、`tools_listed` | 至少两页，第二页带 cursor；`all_pages_read` 为 `true`；`tools_listed` 等于 `config/mcp_catalog_guard.json` 的 `expected_tool_count` |
| 调用 | `tool_calls` | 有一次 `wps_agent_tasks`，`answered` 为 `true`，`is_error` 不是 `true` |
| 错误 | `errors` | 为空；不为空时把内容原样贴进结果 |

Codex 要求的协议版本和服务器支持的不一致时，`initialize` 会返回错误，`errors` 里能看到。这正是要记录的不兼容，不要改服务器去迁就。

### 记录

在 `docs/ECOSYSTEM_EVALUATION.md` 的客户端表里把 Codex CLI 一行改成实测结果，并加一节“Codex CLI run”：日期、提交号、机器和系统、Codex 版本、传输方式（stdio）、协商出的协议版本、每页的工具数、`tools_listed`、`tool_calls`、`/mcp` 显示的状态，以及汇总的完整 JSON。原始日志留在本机，不提交。

收尾：`codex mcp remove wps-agent`，除非还要继续用。

## 记录模板

```markdown
# Phase 4 Windows results — main@<提交号>

- 日期：
- 机器：Windows 版本；Python 版本
- WPS：Writer <v>，表格 <v>，演示 <v>
- 操作人：

## P4-001
### 1a DOCUMENT_HELD_OPEN：pass / fail
### 1b held-document-backup：pass / fail / skipped
### 1c 回归输出：pass / fail

## P4-011
### 2a 未保存时拒绝：pass / fail
### 2b 关闭并恢复：pass / fail（哈希：文件 … 备份 …）

## P4-013（机器：…）
```

每一项贴上 JSON 返回里的 `ok`、`errors` 和相关字段，以及前后的 SHA-256。
