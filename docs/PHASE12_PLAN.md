# Phase 12 计划：全量评测、干净环境、PyPI 发布，为 1.0 做准备

状态：**planned**（2026-10-17 起草，待确认）。

## 目标

Phase 11 之后，PRD v1.2 的核心需求都已实现，已打开文档的 16 个评测任务连续三轮 16/16。但项目评估（2026-10-17）指出，离“可以正式交给用户用”还差三块：

1. **按文件操作的评测太久没重跑。** 34 个评测任务里有 18 个不是已打开文档任务：备份与恢复、按文件写入 Writer/表格/演示、HTML 表格转文档、Writer 转 PDF 等。它们在 Windows 上最后一次跑是 Phase 4、5（当时 3/4 和 6 个通过），之后七个版本的改动都没有在它们身上重测。
2. **只在一个环境里验证过。** 一台 Windows 10、一个 WPS 版本（12.8.2.18913），而且这个账户上已经跑过上百次评测。从来没有在“从没用过本项目的账户”上，从安装开始走一遍。前几个阶段的问题大多出在真实 WPS 和假 COM 行为不同，换一个环境很可能还有没见过的情况。
3. **用户装不方便，接口也没有定稳。** 没有发布到 PyPI，只能从 GitHub Release 下载 wheel。版本还是 0.x，几乎每个阶段都在给结果加字段，没有一份“哪些东西算对外接口”的清单，也就没法判断什么时候可以定 1.0。

Phase 12 做这三件事，最后发布 0.9.0。是否以及何时定 1.0，仍由你决定，不在本阶段的出口标准里。

## 输入：Phase 11 留下的缺口和项目评估

| 缺口 | 出处 |
| --- | --- |
| 18 个按文件操作的评测任务在 Phase 5 之后没在 Windows 上重跑 | `scripts/windows_check/results/` 里的评测都是 `--prefix wps-open-` 或 `--only` |
| 没有在干净的账户或机器上从安装开始验证过 | P5-010（任务目录里唯一的 todo） |
| 兼容矩阵只有一个 WPS 版本 | `docs/COMPATIBILITY_MATRIX.md`，P5-010 |
| 没有发布到 PyPI | `docs/RELEASING.md` |
| 没有对外接口清单和稳定性规则，无法判断 1.0 | 项目评估 |
| 写入后剩 3 次额外核对；撤回的删除没有 Windows 场景；`0x800A01A8`；PRD 未做项（几何、混排格式、准确页码） | `docs/PHASE11_PLAN.md` 开头 |

## 出口标准

每一条都要有可机器读取的记录（测试、结果 JSON 或提交到仓库的结果文档），只按实测结果判定。

| # | 出口标准 | 怎么算达成 |
| --- | --- | --- |
| M1 | 全部评测任务在当前版本上通过 | Windows：一条 `run_windows_check.py eval --repeat 3 --min-passes 2`（不加 `--prefix`，34 个任务全跑）在本阶段的 `main` 上，每个任务至少 2/3，`wrong_tool_calls` 合计 0，`unverified_writes` 0。没通过的任务在本阶段内查清原因并修复后重跑；因环境原因（比如 Claude API 额度）没跑成的，记下原因后只重跑这些任务 |
| M2 | 干净环境从安装开始可用 | Windows：在一个从没运行过本项目的 Windows 账户上（同机新建的本地账户即可，WPS 已安装并是默认程序），只用 `pip install wps-ai-agent-cli==0.9.0` 从 PyPI 安装，不克隆仓库，依次通过：`inspect-env`；兼容矩阵的 C1 到 C6；`run_windows_check.py undo` 6/6（这一步需要仓库里的脚本，可以在安装后再克隆，但被测的包必须来自 PyPI）。结果写进 `docs/COMPATIBILITY_MATRIX.md` 的新一节 |
| M3 | 发布到 PyPI | 离线：发布流程在创建 GitHub Release 之后用 Trusted Publishing（OIDC，不存 token）把同一组 wheel 和 sdist 上传到 PyPI；`run_windows_check.py wheel` 增加 `--source pypi`，从 PyPI 安装并核对文件的 SHA-256 与 GitHub Release 上的一致；离线测试。你：在 PyPI 上为 `wps-ai-agent-cli` 登记一次 pending publisher。Windows：`wheel --version 0.9.0 --source pypi` 通过全部条件 |
| M4 | 对外接口清单和稳定性规则 | 离线：从代码生成一份对外接口清单（CLI 命令和参数、MCP 工具和参数、错误码、每个命令 `data` 里的顶层字段），提交到仓库；测试在接口变化而清单没更新时失败；`docs/RELEASING.md` 写明 1.0 前后的稳定性规则（哪些变化算破坏性、弃用要提前几个版本、`data` 新增字段算不算破坏）和定 1.0 的检查清单 |
| M5 | 发布 0.9.0 | 按 `docs/RELEASING.md` 发布 `v0.9.0`（M3 的发布流程，GitHub Release 和 PyPI 都有），包含本阶段的改动和 M1 发现的修复；在 Windows 上检查 wheel（即 M3 的 `--source pypi` 检查） |

## 待确认的决定

每条都有默认建议，回复“OK”即按默认执行。

