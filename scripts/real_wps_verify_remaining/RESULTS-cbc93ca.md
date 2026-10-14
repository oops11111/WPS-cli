# Phase 4 Windows results — main@cbc93ca

- 日期：2026-10-14
- 机器：Windows 10.0.19045；Python 3.12.14
- WPS：只有 `12.8.2.18913`（`office6` 三个 exe 的 FileVersion）
- 这次只跑手册第 2 节、12.8.2.18913 的 compat 档，并查找第二个 WPS 版本。P4-007、P4-008、P4-001、P4-013 没有重跑。

## P4-011

文档 `doc_611815b62cd4c142`，`%TEMP%\wps-p4\close.xlsx`。关着时备份 `p4-011-backup`，路径 `.wps-agent\backups\doc_611815b62cd4c142\close.20261014T145738018922Z.xlsx`，SHA-256 `15A6F5B6B2C9220771DD5428A79965E8F3DCE6118EDB63EED7B90072BC27DF56`。随后写入 `[["changed"]]`，`ok: true`，文件 SHA-256 `29C1A99E95E347B0B862615769ECFCE89C5B9437D2FF904229498E2C654CD557`。然后在 ET 里打开，未改。

### 2a 不加选项时不关闭：pass

`restore-backup --request-id p4-011-plain`：`ok: false`，`DOCUMENT_HELD_OPEN`。文件 SHA-256 仍是 `29C1A99E…`，文档仍开着，A1 仍是 `changed`。

### 2b 有未保存改动时拒绝：pass

B1 写成 `unsaved-edit`，`Saved=false`。`restore-backup --close-in-wps --request-id p4-011-refuse`：`ok: false`，`DOCUMENT_HAS_UNSAVED_CHANGES`。B1 仍是 `unsaved-edit`，文件 SHA-256 不变。`list-backups` 仍是 2，没有多出恢复前备份。

### 2c 已保存时关闭并恢复：pass

不保存关闭后再打开，A1 为 `changed`，`Saved=true`。

- `--close-in-wps --dry-run --request-id p4-011-dry`：`ok: true`，`close_in_wps` 为 `would_close`。文档仍开着，SHA-256 不变。
- `--close-in-wps --request-id p4-011-restore`：`ok: true`，`close_in_wps` 为 `closed`。`open-documents` 不再列出 `close.xlsx`。文件 SHA-256 等于备份 `15A6F5B6…`。A1 为 `seed`。
- 同一个 `--request-id p4-011-restore` 再跑：`summary` 为 “Restore request replayed from idempotency record.”，`close_in_wps` 仍是 `closed`。ET 的工作簿数仍是 0。

## compat 重跑（C3）

`regression-run --profile compat --include-wps`：`ok: true`，4/4。

- `spreadsheets-com-smoke`
- `spreadsheets-convert-smoke`
- `presentation-com-smoke`
- `presentation-convert-smoke`

输出目录 `artifacts\regression\outputs\20261014T145908Z-eef9dcb7`。结果 JSON 留在本机的 `artifacts\regression\compat\`，没有提交。

## 第二个 WPS 版本

未跑。这台机器只有 `12.8.2.18913`。

## 复核（2026-10-14）

以上是上机时记录的原文，没有改动。

- **P4-011 通过，E5 达成。** 2a、2b、2c 都符合手册第 2 节的通过条件：默认不关闭；有未保存改动时拒绝且没有建恢复前备份；预演只报告 `would_close`；正式恢复后文件 SHA-256 等于备份；同一 request id 重放没有再次打开或关闭文档。
- **C3 为 4/4。** `82c7a88` 上失败的 `presentation-com-smoke` 在包含 PR #61 的 `cbc93ca` 上通过，12.8.2.18913 的 C1 到 C6 全部通过。
- **第二个版本：** 拿不到。2026-10-14 确认按风险预案把 E2 改为单版本记录并写明缺口，**P4-003 完成，E2 达成**。
