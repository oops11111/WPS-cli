# Phase 4 Windows results — main@82c7a88

- 日期：2026-10-14
- 机器：Windows 10.0.19045；Python 3.12.14（Codex primary runtime，不是 WindowsApps 别名）
- WPS：Writer / 表格 / 演示 文件版本均为 `12.8.2.18913`（`office6\wps.exe`、`et.exe`、`wpp.exe` 的 FileVersion；没有点开“关于”对话框）
- ProgID（`inspect-env`，`ok: true`）：writer `kwps.Application`，spreadsheets `ket.Application`，presentation `kwpp.Application`

P4-007 和 P4-008 手册已标完成，这次没有重跑。

## P4-001

### 1a DOCUMENT_HELD_OPEN：pass

临时簿 `%TEMP%\wps-p4\held.xlsx`，`document_id` `doc_983300c28fd5a911`。独占占用（`FileShare.None`）。SHA-256 前后都是 `F52AED3B3149F4C3EBDBCCE07EEFA64609DC9547A3AEEA825D2979570B2BBA22`。stderr 为空，没有 traceback。

Case A `spreadsheet-inspect --request-id checklist-a`：`ok: false`，`errors[0].code` = `DOCUMENT_HELD_OPEN`。

Case B `spreadsheet-write --request-id checklist-b`：`ok: false`，`errors[0].code` = `DOCUMENT_HELD_OPEN`。`list-backups` 的 `count` 为 0。

### 1b held-document-backup：pass

Claude Code CLI 2.1.295，未传 `--model`。`%TEMP%\wps-p4\eval-held\run-20261014T141800922258Z\summary.json`。

1/1 通过，不是 skipped。3 轮。`wps-agent` 调用 2，工具错误 1。`DOCUMENT_HELD_OPEN` 被判定器看到。没有操作记录，没有备份，没有 `restore_backup`，文件未变。

### 1c 回归输出：fail

`regression-run --profile wps --include-wps --artifact-dir artifacts\regression\wps`：`ok: true`，4/4（`spreadsheet-calc-smoke`、`writer-com-smoke`、`writer-convert-smoke`、`writer-table-smoke`）。

`data.regression.output_dir`：`C:\Users\admin\wps cli\artifacts\regression\outputs\20261014T141843Z-98b3f95b`。

`git status --short` 列出了结果 JSON：`artifacts/regression/wps/regression-run-20261014T141904798431Z-03e76dfa-98a4-4651-a47e-eddfee47d6b4.json`。通过条件要求这次状态为空，所以 1c 不算通过。该 JSON 没有提交。

## P4-011

### 2a 未保存时拒绝：fail（按手册停下，没有做后面的步骤）

`%TEMP%\wps-p4\close.xlsx`，A1 为 `seed`，`document_id` `doc_611815b62cd4c142`，已在 ET 中打开。

`spreadsheet-write --values-json [["001"]] --request-id p4-011-write-1`：`ok: false`，只有 `DOCUMENT_HELD_OPEN`。没有 `VALIDATION_FAILED`，没有 `MUTATION_ROLLBACK_BLOCKED`，提示里没有 `--close-in-wps` 或 `--backup-path`。

手册要求这时停下，所以没有改单元格，也没有跑 `--close-in-wps`。

### 2b 关闭并恢复：未跑

## P4-013

不是一台从没装过本项目的机器：这台电脑已有别的检出。按手册命令做了一次新的浅克隆和新建 venv：`%TEMP%\wps-p4\clean-clone`，提交 `82c7a88`。

`pip install -e ".[test]"` 无报错。`inspect-env`：`ok: true`。`regression-run --profile safe`：`ok: true`，7/7。克隆目录里的 `git status --short` 列出了 safe 结果 JSON，手册的通过条件没有要求它为空。

## 复核（2026-10-14）

以上是上机时记录的原文，没有改动。复核结论：

- **1c 改判为 pass。** 手册的通过条件写错了：`git status` 列出的是 `--artifact-dir` 下这次的结果 JSON，正是手册要求写出的证据，仓库里以前的回归结果 JSON 也是提交的。回归输出都在 `artifacts\regression\outputs\` 下，没有写进被跟踪的文件，E1 要求的正是这一点。手册的条件已改正。1a、1b 通过，所以 **P4-001 完成，E1 达成**。
- **P4-011 的 2a 不是缺陷。** WPS 打开工作簿时，写入现在在建备份和改文件之前就以 `DOCUMENT_HELD_OPEN` 拒绝，所以回滚被锁的情形用这种办法造不出来了。手册第 2 节已改写：文档关着时建备份并改文件，再在 WPS 里打开它，然后直接验证 `restore-backup` 默认不关、有未保存改动时拒绝、`--close-in-wps` 关闭并恢复。P4-011 按新步骤重跑。
- **P4-013 按例外接受。** 不是干净机器，但按 README 新克隆、新建 venv 安装无报错，`inspect-env` 通过，safe 档 7/7。机器上已有 Python、WPS 和别的检出，这一点写进结论。**P4-013 完成，E6 达成（有例外）。**
- **C3 的 `presentation-com-smoke` 失败的原因：** 装了 pywin32 时，`com-smoke` 走的是一条单独的 pywin32 分支，它用命名参数 `WithWindow` 打开演示，也不做占用检查；同一个文件上通过的 `convert-smoke` 走的是 PowerShell 脚本。分支 `fix/com-smoke-powershell` 让 `com-smoke` 一律走 PowerShell 脚本。合并后只需重跑 compat 档。
- **C1 的版本来源**是三个 exe 的 FileVersion，不是“关于”对话框，接受，矩阵里已写明。
