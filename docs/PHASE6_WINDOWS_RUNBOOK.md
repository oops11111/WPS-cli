# Phase 6 Windows 上机手册

把 Phase 6 需要 Windows 的任务合到上机里做。第 1 到 3 节在同一次上机里做完。第 4 节要等 `v0.3.0` 发布以后再做。

| 节 | 任务 | 对应标准 | 状态 |
| --- | --- | --- | --- |
| 1 | P6-002：用诊断脚本记录 WPS 在自动化接口上登记了什么 | G1 | 已完成（2026-10-15，`main@655d76c`，见 `scripts/real_wps_verify_p6/RESULTS-655d76c.md`） |
| 2 | P6-004：三个组件分别用双击打开，检查已打开文档命令 | G1 | 已完成，三个组件都是 (a)，G1 达成 |
| 3 | P6-008：已打开文档的评测任务，一条命令跑 3 次 | G2 | 已完成（2026-10-15，`main@4ba838b`，5 个任务都是 3/3），G2 达成 |
| 4 | P6-010：只装 `v0.3.0` 的 wheel，跑 `inspect-env` 和 safe 档 | G3 | 已完成（2026-10-15，见 `scripts/real_wps_verify_remaining/RESULTS-0808715.md`） |

P6-003（经 ROT 附着，或返回 `WPS_INSTANCE_NOT_AUTOMATABLE`）已经在本地做完，所以第 1 节和第 2 节可以一起做：第 1 节记录 WPS 实际登记了什么，第 2 节检查命令在这种情况下的表现。

每一步都写明了命令、通过条件和结果记到哪里。结果只按实测记录。没跑或没复现的，写明原因，不要推断。

## 0. 准备

```powershell
cd C:\path\to\WPS-cli
git checkout main
git pull
git rev-parse --short HEAD          # 记下提交号，第 1 到 3 节的结果都按这个提交记录
python --version
pip install -e ".[test,wps]"
python -m wps_ai_agent_cli inspect-env
claude --version                    # 第 3 节需要 claude CLI，并且已登录
$dir = "$env:TEMP\wps-p6"
New-Item -ItemType Directory -Force $dir | Out-Null
```

上机前：

- 关掉所有 WPS 窗口，并在任务管理器里确认没有 `wps`、`et`、`wpp` 进程。后面每一步都要求从“没有 WPS 在运行”开始。
- 不要改 `.docx`、`.xlsx`、`.pptx` 的默认打开程序和打开命令。G1 和 G2 都要求用系统原本的打开命令。P5-006 时临时改过的 `/Automation` 打开命令，应该已经改回来了，请确认一下。

生成三份测试文档（内容和评测用的一样）：

```powershell
python -c "import sys; sys.path.insert(0, 'scripts/agent_eval'); import run_agent_eval as r; from pathlib import Path; [r.write_fixture(Path(sys.argv[1]), n) for n in ('report.docx', 'book.xlsx', 'deck.pptx')]" $dir
```

结果写到这些地方：

| 任务 | 写到 |
| --- | --- |
| P6-002、P6-004 | `scripts/real_wps_verify_p6/RESULTS-<提交号>.md`（新文件），诊断 JSON 放在同目录的 `RESULTS-<提交号>/` 下 |
| P6-008 | `docs/AGENT_E2E_EVAL.md` 的“Results”下新加一节“P6-008 Windows runs of the open-document tasks” |
| P6-010 | `scripts/real_wps_verify_remaining/RESULTS-<提交号>.md`，格式和 P5-009 一样 |

## 1. P6-002 和 2. P6-004：三个组件分别做

对 Writer（`report.docx`）、表格（`book.xlsx`）、演示（`deck.pptx`）各做一遍下面的步骤。每次开始前都确认没有 WPS 在运行。以 Writer 为例：

```powershell
$file = "$dir\report.docx"; $component = "writer"; $tag = "writer"
Invoke-Item $file                   # 和双击一样，用系统的默认打开命令
# 等 WPS 窗口出现、文档显示出来，然后：
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\real_wps_verify_p6\automation-diagnostic.ps1 -Out "$dir\diag-$tag-doubleclick.json"
python -m wps_ai_agent_cli open-documents --component $component --register > "$dir\open-$tag.json"
Get-Content "$dir\open-$tag.json"
```

`open-documents` 的结果有下面两种情况，两种都算 G1 达成，但要记清楚是哪一种：

