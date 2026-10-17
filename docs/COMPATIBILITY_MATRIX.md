# WPS 兼容矩阵

Phase 4 出口标准 E2：至少两个 WPS 版本，每个版本跑通 wps 回归档，并完成三个组件的打开、保存、导出 PDF 和 HTML。本文定出检查项和每个版本的记录格式（P4-002），结果由 P4-003 填入。

状态：**12.8.2.18913 的 C1 到 C6 全部通过（`main@cbc93ca`）。第二个版本拿不到，按 2026-10-14 确认的风险预案，E2 改为单版本记录并写明缺口，E2 达成。**

## 检查项

每个版本都跑下面全部检查，用同一个提交、同一台机器、同一次上机。

| # | 检查 | 命令 | 通过条件 |
| --- | --- | --- | --- |
| C1 | 记录版本 | `inspect-env`；在 WPS“关于”里读三个组件的版本号；`wps-version-compare --record --writer-version <v> --spreadsheets-version <v> --presentation-version <v>` | 三个版本号都记下；`inspect-env` 报告三个组件的 ProgID 已注册 |
| C2 | wps 回归档 | `regression-run --profile wps --include-wps --artifact-dir <dir>` | 4/4 通过：表格计算、Writer 打开/保存/关闭、Writer 转 PDF、Writer 表格单元格更新 |
| C3 | 兼容补充档 | `regression-run --profile compat --include-wps --artifact-dir <dir>` | 4/4 通过：表格和演示各自的打开/保存/关闭（`com-smoke`）与转 PDF（`convert-smoke`） |
| C4 | Writer 导出 HTML | 见下文“HTML 导出” | `ok: true`；HTML 含三个标记文本；源文件哈希不变且仍打开 |
| C5 | 表格导出 HTML | 同上 | 同上 |
| C6 | 演示导出 HTML | 同上 | 同上 |

C2 加 C3 覆盖三个组件的打开、保存（另存副本）和导出 PDF；Writer 的这两项在 wps 档里，表格和演示的在 compat 档里。C4 到 C6 覆盖导出 HTML。

compat 档的四个场景都写在 `config/regression_manifest.json` 里，`requires_wps: true`，输出写到 `artifacts/regression/outputs/<时间>-<id>/`，不改仓库里的文件。它和 wps 档分开，是为了不改变 wps 档已有的 4/4 基线。

### 回归档使用的输入

| 组件 | 输入 |
| --- | --- |
| Writer | `fixtures/phase3/writer_table_fixture.docx` |
| 表格 | `fixtures/phase0/phase0_calculation_fixture.xlsx` |
| 演示 | `fixtures/phase0/phase0_presentation_fixture_v2.pptx` |

### HTML 导出

`export-open-document` 只导出 WPS 里已打开且已保存的文档，所以这三项要手动打开文档。每个组件用一个临时副本，不要用仓库里的文件，也不要用正在编辑的文档。

1. 新建三个临时文件，各放一个标记：Writer 文档写段落 `COMPAT-WRITER`，表格 A1 写 `COMPAT-SHEET`，演示第一页标题写 `COMPAT-SLIDE`。可以用 `html-editable` 从一个小 HTML 页面生成 xlsx 和 pptx。
2. 记下每个文件的 SHA-256：`Get-FileHash <file> -Algorithm SHA256`。
3. 在 WPS 里打开三个文件，保持已保存状态。
4. 每个文件：`register-document --component <component> --path <file>`，记下 `document_id`；再运行 `export-open-document --document-id <id> --output <dir>\<name>.html`。
5. 检查：返回 `ok: true`；HTML 文件（演示是导出目录里的 `slide0001.htm`）去掉标签后含标记文本；源文件 SHA-256 不变；`open-documents --component <component>` 仍列出该文档。
6. 在 WPS 里关闭这三个文件。

## 每个版本的记录格式

每个版本一节，按下面的模板填写。结果只按实测填写；没跑的写“未跑”，不要从别的版本推断。

