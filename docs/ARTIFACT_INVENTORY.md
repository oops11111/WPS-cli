# 仓库产物清单

本文记录 `artifacts/` 的清理结果。清理在批次 6 中按你的确认执行，删除的文件仍在 git 历史中，可以用 `git log --diff-filter=D -- <路径>` 找到并用 `git checkout <提交>^ -- <路径>` 恢复。

## 清理前后

| | 文件数 | 体积 |
| --- | --- | --- |
| 清理前 | 653 | 13 MB |
| 清理后 | 22 | 404 KB |

另外删除了仓库根目录的 `smoke_writer_copy.docx`（没有任何代码或测试引用）。

## 已删除

| 路径 | 文件数 | 原因 |
| --- | --- | --- |
| `artifacts/recovery-drill/p3-184-extracted/` | 302 | 同步包的完整解压副本，内容与仓库其余部分逐字节重复 |
| `artifacts/cloud-sync/*.zip` | 3 | 同步包本身，生成与检查它们的命令已在 G-07 中删除 |
| `artifacts/regression/safe/` 中被后续通过结果取代的运行 | 169 | 只保留最新一份通过的结果，加上失败的运行 |
| `artifacts/regression/release/` 同上 | 99 | 同上 |
| `artifacts/regression/` 根目录的两份 P3-004 早期结果 | 2 | 早期格式，被取代 |
| `artifacts/writer-nested-parity/`、`writer-structure-parity/` 中较早的运行 | 56 | 每个目录只保留最新一份，所有被删除的运行结果都是通过状态 |

## 保留

| 路径 | 文件数 | 原因 |
| --- | --- | --- |
| `artifacts/regression/wps/` | 4 | 真实 WPS 环境的回归证据，无法在 CI 重新生成 |
| `artifacts/regression/safe/` | 8 | 最新通过的一份，加上 7 份失败运行（`REGRESSION_CI_HANDOFF.md` 规定失败的 safe 结果需保留到相关缺陷关闭） |
| `artifacts/regression/release/` | 1 | 最新一份 |
| `artifacts/writer-*-parity/` | 各 1 | 最新一份真实 WPS 一致性审计结果 |
| `artifacts/recovery-drill/p3-181-final/` | 6 | 恢复演练的最终产物（含哈希清单）。读取它的 `recovery_drill_evidence` 已删除，现在只作为留档 |
| `artifacts/local-repro/` | 1 | 本地复现包的运行摘要 |
| `fixtures/` | 25 | 测试与回归清单使用的夹具，不属于本次清理范围 |

## 后续

- `cleanup-plan` 与 `cleanup-approval-manifest` 仍然保留，用于以后产物再次堆积时先出计划再批准删除。`cleanup_plan` 中针对 `artifacts/cloud-sync` 的"过期同步包"检查已经没有对应的目录，不会产出候选。
- 新的回归结果建议写到被 `.gitignore` 忽略的目录，只把需要留存的证据作为发布附件保存。
