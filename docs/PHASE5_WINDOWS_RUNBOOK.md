# Phase 5 Windows 上机手册

把 Phase 5 需要 Windows 的两项任务合到一次上机。两节互不依赖，先做哪节都可以。

| 节 | 任务 | 对应标准 | 状态 |
| --- | --- | --- | --- |
| 1 | P5-006：新评测任务，每个跑 3 次 | F2 | 已完成，有例外（2026-10-15，见 `docs/AGENT_E2E_EVAL.md` 的 P5-006 一节） |
| 2 | P5-009：只装 Release 的 wheel，跑 `inspect-env` 和 safe 档 | F3 | 已完成（2026-10-15，见 `scripts/real_wps_verify_remaining/RESULTS-bcdbc1d.md`） |

P5-010（第二个 WPS 版本、干净机器）不在这次范围内，拿到条件时按 `docs/PHASE4_WINDOWS_RUNBOOK.md` 第 3 节和第 5 节再做。

每一步都写明了命令、通过条件和结果记到哪里。结果只按实测记录。没跑的或没复现的，写明原因，不要推断。

## 0. 准备

第 1 节在仓库里做。第 2 节在仓库以外的目录做，不需要仓库。

```powershell
cd C:\path\to\WPS-cli
git checkout main
git pull
git rev-parse --short HEAD          # 记下提交号，第 1 节的结果按这个提交记录
python --version                    # 必须是真正的解释器，不能是 WindowsApps 下的商店别名
pip install -e ".[test,wps]"
python -m wps_ai_agent_cli inspect-env
claude --version                    # 第 1 节需要 claude CLI，并且已登录
```

`inspect-env` 要报告三个组件的 ProgID 都已注册。另外记下 WPS“关于”里显示的版本号。

所有临时文件都放在 `$env:TEMP\wps-p5\` 下。不要用仓库里的文件，也不要用正在编辑的文档。不是自己启动的 WPS 进程，不要结束。

结果写到这些地方：

| 任务 | 写到 |
| --- | --- |
| P5-006 | `docs/AGENT_E2E_EVAL.md` 的“Results”下新加一节“P5-006 Windows runs of the Phase 5 tasks” |
| P5-009 | `scripts/real_wps_verify_remaining/RESULTS-<提交号>.md`（新文件，不改旧的），格式见文末的模板 |

## 1. P5-006：新评测任务，每个跑 3 次

P5-005 加了 7 个任务。其中 5 个需要 WPS，F2 只按这 5 个判定。另外 2 个不需要 WPS，但还没有用真实 Agent 跑过，所以放进同一条命令一起跑，结果单独记录。

| 任务 | 需要 WPS | 要注意的地方 |
| --- | --- | --- |
| `wps-spreadsheet-rename-sheet` | 是 | |
| `wps-spreadsheet-create-sheet` | 是 | |
| `wps-writer-table-write` | 是 | |
| `wps-docx-to-pdf` | 是 | |
| `wps-open-document-export-text` | 是 | runner 会先用系统默认程序打开 `report.docx`，最多等 45 秒让 WPS 列出它，跑完后不保存直接关闭。要求 `.docx` 的默认程序是 WPS 文字，而且打开命令要带 `/Automation`，见下面的说明 |
| `spreadsheet-sheets-and-read` | 否 | |
| `html-table-to-docx` | 否 | |

**`wps-open-document-export-text` 的打开命令（P5-006 实测）。** 常规的打开命令 `wps.exe "%1"` 启动的 WPS 文字不注册 `kwps.Application`，`open-documents` 看不到它，这个任务会被 skip。要跑这个任务，先把当前用户的 `.docx` 打开命令临时改成 `wps.exe /Automation "%1"`，跑完后改回来。另外，上一次运行留下的文字进程会一直保持注册，下一次打开的文档在另一个进程里，同样看不到。所以这个任务要分 3 次单独跑（`--repeat 1 --min-passes 1`），每次之间关掉测试用的那个文字窗口。见 `docs/AGENT_E2E_EVAL.md` 的 Limits 和 P5-011。

跑之前：

- 在 WPS 里关掉所有文档，也就是不要有任何打开的窗口。`wps-open-document-export-text` 会让 Agent 列出 WPS 里打开的文档，多出来的文档会干扰判定。
- 确认 `.docx` 的默认程序是 WPS 文字。可以在资源管理器里右键任意 `.docx` →“打开方式”查看。

```powershell
python scripts/agent_eval/run_agent_eval.py `
  --only wps-spreadsheet-rename-sheet --only wps-spreadsheet-create-sheet `
  --only wps-writer-table-write --only wps-docx-to-pdf --only wps-open-document-export-text `
  --only spreadsheet-sheets-and-read --only html-table-to-docx `
  --repeat 3 --min-passes 2 --out $env:TEMP\wps-p5\eval