- **(a) 列出了文档。** `ok: true`，`documents` 里有这个文件，并且带 `document_id`。看 `instances` 里的 `attached_via`：`active_object` 说明 `GetActiveObject` 直接拿到了；`running_object_table` 说明是经 ROT 拿到的（P6-003 的新路径）。接着导出文本：

  ```powershell
  python -m wps_ai_agent_cli export-open-document-text --document-id <document_id> --output "$dir\$tag.txt" > "$dir\export-$tag.json"
  ```

  通过条件：`ok: true`；`$tag.txt` 里有文档的文字（Writer 是三段，演示是两段；表格导出的是工作表文字）；WPS 里的文档仍开着，内容不变。

- **(b) 返回 `WPS_INSTANCE_NOT_AUTOMATABLE`。** 通过条件：`ok: false`，错误码是 `WPS_INSTANCE_NOT_AUTOMATABLE`（不是 `NO_RUNNING_WPS_INSTANCE`），错误信息说明了原因和 `/Automation` 的处理办法；`data.not_automatable` 里有这个组件。

如果结果是 `NO_RUNNING_WPS_INSTANCE`、`COM_OPERATION_FAILED` 或别的错误码，就是 G1 没有达成。请把 JSON 原样贴进结果，诊断 JSON 也一起保存，我据此修改。

做 Writer 时，在关掉文档之前先记下 `wps.exe` 的路径，后面的对照组要用：

```powershell
$wpsExe = (Get-Process wps | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1).Path
$wpsExe
```

做完一个组件，在 WPS 里关掉文档（不保存），确认 WPS 进程都退出了，再做下一个组件。

**对照组（只做 Writer）：** 在没有 WPS 运行时，用 `/Automation` 打开同一份文档，再跑一次诊断：

```powershell
Start-Process $wpsExe -ArgumentList '/Automation', "`"$dir\report.docx`""
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\real_wps_verify_p6\automation-diagnostic.ps1 -Out "$dir\diag-writer-automation.json"
python -m wps_ai_agent_cli open-documents --component writer > "$dir\open-writer-automation.json"
```

预期：`prog_ids` 里 `kwps.Application` 的 `active_object` 为 true，`open-documents` 用 `active_object` 列出文档。做完后关掉文档，不保存。

### 记录

在 `RESULTS-<提交号>.md` 里，每个组件写一节：

- 用 (a) 还是 (b) 达成；如果是 (a)，写明 `attached_via` 是哪一种。
- 诊断 JSON 里的要点：
  - 哪些 ProgID 的 `active_object` 为 true；
  - ROT 里有没有这份文档（`display_name`、`app_name`、`app_path`）；
  - WPS 进程的 `command_line`。
- `open-documents` 和导出命令返回的 `ok`、`errors`。

Writer 的对照组也写一节。诊断 JSON 里有用户名和路径，提交前可以把用户名换成 `<user>`。

## 3. P6-008：已打开文档的评测任务

**2026-10-15 重跑说明。** 第一次运行（`main@655d76c`）的 4 个写入任务全部失败或被 skip，原因有两个，都已修复：

1. 已打开文档的写入命令先建备份，备份前做了独占（`FileShare.None`）检查。文档在 WPS 里开着，这个检查必然失败，于是都返回 `DOCUMENT_HELD_OPEN`。现在这些命令建备份时不做独占检查，只要文件能和 WPS 同时读取就行。P6-004 里登记文档时已经读过开着的文件，说明 WPS 允许别人读取。
2. runner 用 shell 打开文件。在这台机器上，`.xlsx` 和 `.pptx` 会弹出“打开方式”，不会启动 WPS，所以演示任务被 skip 了。现在 runner 直接运行注册表里的打开命令，和第 2 节手动做的一样。`--wps-launch automation` 是在同一条命令上加 `/Automation`。

runner 现在会自己找到 `claude.CMD`，并按 UTF-8 读取输出，不需要再手动处理。

重跑时用包含这些修复的 `main`，命令不变。

**2026-10-15 第二次重跑说明（`174f04e`）。** 写入修复有效：选区替换 3/3，选区插入 2/3。其余运行没有测到工具：

- Claude API 余额不足（`402 Insufficient Balance`），保存任务和表格对比的每次运行都在第一轮就结束了。**再跑之前先确认账户余额充足**，可以先用 `claude -p "hi"` 试一下。runner 现在会把这类运行标成 `agent_error`。
- 演示任务的准备步骤里，WPS 不支持 `TextRange.Find`，现在改成按位置选中文字。
- runner 关不掉带未保存改动的测试文档，所以留下了一个 Writer。现在它会不保存直接关掉自己的测试文档。

用包含这些修复的 `main`，把 5 个任务用同一条命令重跑一次，再跑表格对比。命令和上面一样。

**2026-10-15 第三次重跑说明（`98d8dcd`）。** 导出、选区替换、选区插入、保存都通过了，表格对比 3/3（P6-007 完成）。只有演示选区替换 0/3。

原因是：写入后，脚本从选区读回新文字，但 WPS 12.8 写入后选区不再正好是新文字，所以读回的文字对不上，报了 `VALIDATION_FAILED`。文件其实已经改对了。现在改为检查整个文本框的文字。runner 的 `select_text` 也会检查选区类型是不是文字选区。

用包含这个修复的 `main`，把 5 个任务用同一条命令再跑一次。表格对比不用再跑。

先确认没有 WPS 在运行。然后用一条命令，把 4 个新任务和 `wps-open-document-export-text` 各跑 3 次：

```powershell
python scripts/agent_eval/run_agent_eval.py `
  --only wps-open-document-export-text --only wps-open-writer-selection-replace `
  --only wps-open-writer-selection-insert --only wps-open-presentation-selection-replace `
  --only wps-open-save-document `
  --repeat 3 --min-passes 2 --out $dir\eval-open