| 决定 | 默认建议 | 依据 | 其他选择 |
| --- | --- | --- | --- |
| Phase 12 做什么 | 上面五件事 | 都来自项目评估；全量评测最便宜，也最能说明按文件那一侧的现状 | 加上撤回删除的 Windows 场景（3 个），或把写入后的 3 次额外核对压到 0 |
| 干净环境用什么 | 同一台机器上新建一个本地 Windows 账户 | 不用新机器就能验证“从没用过本项目”：用户级的 WPS 配置、注册的打开命令、Python 包都从零开始 | 用第二台机器或虚拟机；如果能装到第二个 WPS 版本（比如 11.x 或另一个 12.x），在那里也跑 C1 到 C6，补上兼容矩阵的第二列 |
| PyPI 怎么发 | Trusted Publishing（GitHub Actions 的 OIDC），包名 `wps-ai-agent-cli`（2026-10-17 查过 PyPI 上还没有这个名字），在 GitHub Release 之后上传同一组文件 | 不在仓库或 Secrets 里存 token；同一组文件保证 GitHub 和 PyPI 上的 SHA-256 一致 | 用 API token 存在仓库 Secrets 里（要你生成和轮换 token） |
| M1 没通过怎么办 | 在本阶段内查清并修复，再只重跑没通过的任务；不降低门槛 | 这 18 个任务就是用来发现按文件那一侧的回退的 | 把没通过的任务记成缺口，留到下一阶段 |
| 1.0 | 本阶段只准备清单和规则，不定 1.0 | 定 1.0 意味着承诺接口，按 `docs/RELEASING.md` 由你决定 | 本阶段结束直接发 1.0.0 而不是 0.9.0 |
| 版本号 | 0.9.0 | M3、M4 给发布流程和 `wheel` 检查加了新能力；M1 的修复也可能改变行为；按规则升次版本 | — |

## 任务拆分

| 任务 | 对应标准 | 内容 | 在哪做 |
| --- | --- | --- | --- |
| P12-001 | M1 | 确认 `run_windows_check.py eval` 不加 `--prefix` 时跑全部 34 个任务、准备步骤和清理对按文件的任务也正确（它们不打开 WPS 窗口）；离线检查不需要 WPS 的任务的判定测试都还在、都能过 | 本地 |
| P12-002 | M1 | 在 Windows 上：全部 34 个任务一条命令各跑 3 次 | Windows |
| P12-003 | M1 | 按 P12-002 的结果修复没通过的任务，再只重跑它们 | 本地 + Windows |
| P12-004 | M3 | 发布流程加 PyPI 上传（Trusted Publishing，`id-token: write`，`pypa/gh-action-pypi-publish`）；`docs/RELEASING.md` 写明一次性的 PyPI 登记步骤 | 本地 + 你 |
| P12-005 | M3 | `run_windows_check.py wheel --source pypi`：从 PyPI 安装指定版本，核对 SHA-256 与 GitHub Release 一致；离线测试 | 本地 |
| P12-006 | M4 | 生成对外接口清单的脚本和提交的清单文件；接口变化而清单没更新时失败的测试；`docs/RELEASING.md` 的稳定性规则和 1.0 检查清单 | 本地 |
| P12-007 | M2 | `docs/COMPATIBILITY_MATRIX.md` 加“干净环境”一节的检查项和记录格式；`docs/` 里写干净账户上从安装开始的步骤 | 本地 |
| P12-008 | M5 | 定版本 0.9.0，整理 `CHANGELOG.md`，合并后由你推送 `v0.9.0` 标签 | 本地 + 你 |
| P12-009 | M3、M5 | 在 Windows 上：`wheel --version 0.9.0 --source pypi` | Windows |
| P12-010 | M2 | 在 Windows 的新账户上：从 PyPI 安装 0.9.0，跑 `inspect-env`、C1 到 C6、`undo` | Windows |

## 建议顺序

1. 本地任务先做：P12-001，P12-004 到 P12-007。
2. 第一次上机做 P12-002；有没通过的就做 P12-003。
3. 在 PyPI 上登记 pending publisher，然后做 P12-008，发布 0.9.0。
4. 第二次上机做 P12-009 和 P12-010（P12-010 在新账户上做）。

## 主要风险

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| 34 个任务各 3 次耗时长，跑到一半会话或 API 额度用完 | P12-002 要分几次跑 | `eval --resume` 已经支持接着跑；结果目录和设置不变 |
| 按文件的任务在 Phase 5 之后有回退 | M1 需要修复，阶段变长 | 这正是本阶段要发现的；修复按任务分开提交，只重跑没通过的 |
| PyPI 上传失败（Trusted Publisher 没登记或名字被占） | 0.9.0 只有 GitHub Release | 发布流程先建 GitHub Release 再上传 PyPI，上传失败不影响已有的发布；修好后可以对同一个标签重跑上传那一步 |
| 新账户上 WPS 首次启动有欢迎页、登录框或会话恢复对话框 | 自动化被对话框挡住 | 在新账户上先手动打开一次 WPS 关掉首次启动的界面，并记进步骤；runner 已能记录准备失败的原因 |
| 接口清单太细，每个阶段都要改 | 清单形同虚设 | 清单只列对外的东西（命令、参数、工具、错误码、`data` 顶层字段），不列内部结构；`data` 里新增字段按规则不算破坏 |