```

通过条件（F2）：5 个需要 WPS 的任务都至少 2/3 通过，并且都不是 skipped。被 skip 的任务算没跑，要先查清 skip 原因，修好后重跑这个任务。2 个不需要 WPS 的任务只记录结果，不影响 F2。

`wps-open-document-export-text` 被 skip 的话，原因会写在 `summary.json` 里。常见原因有两个：默认程序不是 WPS，或者 WPS 45 秒内没有列出这个文档（比如 WPS 启动时弹了对话框）。处理完以后只重跑这一个任务：

```powershell
python scripts/agent_eval/run_agent_eval.py --only wps-open-document-export-text --repeat 3 --min-passes 2 --out $env:TEMP\wps-p5\eval-open
```

跑完后看一眼 WPS，不应该留下 runner 打开的 `report.docx`。

### 记录

在 `docs/AGENT_E2E_EVAL.md` 的“Results”下加一节，格式照 P4-007 那几节。内容包括：

- 日期、提交号、Windows 版本、WPS 版本、Claude Code CLI 版本、模型（没加 `--model` 就写 CLI 默认）、完整命令、`summary.json` 的路径。
- 每个任务一行：通过次数、平均轮数（以及每次的轮数）、`wps-agent` 调用数、工具错误数、`off_path_calls` 和 `off_path_tools`。
- 有失败的运行，就把 `summary.json` 里这次运行的工具调用和没通过的检查贴进结果。
- 预期之外的调用（off-path）只记录，不判失败。如果多次出现同一个预期之外的工具，在结果里写一句它被用来做什么。

然后把同一文件“What it covers”里的“have only been checked offline … until P5-006 runs them on Windows”一句改成实测结果。

## 2. P5-009：只装 Release 的 wheel

这一节检查的是：别人不拉仓库，只装发布出来的包，能不能用起来。所以整个过程都不要进仓库目录，也不要 `pip install -e`。

```powershell
$dir = "$env:TEMP\wps-p5\wheel"
New-Item -ItemType Directory -Force $dir | Out-Null
cd $dir
python -m venv .venv
.venv\Scripts\Activate.ps1

$wheel = "wps_ai_agent_cli-0.2.0-py3-none-any.whl"
Invoke-WebRequest "https://github.com/oops11111/WPS-cli/releases/download/v0.2.0/$wheel" -OutFile $wheel
(Get-FileHash $wheel -Algorithm SHA256).Hash
pip install ".\$wheel"
python -c "import wps_ai_agent_cli as p; print(p.__version__, p.__file__)"
```

通过条件：

- SHA-256 等于 `00102021C9D339FEAC1D778CDBB4D2EFBD2F66B3A2A8092DE315B0C1EE71E9A3`，也就是 Release 页面上列出的值。
- 安装没有报错。
- 版本是 `0.2.0`。
- `__file__` 在 `$dir\.venv\Lib\site-packages\` 下面，不在仓库里。

接着在同一个目录里跑：

```powershell
wps-agent inspect-env > inspect-env.json
wps-agent regression-run --profile safe --artifact-dir "$dir\artifacts" > safe.json
@'
import json
env = json.load(open("inspect-env.json", encoding="utf-8"))
print("inspect-env ok:", env["ok"], env["errors"])
payload = json.load(open("safe.json", encoding="utf-8"))
regression = payload["data"]["regression"]
print("safe ok:", payload["ok"], payload["errors"])
print("passed", regression["passed_count"], "of", regression["scenario_count"], "failed", regression["failed_count"])
print("manifest:", regression["manifest_path"])
'@ | python -
```

通过条件（F3 的 Windows 部分）：

- `inspect-env` 返回 `ok: true`，三个组件的 ProgID 都已注册。
- safe 档 `ok: true`，7/7 通过，`failed_count` 为 0。
- `manifest_path` 在 `site-packages\wps_ai_agent_cli\resources\` 下。

如果不通过，把 JSON 的 `errors` 和失败场景的 `checks` 原样贴进结果。只装 wheel 时缺什么文件，写清楚是哪个文件、在哪一步缺的。

收尾：运行 `deactivate`。`$dir` 可以留着，不要提交。

## 记录模板

P5-009 的结果写成下面这样：

```markdown
# Phase 5 Windows results — v0.2.0 wheel

- 日期：
- 机器：Windows 版本；Python 版本
- WPS：Writer <v>，表格 <v>，演示 <v>
- 操作人：

## P5-009：只装 Release 的 wheel
- wheel SHA-256：…（与 Release 一致：是 / 否）
- `__version__` / `__file__`：
- inspect-env：pass / fail
- safe 档：pass / fail（通过 … / 共 …；manifest_path：…）
```

P5-009 的结果文件名用第 0 节记下的提交号，即 `RESULTS-<提交号>.md`。