```

通过条件（G2）：5 个任务都至少 2/3 通过，并且都没有被 skip。这条命令用的是系统的默认打开命令（`--wps-launch default`）。

第 2 节三个组件都是 (a)，所以按这条命令判定 G2。如果任务因为 `WPS_INSTANCE_NOT_AUTOMATABLE` 被 skip，就改用 runner 自己带 `/Automation` 启动 WPS，再跑一次（不改系统的打开命令）：

```powershell
python scripts/agent_eval/run_agent_eval.py `
  --only wps-open-document-export-text --only wps-open-writer-selection-replace `
  --only wps-open-writer-selection-insert --only wps-open-presentation-selection-replace `
  --only wps-open-save-document `
  --repeat 3 --min-passes 2 --wps-launch automation --out $dir\eval-open-automation
```

两条命令的结果都要记录，并写明 G2 是按哪一条判定的。

一个运行的准备步骤失败（比如选区读回来的文字不对，或者 WPS 45 秒内没有列出文档），在 `summary.json` 里会记成这次运行失败，并带 `setup_failed` 和原因，不会把前面的运行丢掉。

跑完以后，WPS 里不应该留下 runner 打开的文档，也不应该留下 runner 启动的 `wps`、`et`、`wpp` 进程。如果有留下的，记下来。

**P6-007 的对比：** 再跑一次 Writer 表格任务，和 P5-006 的平均 15.3 轮、41 次调用对比：

```powershell
python scripts/agent_eval/run_agent_eval.py --only wps-writer-table-write --repeat 3 --min-passes 2 --out $dir\eval-table
```

### 记录

在 `docs/AGENT_E2E_EVAL.md` 加一节，格式和 P5-006 那一节一样：

- 日期、提交号、WPS 版本、CLI 版本、模型、完整命令、`summary.json` 的路径。
- 每个任务一行：通过次数、轮数、`wps-agent` 调用数、工具错误数、`off_path_calls` 和 `off_path_tools`。
- 有失败的运行，就把这次运行的工具调用和没通过的检查贴进去。
- `wps-writer-table-write` 单独写一行，和 P5-006 对比；如果还出现 `CELL_NOT_FOUND`，把错误信息原文贴进去。

## 4. P6-010：只装 `v0.3.0` 的 wheel

等 `v0.3.0` 发布以后，按 `docs/PHASE5_WINDOWS_RUNBOOK.md` 第 2 节做，把版本号和文件名里的 `0.2.0` 换成 `0.3.0`，SHA-256 应为 `870DD38DFC587257A952F894E506039E58F14D09D80B0BE2C2C815722A146AEE`（以 Release 页面上列出的为准）。通过条件也一样：版本是 0.3.0，`inspect-env` 通过，safe 档 7/7，清单来自 site-packages。