```markdown
### WPS <版本号>

- 日期：
- 提交：`<sha>`
- 机器：Windows 版本；Python 版本
- 版本号：Writer <v>，表格 <v>，演示 <v>（来源：WPS“关于”）
- ProgID（`inspect-env`）：

| # | 结果 | 证据 |
| --- | --- | --- |
| C1 | pass / fail | `wps-version-compare` 输出摘要 |
| C2 | 4/4 | 回归结果 JSON 路径 |
| C3 | 4/4 | 回归结果 JSON 路径 |
| C4 | pass / fail | HTML 字节数；标记是否保留；源哈希前后 |
| C5 | pass / fail | 同上 |
| C6 | pass / fail | 同上 |

与其他版本的差异：
```

回归结果 JSON 留在上机的那台机器上即可，这里记路径和通过数；失败时把失败场景的 `errors` 原文贴进“与其他版本的差异”。

## 判定

E2 原来的达成条件：两个版本的 C1 到 C6 都是 pass（C2、C3 都是 4/4），并且两个版本之间的差异都已写明。某项只在一个版本上失败时，E2 不算达成，要么修好，要么写清楚这个版本不支持哪一项，并由你确认。

2026-10-14 确认：上机的机器上只有 12.8.2.18913，拿不到第二个正式版。按 `docs/PHASE4_PLAN.md` 风险表的预案，E2 改为“一个版本的 C1 到 C6 全部通过，并写明缺口”。

**缺口**：没有在第二个 WPS 版本上跑过，跨版本的兼容性没有证据。拿到另一个版本时，按本文流程补一节即可，不需要改检查项。

## 结果

### WPS 12.8.2.18913

- 日期：2026-10-14
- 提交：`82c7a88`
- 机器：Windows 10.0.19045；Python 3.12.14
- 版本号：Writer `12.8.2.18913`，表格 `12.8.2.18913`，演示 `12.8.2.18913`（来源：`office6` 下三个 exe 的 FileVersion，没有点开“关于”）
- ProgID（`inspect-env`）：writer `kwps.Application`，spreadsheets `ket.Application`，presentation `kwpp.Application`

| # | 结果 | 证据 |
| --- | --- | --- |
| C1 | pass | `wps-version-compare --record`：`ok: true`，三个组件 `current` 都是 `12.8.2.18913`，`relation` 为 `absent_baseline` |
| C2 | 4/4 | `artifacts\regression\outputs\20261014T141843Z-98b3f95b`；结果 JSON `artifacts\regression\wps\regression-run-20261014T141904798431Z-03e76dfa-98a4-4651-a47e-eddfee47d6b4.json`。`git status --short` 列出了这份 JSON，见 `RESULTS-82c7a88.md` 的 1c |
| C3 | 4/4 | 在 `cbc93ca` 重跑：`artifacts\regression\outputs\20261014T145908Z-eef9dcb7`。`82c7a88` 上 `presentation-com-smoke` 曾失败，这次四项都通过 |
| C4 | pass | `compat-writer.html` 315117 字节，含 `COMPAT-WRITER`；源 SHA-256 前后都是 `E81C1E14EC5E7B05CDF0A8AAA54248E1A0428B6C9419C854703A7077CEB01924`；`open-documents` 仍列出 `compat.docx` |
| C5 | pass | `compat-sheet.html` 19478 字节，含 `COMPAT-SHEET`；源 SHA-256 前后都是 `32DE844609E4D4909955A8E518B82E8DBFF8CE5B27226C2776AEA30286924291`；仍列出 `compat.xlsx` |
| C6 | pass | `slide0001.htm` 8692 字节，含 `COMPAT-SLIDE`；源 SHA-256 前后都是 `2E3258C8999BF8C6DFF119C0D468A618AE784EB967904AFC96C58A8882C14D9C`；仍列出 `compat.pptx` |

与其他版本的差异：还没有第二个版本。`82c7a88` 上 C3 的 `presentation-com-smoke` 曾返回 `COM_OPERATION_FAILED`（`(-2147352567, '发生意外。', …, -2147467259)`）。`cbc93ca` 重跑后该项通过。

复核：`82c7a88` 的失败出在装了 pywin32 时 `com-smoke` 走的 pywin32 分支。`cbc93ca` 已包含该修复，compat 档重跑为 4/4。

