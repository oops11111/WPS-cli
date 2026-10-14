# Phase 4 计划：多环境与 Agent 工作流就绪

状态：**active**（2026-10-14 确认，四项决定均按默认建议）。

## 目标

Phase 3 证明了这套工具在一台 Windows 机器、一个 WPS 版本、一个 Agent 客户端上可用。Phase 4 要回答三个问题：

1. 换一个 WPS 版本还能用吗？
2. 换一个 Agent 客户端还能用吗？
3. Agent 能不能在真实 WPS 上安全地完成写入任务，出错时不用离开 CLI 就能恢复？

同时补上发布流程，让别人能按文档在一台干净的机器上装好并跑通。

## 输入：Phase 3 留下的已知缺口

| 缺口 | 出处 |
| --- | --- |
| 三项 Windows 验证未做：`DOCUMENT_HELD_OPEN` 真机检查、评测任务 `held-document-backup`、回归输出写入 `artifacts\regression\outputs\` | README 状态区 |
| 只在一个 WPS 版本（12.0）上验证过；各转换方向的保真度和跨版本矩阵都没做 | `docs/CONVERSION_MATRIX.md` |
| Agent 评测只有离线任务，没有任何 WPS 写入路径；85 个工具里只用到少数几个 | `docs/AGENT_E2E_EVAL.md` |
| 只验证了 Claude Code CLI；Codex、Claude Desktop 未验证；只支持 stdio 传输 | `docs/ECOSYSTEM_EVALUATION.md` |
| WPS 打开着文档时，自动回滚被文件锁拒绝，用户要自己去 WPS 里关文档再执行 `restore-backup` | `config/project_plan.json` Phase 3 原子事务条件 |
| 版本号仍是 0.1.0，没有变更记录、发布流程，也没在干净机器上验证过安装 | `pyproject.toml` |

## 出口标准

每一条都要有可机器读取的记录（结果 JSON 或提交到仓库的结果文档），只按实测结果判定。

| # | 出口标准 | 怎么算达成 |
| --- | --- | --- |
| E1 | Phase 3 遗留的三项 Windows 验证已记录 | 三项结果写进 `scripts/real_wps_verify_remaining/` 下的结果文档 |
| E2 | 至少两个 WPS 版本的兼容矩阵 | 每个版本都跑通 `regression-run --profile wps --include-wps`，并完成三个组件的打开、保存、导出 PDF 和 HTML；结果按版本记录在新的 `docs/COMPATIBILITY_MATRIX.md`，不一致处写明 |
| E3 | Agent 评测覆盖 WPS 写入路径 | 在 Windows 上新增至少 4 个写入任务（表格写入并校验、Writer 替换、演示替换、被占用文件的拒绝与恢复）。每个任务连续跑 3 次，至少 2 次通过；记录通过率、轮数、工具调用数和工具出错数 |
| E4 | 第二个 MCP 客户端验证通过 | Codex CLI 或 Claude Desktop 完成 `initialize`、分页 `tools/list` 和一次安全的 `tools/call`；记录客户端版本、传输方式和协商的协议版本 |
| E5 | 文档打开时的回滚能在 CLI 内完成 | 提供一个需要显式同意的恢复方式：让 WPS 不保存地关闭该文档，再恢复备份。默认行为不变，仍不会擅自关闭用户的文档。在 Windows 上验证：写入失败、文档开着，用这个方式恢复后文件哈希等于备份 |
| E6 | 可发布 | 有版本号规则和变更记录，CI 构建 wheel；在一台干净的 Windows 上按 README 安装，跑通 `inspect-env` 和 safe 档回归，并记录结果 |

## 已做的决定（不是出口标准）

2026-10-14 确认，均按默认建议：

| 决定 | 依据 | 结论 |
| --- | --- | --- |
| 是否支持 HTTP / SSE 传输 | 有没有目标客户端只能用 HTTP 连接 | Phase 4 不做；等 E4 的结果再定，如果做则单独立项 |
| 是否收缩工具面（85 个） | E3 记录的选错工具次数、多余调用次数 | Phase 4 只收集数据，不改工具面 |
| E2 用哪两个 WPS 版本 | 用户实际在用的版本 | 当前 12.0，再加一个更新或更旧的正式版 |
| E4 先做哪个客户端 | 哪个客户端更快能装好并检查 | Codex CLI（命令行，便于记录） |
| E5 关闭用户文档的尺度 | 关闭会丢掉 WPS 里未保存的改动 | 只在显式同意时关闭；WPS 里有未保存的改动就拒绝；默认行为不变 |

## 任务拆分

| 任务 | 对应标准 | 内容 | 在哪做 |
| --- | --- | --- | --- |
| P4-001 | E1 | 跑完三项遗留的 Windows 验证并记录结果 | Windows |
| P4-002 | E2 | 定出兼容矩阵的检查项和记录格式，新建 `docs/COMPATIBILITY_MATRIX.md` | 本地 |
| P4-003 | E2 | 在 12.0 和第二个 WPS 版本上按 `docs/COMPATIBILITY_MATRIX.md` 跑 C1 到 C6（wps 档、compat 档、三个组件导出 HTML），写入矩阵 | Windows |
| P4-004 | E3 | 评测 runner 支持需要 WPS 的任务：标记 `requires_wps`，没有 WPS 时跳过 | 本地 |
| P4-005 | E3 | 编写 4 个写入任务（表格写入、Writer 替换、演示替换、被占用文件写入被拒），并为每个任务补离线判定测试。被占用文件的"恢复"任务见下方 E5 设计里的说明 | 本地 |
| P4-006 | E3 | runner 支持同一任务连跑 N 次，汇总通过率 | 本地 |
| P4-007 | E3 | 在 Windows 上每个写入任务跑 3 次，记录结果 | Windows |
| P4-008 | E4 | 用 Codex CLI 或 Claude Desktop 完成 MCP 检查，记录结果 | 客户端所在机器 |
| P4-009 | E5 | 设计"需显式同意的关闭再恢复"方式：参数名、提示文字、错误码；默认行为不变 | 本地 |
| P4-010 | E5 | 实现并补离线测试（包括未同意时绝不关闭文档） | 本地 |
| P4-011 | E5 | 在 Windows 上验证打开状态下的恢复：写入失败、回滚被拒后，用 `--close-in-wps` 恢复，文件哈希等于备份；再验证有未保存改动时被拒 | Windows |
| P4-012 | E6 | 定版本号规则，加 `CHANGELOG.md`，CI 构建 wheel 并上传为产物 | 本地 |
| P4-013 | E6 | 在干净的 Windows 上按 README 安装并跑 safe 档回归，记录结果 | Windows |
| P4-014 | 决定 | 根据 E3、E4 的结果，写下是否支持 HTTP 传输、是否收缩工具面 | 本地 |

## E5 设计（P4-009）

文档在 WPS 里打开时，自动回滚会被文件锁拒绝，返回 `MUTATION_ROLLBACK_BLOCKED`。E5 让用户在 CLI 里就能把恢复做完。

| 项 | 设计 |
| --- | --- |
| 入口 | `restore-backup --close-in-wps`；MCP 工具 `wps_agent_restore_backup` 的参数 `close_in_wps` |
| 默认行为 | 不变。不加这个选项时，`restore-backup` 绝不碰 WPS |
| 加了选项、文档没打开或 WPS 没运行 | 没什么可关，照常恢复；结果里 `close_in_wps` 为 `not_open` 或 `no_instance` |
| 加了选项、文档打开且 WPS 里没有未保存的改动 | 在正在运行的 WPS 里不保存地关闭这一个文档，再恢复；`close_in_wps` 为 `closed` |
| 加了选项、文档打开且有未保存的改动 | 拒绝，错误码 `DOCUMENT_HAS_UNSAVED_CHANGES`；不关闭、不恢复、不建恢复前备份 |
| 关闭失败 | 报错（通常为 `COM_OPERATION_FAILED`），不恢复 |
| 顺序 | 先关闭，再建恢复前备份，最后恢复。WPS 占着文件时，备份会被拒绝 |
| `--dry-run` | 只检查不关闭：可以关时 `close_in_wps` 为 `would_close` |
| 幂等 | 同一个 `request_id` 重放时直接返回上次结果，不会再关一次；不带这个选项的旧请求照常重放 |
| 提示 | `MUTATION_ROLLBACK_BLOCKED` 的提示文字写明可以加 `--close-in-wps`，以及有未保存改动时会被拒绝 |

关闭文档只用 WPS 自己报告的"是否已保存"来判断，所以不会丢掉用户在 WPS 里输入但没保存的内容。

Agent 评测里的"被占用文件恢复"任务暂不做：需要 runner 先让 WPS 真的打开文档并让一次写入的回滚被拒，runner 目前做不到。用文件锁模拟也不对，因为关闭脚本只会关 WPS 打开的文档。E5 的验证改为 P4-011 在 Windows 上手动走一遍。

## 建议顺序

1. 先做 P4-001：它关闭 Phase 3 的遗留，也确认现有 Windows 环境还能用。
2. 本地任务可以并行：P4-002、P4-004 至 P4-006、P4-009 和 P4-010、P4-012。
3. Windows 任务尽量合并到同一次上机：P4-001、P4-003、P4-007、P4-011、P4-013。步骤见 `docs/PHASE4_WINDOWS_RUNBOOK.md`。
4. P4-008 和 P4-014 最后做。

## 主要风险

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| 拿不到第二个 WPS 版本 | E2 无法达成 | 尽早确定版本来源；实在拿不到时，把 E2 改为"记录单版本结果和缺口"，并由你确认 |
| 写入类评测结果不稳定 | E3 的通过率波动 | 每个任务跑 3 次，按 2/3 判定；失败时保留完整的工具调用记录 |
| 关闭用户文档有风险 | 用户在 WPS 里没保存的改动会丢失 | 只在显式同意时关闭；关闭前报告文档是否有未保存的改动，有就拒绝 |
| Windows 上机次数有限 | 任务排队 | 按上面的顺序把 Windows 任务合并到一次上机 |
