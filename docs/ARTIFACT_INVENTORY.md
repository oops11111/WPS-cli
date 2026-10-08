# 仓库产物清单

目的：区分 `artifacts/` 与 `fixtures/` 中哪些被代码、测试或配置依赖，哪些只是历史证据或重复副本。本文只做盘点，没有删除任何文件。删除前请先运行 `cleanup-plan` 生成候选清单，并经过 `cleanup-approval-manifest` 批准。

统计基于 `git ls-files`：`artifacts/` 653 个文件，`fixtures/` 25 个文件。"被引用"指路径或文件名出现在 `tests/`、`src/`、`config/`、`scripts/` 中（不含 `artifacts/` 自身）。

## 按目录

| 目录 | 文件数 | 被代码或测试引用 | 说明 |
| --- | --- | --- | --- |
| `fixtures/phase3` | 11 | 11 | 测试与回归清单直接使用，保留 |
| `fixtures/phase0` | 13 | 2 | 其余 11 个仅在文档中提及，是 Phase 0 的实验夹具 |
| `fixtures/restore_probe` | 1 | 0 | 恢复探针样例 |
| `artifacts/cloud-sync` | 3 | 3 | 三个 zip，`project_status` 与同步包检查命令读取 `...-cli.zip` |
| `artifacts/regression/safe` | 177 | 0 | 按时间戳累积的回归结果，命令读取"最新"一份 |
| `artifacts/regression/release` | 100 | 0 | 同上 |
| `artifacts/regression/wps` | 4 | 0 | 真实 WPS 回归的唯一证据，不可重新生成 |
| `artifacts/recovery-drill/p3-181-final` | 6 | `cloud_sync.py` 引用 | 恢复演练的最终产物，保留 |
| `artifacts/recovery-drill/p3-184-extracted` | 302 | 0 | 见下 |
| `artifacts/writer-nested-parity`、`writer-structure-parity` | 58 | 0 | 带时间戳的运行结果，命令读取最新一份 |
| `artifacts/local-repro` | 1 | 0 | `project_status` 读取最新一份 |

## 重复

按内容哈希，有 34 个文件与另一个文件逐字节相同，全部位于 `artifacts/recovery-drill/p3-184-extracted/` 与 `fixtures/`、`artifacts/regression/` 等目录之间。`p3-184-extracted` 是同步包解压后的整份副本（302 个文件），只有 `docs/P3_PORTABLE_RECOVERY_EXTRACTION.md` 提到它。

## 候选清单（未执行）

1. `artifacts/recovery-drill/p3-184-extracted/`：可再生的解压副本，删除前确认 `docs/P3_PORTABLE_RECOVERY_EXTRACTION.md` 中的演练结论不依赖仓库内的这份副本。
2. `artifacts/regression/safe` 与 `release` 中除最新若干份外的历史结果：命令只读取最新一份，`cleanup-plan` 的 `artifact-retention-summary` 已有保留策略。
3. `artifacts/cloud-sync/` 中除 `...-cli.zip` 外的两个 zip：`project_status` 只检查 `...-cli.zip`，其余两个是早期迭代的包。
4. 仓库根目录的 `smoke_writer_copy.docx`：只在历史回归结果和 Phase 0 文档的文本里出现，没有代码或测试引用。

不要删除：`artifacts/regression/wps/`（真实 WPS 环境的证据，无法在 CI 重新生成）、`artifacts/recovery-drill/p3-181-final/`、`fixtures/phase3/`。

## 风险与后续

- 删除历史产物会让 `regression-history` 这类按目录汇总的命令统计变少，同时 `documentation-freshness` 与文档中引用的具体文件名可能失效。执行清理时需要同步检查这两项。
- 长期做法：新的回归结果写到被 `.gitignore` 忽略的目录，只把需要留存的证据作为发布附件保存；`artifacts/` 中只保留夹具和每个 profile 的最新一份结果。这需要同时调整 `project_status`、`cloud_sync` 里写死的路径，属于单独的改动。