### 第二个版本

未跑。2026-10-14 在这台 Windows 10.0.19045 机器上只找到 `C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913`。正在运行的 `et.exe`、`wps.exe`、`wpp.exe` 都来自这个目录。没有第二个正式版可按第 3 节重跑。

## 干净环境（Phase 12，M2）

上面的结果都来自同一个账户，这个账户上已经跑过上百次评测。这一节在同一台机器上新建的本地账户上，从安装 GitHub Release 的 wheel 开始，再验证一遍（PyPI 发布已略去，2026-10-17）。被测的包必须来自这个 wheel；仓库只用来提供测试输入和检查脚本。

### 检查项

| # | 检查 | 命令 | 通过条件 |
| --- | --- | --- | --- |
| K0 | 包来自 Release 的 wheel | `run_windows_check.py --installed prereq --skip-claude` | 必需项全过；`installed package` 一项的路径在新虚拟环境的 `site-packages` 里，版本是 `0.9.0` |
| K1 | `inspect-env` | `wps-agent inspect-env` | 三个组件的 ProgID 已注册，版本号与上面的记录一致 |
| K2 到 K7 | C1 到 C6 | 同上面的检查项，`wps-agent` 用新虚拟环境里的 | 同上面的通过条件 |
| K8 | 撤回 | `run_windows_check.py --installed undo` | 6/6 通过 |

### 步骤

1. 用管理员账户新建一个本地账户（设置 → 账户 → 其他用户 → 添加），注销后用新账户登录。
2. 在新账户里手动打开一次 WPS 文字、表格和演示，关掉欢迎页、登录框和会话恢复对话框，再全部关闭。确认 `.docx`、`.xlsx`、`.pptx` 默认用 WPS 打开。
3. 安装 Python 3.10 以上（python.org 的安装包，不要用 Microsoft Store 的），然后：

   ```powershell
   py -m venv $HOME\wps-agent-venv
   $HOME\wps-agent-venv\Scripts\python -m pip install "wps-ai-agent-cli[wps] @ https://github.com/oops11111/WPS-cli/releases/download/v0.9.0/wps_ai_agent_cli-0.9.0-py3-none-any.whl"
   $HOME\wps-agent-venv\Scripts\wps-agent inspect-env
   ```

4. 克隆仓库，只用它的测试输入和脚本，不要 `pip install -e`：

   ```powershell
   git clone https://github.com/oops11111/WPS-cli.git $HOME\WPS-cli
   cd $HOME\WPS-cli
   $py = "$HOME\wps-agent-venv\Scripts\python"
   & $py scripts\windows_check\run_windows_check.py --installed prereq --skip-claude
   & $py scripts\windows_check\run_windows_check.py --installed undo
   ```

   不要设置 `PYTHONPATH`。`--installed` 让检查脚本和评测 runner 用新虚拟环境里装的包，而不是仓库的 `src/`；`RESULTS.md` 开头的 `Package` 一行写明被测的版本和路径。
5. 在仓库根目录用 `$HOME\wps-agent-venv\Scripts\wps-agent` 按上面“检查项”跑 C1 到 C6。
6. 把 `scripts\windows_check\results\` 里新写出的目录和下面的记录一起提交到 `cursor/phase12-windows-<提交号>`。

### 记录格式

```markdown
### 干净账户，WPS <版本号>，wps-ai-agent-cli <版本号>

- 日期：
- 机器：同一台 Windows <版本>，新建本地账户 `<名字>`
- 安装：`pip install "wps-ai-agent-cli[wps] @ <Release 上 wheel 的地址>"`，包路径 `<site-packages 下的路径>`
- 首次启动 WPS 时出现过的对话框：

| # | 结果 | 证据 |
| --- | --- | --- |
| K0 | pass / fail | `prereq` 结果目录 |
| K1 | pass / fail | `inspect-env` 输出摘要 |
| C1 到 C6 | pass / fail | 同上面每个版本的记录格式 |
| K8 | pass / fail | `undo` 结果目录，n/6 |

与原账户的差异：
```

### 结果

未跑（P12-010，需要 0.9.0 发布到 GitHub Release 之后）。
