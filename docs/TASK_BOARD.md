# 开发任务调度

## 当前执行策略

以阶段目标拆分任务，Phase 0 先跑通技术事实，再用事实收敛 Phase 1 的实现范围。

## Phase 0 当前任务

| ID | 任务 | 状态 | 验收标准 |
| --- | --- | --- | --- |
| P0-001 | 建立项目骨架与 CLI 入口 | done | `python -m wps_ai_agent_cli inspect-env` 可输出 JSON |
| P0-002 | 实现 WPS ProgID 注册检测 | done | 不启动 WPS，仅检测 COM 注册状态 |
| P0-003 | 建立结构化响应模型 | done | 输出含 ok、request_id、backend、summary、validation、errors |
| P0-004 | 建立阶段任务清单与调度命令 | done | `plan` 与 `tasks` 命令可列出阶段任务 |
| P0-005 | 接入最小 COM 原型 | done | Writer、Spreadsheets、Presentation 均已通过 open/save/close |
| P0-006 | 表格公式计算验证样例 | done | raw value `18.0` 与 display text `18` 验证通过 |
| P0-007 | 转换损失矩阵样例 | done | DOCX 到 PDF 样例已记录后端、前提、保留能力与已知损失 |
| P0-008 | Phase 0 可行性报告 | done | 已形成进入 Phase 1 的 conditional go 结论 |

## Phase 1 预备任务

| ID | 任务 | 状态 | 验收标准 |
| --- | --- | --- | --- |
| P1-001 | document_id 会话模型 | done | 文件可注册、查询，并通过稳定 document_id 定位 |
| P1-002 | 修改前强制备份 | done | 已实现 `backup-document`，可按 document_id 创建恢复备份 |
| P1-003 | 请求 ID 与幂等保护 | done | 同一 request_id 重放时返回已记录结果，不重复创建备份 |
| P1-004 | dry-run 预览 | done | `writer-replace --dry-run` 可预览正文匹配数且不修改文件 |
| P1-005 | 基础验证钩子 | done | `validate-document` 支持 Writer 正文文本与 Spreadsheet 单元格值验证 |
| P1-006 | 任务状态台账 | done | `operation` 和 `operations` 可查询 request_id 与历史操作 |
| P1-007 | 批量文件状态报告 | done | `scan-dir` 可输出逐文件组件、大小与注册状态 |
| P1-008 | Phase 1 汇总报告 | done | 已汇总 MVP CLI 能力、已验证命令、剩余缺口与下一步优先级 |
| P1-009 | Writer 范围替换扩展 | done | `writer-replace --paragraph-index` 支持 1-based 段落范围替换，dry-run 与验证范围一致 |
| P1-010 | Spreadsheet 区域读写 | done | A1 范围读取与写入支持备份、COM 写入、读回校验和幂等重放 |
| P1-011 | Presentation 占位符文本替换 | done | 支持演示文稿占位符或文本框替换，并具备备份、验证和幂等 |
| P1-012 | Spreadsheet 公式写入与重算 | done | 支持表格公式写入、触发 WPS 计算，并验证缓存结果 |
| P1-013 | 验证快照扩展 | done | 增加 docx 文本结构、xlsx 公式错误、pptx 文本对象计数等更强验证 |
| P1-014 | 批量执行报告 | done | 合并目录扫描、注册状态和验证快照，输出批量处理报告 |
| P1-015 | 备份清单与恢复 | done | 可按 document_id 列出可恢复备份，并安全恢复指定备份 |
| P1-016 | Phase 1 发布候选审计 | done | 运行最终能力审计，记录剩余缺口并形成 Phase 1 release candidate 报告 |

## Phase 2 当前任务

| ID | 任务 | 状态 | 验收标准 |
| --- | --- | --- | --- |
| P2-001 | 长任务状态模型 | done | 为长时间 WPS 操作建立可复用状态模型，包含进度、终态和恢复建议 |
| P2-002 | 修改命令接入任务状态 | done | 将任务状态创建与终态更新接入选定的 WPS 修改命令，同时保持既有幂等行为 |
| P2-003 | 长任务恢复手册 | done | 为中断、失败和状态不明确的长时间 WPS 操作整理并暴露恢复手册 |
| P2-004 | MCP 工具契约草案 | done | 将当前 CLI 命令映射为可复用的 Agent/MCP 工具契约和示例 |
| P2-005 | MCP adapter 实现 | done | 基于契约草案实现可调用的 MCP adapter 层，并复用现有 CLI 核心逻辑 |
| P2-006 | MCP server 原型 | done | 将 adapter 工具通过标准 MCP-compatible transport 暴露为本地 server 原型 |
| P2-007 | MCP server client 配置与 smoke harness | done | 记录本地 MCP server 客户端配置，并补充 initialize、tools/list、tools/call 可重复 smoke |
| P2-008 | MCP desktop 集成审计 | done | 用桌面客户端配置审计本地 MCP server，记录 transport、路径和环境变量问题 |
| P2-009 | Phase 2 最终交付报告 | done | 汇总 MCP readiness、验证证据、已知边界和后续可选扩展方向 |

## Phase 3 当前任务

| ID | 任务 | 状态 | 验收标准 |
| --- | --- | --- | --- |
| P3-001 | 生产就绪计划与风险清单 | done | 定义 Phase 3 workstreams、风险、验收门槛和首批回归目标 |
| P3-002 | 回归套件 manifest 与 smoke matrix | done | 创建机器可读回归清单，覆盖关键 CLI、MCP 与 WPS smoke 场景 |
| P3-003 | 回归 manifest WPS smoke 执行 | done | 在真实桌面环境运行 WPS-required 回归 profile，记录组件级证据和缺口 |
| P3-004 | 回归结果 artifact 导出 | done | 将 regression-run 输出持久化为带时间戳的 JSON artifact，用于 CI、审计和后续对比 |
| P3-005 | 回归 artifact CI 交接 | done | 记录 CI 调用方式、artifact 留存路径，以及 safe/WPS 回归 profile 的通过门槛 |
| P3-006 | 恢复硬化演练 | done | 定义并执行一次针对中断或失败修改类文档操作的恢复演练，包含恢复证据 |
| P3-007 | 安全边界审计 | done | 审计修改类 CLI 与 MCP 工具的 request_id、dry-run、backup、恢复建议和风险边界 |
| P3-008 | 性能基线采集 | done | 采集核心只读命令和 safe 回归命令的耗时、输出规模和证据，不启动 WPS |
| P3-009 | Desktop MCP 集成证据刷新 | done | 基于当前工具面刷新 MCP desktop 集成证据，覆盖 config audit、tools/list、tools/call 和真实 client 缺口 |
| P3-010 | 高级 WPS 能力定范围 | done | 选择下一个高级 WPS 能力，并在实现前定义 fixture、dry-run、backup、validation 和 smoke 证据要求 |
| P3-011 | Writer 表格单元格更新原型 | done | 实现 Writer 表格单元格更新，包含 fixture、dry-run、backup、读回验证、MCP schema 和 WPS smoke 证据 |
| P3-012 | Writer 表格回归集成 | done | 将 Writer 表格更新纳入回归证据、恢复检查和可重复 WPS smoke 文档，同时避免 safe CI 启动桌面 WPS |
| P3-013 | Spreadsheet WPS calc timeout 调查 | done | 诊断并硬化完整 WPS 回归 profile 暴露出的 spreadsheet calc smoke 超时，同时保留结构化回归 artifact |
| P3-014 | WPS 进程生命周期清理审计 | done | 审计 WPS COM smoke 命令的进程生命周期清理，采集残留进程诊断，并记录不自动杀用户进程的安全清理建议 |
| P3-015 | Phase 3 release readiness 刷新 | done | 刷新 Phase 3 发布就绪证据，总结当前 safe/WPS 回归状态，并列出剩余生产风险和交接步骤 |
| P3-016 | 云端同步就绪交接 | done | 准备将当前本地项目状态同步到云端或远程项目工作区所需的 artifact、证据路径和仓库交接说明 |
| P3-017 | 本地工作区同步模式确认 | done | 确认项目后续继续保留在当前本地工作区，保留本地同步包证据，并移除远程 Git/cloud 上传作为阻塞要求 |
| P3-018 | 本地工作区连续性审计 | done | 审计当前本地工作区 artifact、生成包、WPS 输出和状态目录，识别后续本地开发需要的清理、留存和可复现动作 |
| P3-019 | 本地清理策略与授权 | done | 定义本地-only 开发的保守清理策略，并仅在用户授权后移除被取代的 probe、旧 artifact 或过期恢复文件 |
| P3-020 | 本地可复现命令包 | done | 创建本地-only 可复现命令包，可在不依赖远程 Git 或云端的情况下重跑测试、safe regression、cleanup-plan 和同步打包 |
| P3-021 | 本地清理执行授权检查点 | done | 与用户复核 cleanup-plan 候选项；除非明确授权具体路径或类别，否则不执行任何移除 |
| P3-022 | 本地项目状态摘要 | done | 暴露本地-only 项目状态命令，汇总 next 任务、MCP 工具数、清理姿态、最新 artifact 和同步包状态 |
| P3-023 | 文档新鲜度扫尾 | done | 刷新仍引用过期工具数、旧 next 任务或远程 Git/cloud 假设的用户文档 |
| P3-024 | 文档扫尾后的本地包刷新 | done | 在文档更新后重新生成本地同步包，并记录刷新后的 hash 与回归证据 |
| P3-025 | 授权清理执行闸门 | done | 仅在用户明确批准 cleanup-plan 的具体类别或路径后执行清理；否则保留全部候选并继续本地开发 |
| P3-026 | 清理授权清单导出 | done | 暴露只读清理授权清单，按精确清理类别和路径分组，供未来用户明确授权使用 |
| P3-027 | 本地工作区健康摘要 | done | 新增只读本地工作区健康摘要，组合 project status、清理授权姿态、回归新鲜度和同步包证据 |
| P3-028 | 健康摘要后的本地包刷新 | done | 在 workspace-health 新增后重新生成本地同步包，并验证 project-status 与 workspace-health 报告刷新后的证据 |
| P3-029 | Phase 3 本地-only 状态汇总 | done | 将最新本地-only 状态、health、清理闸门和同步包证据合并为一份 Phase 3 状态说明 |
| P3-030 | 下一项高级能力选择 | done | 在本地-only 稳定后选择下一个非破坏性 Phase 3 开发目标，并在实现前记录范围、验证和安全约束 |
| P3-031 | MCP 工具目录快照 | done | 实现只读 MCP 工具目录快照命令，汇总工具数量、分类、修改/WPS 要求和 safety-note 覆盖情况 |
| P3-032 | 工具目录后的本地包刷新 | done | 在 MCP 工具目录快照后重新生成本地同步包，并验证 safe regression、project status 和 workspace health 使用刷新后的工具面 |
| P3-033 | 工具目录快照文档刷新 | done | 刷新 README 和 MCP 文档，提及 mcp-catalog-snapshot 与当前 47-tool 工具目录面 |
| P3-034 | 工具目录文档后的本地包刷新 | done | 在工具目录快照文档刷新后重新生成本地同步包，并验证 project status、workspace health 和 safe regression 证据仍然最新 |
| P3-035 | MCP 工具目录漂移闸门定范围 | done | 定义一个非破坏性的 MCP catalog drift guard，让后续工具数量、分类和 safety-note 变更在打包前更容易审查 |
| P3-036 | MCP 工具目录漂移闸门实现 | done | 实现一个基于显式 baseline 的只读 MCP catalog drift guard，并纳入 safe regression，且不启动 WPS |
| P3-037 | 漂移闸门后的本地包刷新 | done | 在 MCP catalog drift guard 后重新生成本地同步包，并验证 safe regression、project status、workspace health 和包证据 |
| P3-038 | 下一项非破坏性能力选择 | done | 在 MCP catalog drift guard 后选择下一项非破坏性本地开发目标，并在实现前记录范围、验证和安全约束 |
| P3-039 | 回归证据摘要 | done | 实现只读 regression evidence summary，汇总最新 safe 与 WPS 回归 artifact，且不启动 WPS 或修改文件 |
| P3-040 | 回归证据摘要后的本地包刷新 | done | 在 regression-evidence 后重新生成本地同步包，并验证测试、safe regression、project status、workspace health、catalog drift 和包证据 |
| P3-041 | 下一项非破坏性能力选择 | done | 在 regression evidence summary 后选择下一项非破坏性本地开发目标，并在实现前记录范围、验证和安全约束 |
| P3-042 | 本地交接摘要 | done | 实现只读 local handoff summary，组合 project status、workspace health、regression evidence、catalog drift 和同步包证据 |
| P3-043 | 本地交接摘要后的本地包刷新 | done | 在 local-handoff-summary 后重新生成本地同步包，并验证测试、safe regression、local handoff、project status、workspace health、catalog drift 和包证据 |
| P3-044 | 下一项非破坏性能力选择 | done | 在 local handoff summary 后选择下一项非破坏性本地开发目标，并在实现前记录范围、验证和安全约束 |
| P3-045 | artifact 留存摘要 | done | 新增只读 artifact retention summary，汇总保留证据、清理候选、审批姿态和同步包状态，不删除文件 |
| P3-046 | artifact 留存摘要后的本地包刷新 | done | 在 artifact-retention-summary 后重新生成本地同步包，并验证测试、safe regression、retention summary、project status、workspace health、catalog drift 和包证据 |
| P3-047 | 下一项非破坏性能力选择 | done | 在 artifact retention summary 与本地包刷新后选择下一项非破坏性本地开发目标，并在实现前记录范围、验证和安全约束 |
| P3-048 | 本地验证 runbook | done | 新增只读 validation runbook，返回快速检查、safe regression、本地打包、可选 WPS 验证和清理复核步骤，但不执行命令 |
| P3-049 | validation runbook 后的本地包刷新 | done | 在 validation-runbook 后重新生成本地同步包，并验证测试、safe regression、validation runbook、project status、workspace health、catalog drift 和包证据 |
| P3-050 | 下一项非破坏性能力选择 | done | 在 validation runbook 与本地包刷新后选择下一项非破坏性本地开发目标，并在实现前记录范围、验证和安全约束 |
| P3-051 | 文档新鲜度闸门 | done | 新增只读 documentation freshness guard，扫描当前文档和配置中的旧工具数、旧 expected-min-tools 或旧 next 任务引用，不自动编辑文件 |
| P3-052 | documentation freshness 后的本地包刷新 | done | 在 documentation-freshness 后重新生成本地同步包，并验证测试、safe regression、documentation freshness、project status、workspace health、catalog drift 和包证据 |
| P3-053 | 下一项非破坏性能力选择 | done | 在 documentation freshness 与本地包刷新后选择下一项非破坏性本地开发目标，并在实现前记录范围、验证和安全约束 |
| P3-054 | 回归历史摘要 | done | 新增只读 regression history summary，汇总最近 safe/WPS 回归 artifact、通过趋势和最新结果，不运行回归或启动 WPS |
| P3-055 | regression history 后的本地包刷新 | done | 在 regression-history 后重新生成本地同步包，并验证测试、safe regression、regression history、project status、workspace health、catalog drift 和包证据 |
| P3-056 | 下一项非破坏性能力选择 | done | 在 regression history 与本地包刷新后选择下一项非破坏性本地开发目标，并在实现前记录范围、验证和安全约束 |
| P3-057 | 同步包检查 | done | 新增只读 `sync-package-inspect` / `wps_agent_sync_package_inspect`，检查已有同步包 hash、条目数、默认根目录覆盖和打包时最新 safe/WPS 回归 artifact 收录情况 |
| P3-058 | sync-package-inspect 后的本地包刷新 | done | 在 sync-package-inspect 后重新生成本地同步包，并验证测试、safe regression、包检查、project status、workspace health、catalog drift 和 documentation freshness |
| P3-059 | 下一项非破坏性能力选择 | done | 在 sync package inspection 与本地包刷新后选择下一项非破坏性本地开发目标，并在实现前记录范围、验证和安全约束 |
| P3-060 | 同步包内容摘要 | done | 新增只读 `sync-package-summary` / `wps_agent_sync_package_summary`，汇总已有同步包的顶层目录分布、artifact 条目和最大条目，不创建包、不删除文件、不启动 WPS、不使用远程 Git |
| P3-061 | sync-package-summary 后的本地包刷新 | done | 在 sync-package-summary 后重新生成本地同步包，并验证测试、safe regression、包摘要、project status、workspace health、catalog drift 和 documentation freshness |
| P3-062 | 下一项非破坏性能力选择 | done | 在 sync package summary 与本地包刷新后选择下一项非破坏性本地开发目标，并在实现前记录范围、验证和安全约束 |
| P3-063 | 同步包 manifest | done | 新增只读 `sync-package-manifest` / `wps_agent_sync_package_manifest`，列出已有同步包条目并支持 prefix 过滤，不创建包、不删除文件、不启动 WPS、不使用远程 Git |
| P3-064 | sync-package-manifest 后的本地包刷新 | done | 在 sync-package-manifest 后重新生成本地同步包，并验证测试、safe regression、包 manifest、project status、workspace health、catalog drift 和 documentation freshness |
| P3-065 | 下一项非破坏性能力选择 | done | 在 sync package manifest 与本地包刷新后选择下一项非破坏性本地开发目标，并在实现前记录范围、验证和安全约束 |
| P3-066 | 同步包覆盖率检查 | done | 新增只读 `sync-package-coverage` / `wps_agent_sync_package_coverage`，按包创建时间比较工作区同步根目录与包内条目覆盖情况，不创建包、不删除文件、不启动 WPS、不使用远程 Git |
| P3-067 | sync-package-coverage 后的本地包刷新 | done | 在 sync-package-coverage 后重新生成本地同步包，并验证测试、safe regression、包覆盖率、project status、workspace health、catalog drift 和 documentation freshness |
| P3-068 | 下一项非破坏性能力选择 | done | 在 sync package coverage 与本地包刷新后选择下一项非破坏性本地开发目标，并在实现前记录范围、验证和安全约束 |
| P3-069 | 同步包交接就绪摘要 | done | 新增只读 `sync-package-readiness` / `wps_agent_sync_package_readiness`，汇总 inspect、summary 和 coverage，判断现有同步包是否适合本地交接，不创建包、不删除文件、不启动 WPS、不使用远程 Git |
| P3-070 | sync-package-readiness 后的本地包刷新 | done | 在 sync-package-readiness 后重新生成本地同步包，并验证测试、safe regression、包 readiness、project status、workspace health、catalog drift 和 documentation freshness |
| P3-071 | 下一项非破坏性能力选择 | done | 选定现有同步包内容完整性修复，范围见 P3_PACKAGE_CONTENT_INTEGRITY.md |
| P3-072 | 同步包内容完整性 | done | SHA-256 检查内容，识别重复及过期条目，保留时间戳修改回归验证 |
| P3-073 | 产品需求证据审计 | done | 已记录原始 PRD 与实现差距，见 P3_PRODUCT_REQUIREMENTS_AUDIT.md |
| P3-074 | 演示逻辑页序与空白页 | done | 按 presentation relationships 解析页序，保留空白页，验证重排演示的定向读取与替换预检 |
| P3-075 | Writer 标题、样式与书签快照 | done | 保留段落索引，补充大纲级别、样式与书签位置，明确不支持范围并验证文件未修改 |
| P3-076 | Writer 逻辑文本验证 | done | 修复跨文本运行、XML 转义与属性误匹配，验证正文及段落范围的读取与替换预检 |
| P3-077 | Writer 替换范围与段落定位 | done | 四种替换已通过本机 WPS 实测，范围外段落与表格未变化，见 P3_WRITER_REPLACE_SCOPE.md |
| P3-078 | Writer 替换精确读回验证 | done | 比较保存后的完整逻辑段落，覆盖同词替换和范围外变化，见 P3_WRITER_EXACT_READBACK.md |
| P3-079 | Writer 书签填充 | done | 完成同正文段落的具名书签预览、WPS 填充、备份、精确读回及本机实测，边界见 P3_WRITER_BOOKMARK_FILL.md |
| P3-080 | 表格公式、缓存与显示值读回 | done | 新增 spreadsheet-inspect 与 MCP 只读工具；公式/缓存/WPS 重算/显示文本分层，并完成数字、日期、错误、空值及文件不变性实测，见 P3_SPREADSHEET_INSPECT.md |
| P3-081 | 表格读取显示格式契约 | done | 保留 values 矩阵兼容，新增并行 cell_metadata 矩阵；离线及 WPS 对照覆盖日期、百分比、货币和空值，见 P3_SPREADSHEET_READ_FORMATS.md |
| P3-082 | 表格范围读取防护 | done | spreadsheet-read/inspect 共用 A1 校验；拒绝畸形、无界、越界和超过 10,000 格范围，拒绝时不打开文件或探测 WPS，见 P3_SPREADSHEET_RANGE_GUARDRAILS.md |
| P3-083 | 演示文稿文本对象覆盖 | done | 快照识别表格为单一文本对象、组合形状内文本框按 XML 顺序保留且不重复，新增 object_type，见 P3_PRESENTATION_TEXT_OBJECT_COVERAGE.md |
| P3-084 | 演示文稿嵌套文本替换契约 | done | WPS 递归处理组合形状并逐格处理表格；替换数精确匹配且逐页文本读回一致，真实 WPS 覆盖 2 个组合文本框和 2x2 表格，见 P3_PRESENTATION_NESTED_REPLACE.md |
| P3-085 | 演示文稿替换格式保留 | done | 原位替换命中区间并继承首字符格式，WPS/OOXML 验证前缀、替换文本和后缀 run 样式，见 P3_PRESENTATION_FORMAT_PRESERVATION.md |
| P3-086 | 演示文稿对象级替换读回 | done | 按段落/单元格统计命中并逐对象精确对比有序读回，拒绝跨对象边界假命中，见 P3_PRESENTATION_OBJECT_READBACK.md |
| P3-087 | 文档变更幂等参数绑定 | done | 统一 operation replay 校验命令和全部绑定参数；冲突在备份/WPS 前返回 IDEMPOTENCY_CONFLICT，书签内容以 SHA-256 绑定，见 P3_MUTATION_IDEMPOTENCY.md |
| P3-088 | 表格写入范围防护 | done | spreadsheet-write/formula-write 复用有限 A1 校验及 10,000 格上限；错误在备份/WPS 前返回，矩阵形状规则保留，见 P3_SPREADSHEET_WRITE_GUARDRAILS.md |
| P3-089 | 表格工作表清单 | done | 新增 spreadsheet-sheets 及只读 MCP 工具；返回工作表顺序、名称、visibility 和 used dimensions，文件哈希保持不变，见 P3_SPREADSHEET_SHEETS.md |
| P3-090 | 表格工作表重命名事务 | done | 新增 spreadsheet-rename-sheet/MCP；Excel 名称校验、dry-run、备份、WPS 重命名、完整顺序读回与幂等冲突处理均验证通过，见 P3_SPREADSHEET_RENAME_SHEET.md |
| P3-091 | 表格工作表创建事务 | done | spreadsheet-create-sheet/MCP 已支持 dry-run、名称与位置校验、备份、WPS 创建、顺序读回和 request_id 参数绑定；模拟与本机 WPS 集成验证通过 |
| P3-092 | 表格工作表可见性事务 | done | 新增 spreadsheet-set-sheet-visibility CLI/MCP；隐藏最后一个可见工作表前拒绝，提交前备份，WPS 保存后验证有序可见状态并绑定 request_id |
| P3-093 | 表格工作表删除事务 | done | 新增 spreadsheet-delete-sheet CLI/MCP；dry-run 展示删除后的顺序，阻止删除最后工作表，提交前备份并验证 WPS 有序读回和 request_id |
| P3-094 | 表格工作表复制事务 | done | 新增 spreadsheet-copy-sheet CLI/MCP，支持 dry-run、名称/位置校验、WPS 原生复制、备份、有序名称与样例单元格读回及 request_id 绑定 |
| P3-095 | 表格工作表标签颜色事务 | done | 新增 spreadsheet-set-sheet-tab-color CLI/MCP，严格接受 #RRGGBB/none，提交前备份并通过 WPS 与独立工作簿读回校验；本机设置及清除集成测试通过 |
| P3-096 | 表格工作表标签颜色清单 | done | spreadsheet-sheets 新增 none/#RRGGBB 规范化颜色字段；既有哈希不变、WPS 不启动的断言覆盖该字段 |
| P3-097 | 表格工作表保护状态清单 | next | 扩展只读工作表清单，返回工作表保护状态与受保护单元格计数，不暴露密码、不改写文件且不启动 WPS |
| P3-097 | 表格工作表保护状态清单 | done | spreadsheet-sheets 返回 protection_enabled、最多扫描 100,000 格的 protected_cell_count 及 protection_scan_truncated；不返回保护密码、不启动 WPS，哈希不变测试覆盖普通与超限工作表 |
| P3-098 | 表格清单有界扫描契约 | done | 更新 P3_SPREADSHEET_SHEETS.md 说明元数据和 100,000 格扫描限制；单测覆盖超限截断字段及文件哈希不变 |
| P3-099 | 表格清单公式元数据 | done | spreadsheet-sheets 新增 populated_cell_count/formula_count，并复用 100,000 格边界；超限明确返回 null 和 inventory_scan_truncated，单测覆盖公式及哈希不变 |
| P3-100 | 表格清单视图元数据 | done | spreadsheet-sheets 返回 freeze_panes 和 autofilter_range；单测验证值、WPS 未启动及文件哈希不变 |
| P3-101 | 表格清单合并区域元数据 | done | 返回稳定排序的合并区域清单，最多 1,000 项并报告完整数量/截断标志；测试覆盖 1,002 区域与哈希不变 |
| P3-102 | 表格清单命名区域元数据 | done | spreadsheet-sheets 以稳定作用域/名称排序返回最多 1,000 个定义名称及目标，报告总数和截断标记；测试覆盖超限、文件哈希和无 WPS |
| P3-103 | 表格清单计算模式元数据 | done | 返回 calcMode/fullCalcOnLoad/forceFullCalc/calcOnSave/iterate 原始存储标记；单测设置 manual 与 force-full 并验证哈希及无 WPS |
| P3-104 | 表格清单宏工作簿兼容 | done | xlsm 清单启用 VBA 保留读取并显式关闭辅助归档；哈希不变、WPS 未启动、公式及受限扫描测试通过 |
| P3-105 | 表格清单打印元数据 | done | 返回 print_area/title rows/columns、方向及纸张编码；测试校验归一化范围与哈希不变、无 WPS |
| P3-106 | 表格清单分页符元数据 | done | 返回排序的行/列分页符，最多 1,000 项并带总数/截断字段；测试验证超限、哈希不变及无 WPS |
| P3-107 | 表格清单端到端验证 | done | CLI 测试验证扩展 inventory 字段保持在 response 中；MCP adapter/schema 明确 mutates_document=false、requires_wps=false |
| P3-108 | 表格清单数据验证元数据 | done | 返回最多 1,000 条排序验证范围/类型/操作符/空值策略及总数/截断标志；测试覆盖超限、无 WPS 和哈希不变 |
| P3-109 | 表格清单条件格式元数据 | done | 返回最多 1,000 条稳定排序的条件格式区域/类型/操作符/优先级，附总数及截断标志；测试覆盖超限和哈希不变 |
| P3-110 | 表格清单错误忽略规则 | done | 流式解析 OOXML ignoredErrors，输出最多 1,000 条范围/标记、完整计数和截断；xlsm 测试覆盖 1,002 项且哈希不变、无 WPS |
| P3-111 | 表格清单结构集成验证 | done | 新增 CLI 端到端 xlsx/xlsm 双次读取测试，完整元数据输出稳定、公式计数正确、源文件哈希不变 |
| P3-112 | 表格清单契约文档 | done | 补充 MCP 工具说明的完整清单能力与只读边界，并校正 PRD 审计中已完成的表格工作表管理项 |
| P3-113 | 表格日期与区域兼容性 | done | 覆盖 1900/1904 日期系统、区域标签格式、公式和 WPS 实际显示；当前 WPS 遵循主机区域显示，哈希不变，证据见 P3_SPREADSHEET_DATE_LOCALE_COMPAT.md |
| P3-114 | HTML 视觉优先转换 | done | 本地 Edge/Playwright PDF 与 PNG 渲染，默认禁用 JS、阻断网络并限制本地资源；真实浏览器集成与非空图像检查通过 |
| P3-115 | HTML 可编辑优先语义转换 | done | 新增 `html-editable`/`wps_agent_html_editable`，将语义结构映射到原生可编辑 DOCX 对象并回报 CSS/资源降级 |
| P3-116 | HTML 受控往返对象身份模型 | done | 新增 `html-roundtrip-plan`/MCP 只读校验，要求 schema v1、稳定且唯一对象 ID，生成确定性 native-index/parent/hash 映射并拒绝 CSS/脚本/不支持特性 |
| P3-117 | HTML 受控往返 DOCX 导入和身份读回 | done | 新增 `html-controlled-import` 持久化 sidecar 与 DOCX 原生书签；`html-roundtrip-verify` 允许文本编辑但检测书签缺失、重复、未知和同类型重排 |
| P3-118 | 受控 DOCX 回写为 owned HTML | done | 新增 `html-roundtrip-export`/MCP 导出，先验证 sidecar/bookmark，再保留对象身份序列化并拒绝不支持内容 |
| P3-119 | 批量转换逐文件结果 | done | 新增 `html-batch-convert` 支持目录内 HTML 转 PDF/PNG/DOCX，最多 100 个文件，单文件失败隔离并写入 SHA-256 来源清单 |
| P3-120 | 批量转换 MCP 接入 | done | 新增 `wps_agent_html_batch_convert`，支持格式/递归/任务追踪参数；adapter 实际 DOCX 批次调用和安全审计通过 |
| P3-121 | 模板报告生成 | done | 新增 `batch-template-report`，严格校验批次摘要/哈希，仅渲染白名单模板字段并禁止覆盖；批次转报告端到端测试通过 |
| P3-122 | 模板报告 MCP 接入 | done | 新增 `wps_agent_batch_template_report`，校验 manifest/模板字段后写新报告；实际 adapter 调用及安全审计通过 |
| P3-123 | HTML 批量浏览器集成覆盖 | done | Edge 实测批量 PDF/PNG；验证非空文件、逐文件 SHA-256 及 JavaScript/网络关闭 |
| P3-124 | HTML 批量 DOCX 的 WPS 兼容性 | done | 两个批次 DOCX 分别经 Writer 打开和另存，验证原始正文文本保留 |
| P3-125 | 受控 HTML 富媒体 WPS 往返 | done | 修复图片书签落位及 WPS HYPERLINK 字段回读；实测图片、超链接、对象 ID 和目标地址往返保留 |
| P3-126 | DOCX 模板批量报告输出 | done | 新增 DOCX 模板摘要占位符和重复行，保留表格/文字样式；分裂、未知字段拒绝；WPS Writer 打开保存通过 |
| P3-127 | 多页 DOCX 批量报告完整性 | done | 50 行报告经 WPS Writer 打开另存后仍完整，WPS PDF 导出实际多页且总计/来源行均可核验 |
| P3-128 | 批次报告资源边界加固 | done | DOCX ZIP 条目/解压量/压缩比及 manifest 来源/输出累计字节均受限；先预检后流式哈希，超限/篡改测试通过 |
| P3-129 | 受控列表与表格 WPS 往返保真 | done | WPS Writer 往返后有序/无序列表及多行表头/正文表格的对象 ID、类型、序号均一致 |
| P3-130 | 批处理进度与取消 | done | `task_id` 下逐文件更新进度；task-status-update 取消后在文件边界停止并写入部分 manifest，实时状态轮询集成测试通过 |
| P3-131 | 取消批次报告交付 | done | 取消 manifest 渲染为 DOCX 后经 WPS Writer 往返，计划数/已处理数/取消状态及完成行均保留 |
| P3-132 | MCP 批转换取消工作流 | done | 真实 stdio MCP 会话中发起批转换，再通过后续 task-status MCP 请求取消；部分结果与 cancelled 终态均已验证 |
| P3-133 | MCP 批请求并发限制 | done | stdio MCP 会话仅允许一个在途批转换；重叠调用返回 -32000 busy，task-status 取消仍可执行 |
| P3-134 | 批处理期间 MCP 协议错误隔离 | done | 批处理运行时畸形 JSON 返回 parse error、无效 JSON-RPC 返回 -32600，批任务及 task ID 不受影响 |
| P3-135 | MCP 批任务响应生命周期 | done | EOF 时活动批请求恰好返回一次；正常完成与取消均有覆盖，executor 在 serve_stdio 返回前收束 |
| P3-136 | MCP 批工作线程异常隔离 | done | worker 未预期异常以 -32603 返回且不泄露异常内容；后续 tools/list 正常响应 |
| P3-137 | MCP stdio 请求生命周期回归 | done | 筛选后套件共 253 项：231 通过、22 跳过；另有 3 项历史状态敏感测试未运行，不能据此声称完整回归全绿 |
| P3-138 | MCP 文档与工具目录核验 | done | 文档 freshness、76 项 MCP 工具目录、config audit 与 45 个 MCP schema/smoke/server/adapter/security 测试均通过 |
| P3-139 | MCP 生命周期工作后的本地同步包刷新 | done | 本地包 250 项、SHA-256 A23527FB616A4189AEB64364A35D158EE7D40A0873E91163F0731D7061337FF9；readiness 全部通过，未远程上传 |
| P3-140 | 打包后工作区一致性核验 | done | 最终包 250 项、SHA-256 64DBDF5B611CFBF6867F75D18A85ED86F5B643F07B7909138D5CC44C6727B800；readiness、doc freshness 和 next-task 检查均通过 |
| P3-141 | MCP stdio 生命周期用户文档 | done | 客户端文档补充并发限制、-32000 busy、task_id 协作取消、EOF 收束与 -32603 异常行为；文档 freshness 及 41 项相关测试通过 |
| P3-142 | MCP 生命周期发布证据刷新 | done | 本地包 250 项且 readiness 通过；MCP smoke 76 工具通过，文档 freshness 显示 P3-142 为 next |
| P3-143 | MCP adapter stdout 隔离回归 | done | MCP adapter 与显式 CLI 输出流测试通过；20 个 adapter 测试通过且 stdout 未被污染 |
| P3-144 | stdout 隔离后的本地包刷新 | done | 本地包 250 项，readiness passed、缺失/过期均为 0；文档 freshness 通过，adapter/server 28 项测试通过 |
| P3-145 | MCP stdio 发布检查点复核 | done | 修复保持 stdin 打开时批响应不发送的问题；真实子进程连续两批 DOCX 验证通过，server/adapter 30 项通过；剩余状态竞争见 P3-146 |
| P3-146 | 并发任务状态持久化 | done | 线程及跨进程锁保护读改写；JSON 原子替换；4 进程 48 条记录、取消终态和替换失败保留原文件测试通过 |
| P3-147 | 回归测试证据确定性 | done | 明确 manifest fixture 实测执行及落盘；性能汇总用固定结果；失败传播测试通过，完整套件不再排除历史敏感用例 |
| P3-148 | 嵌套 CLI 输出隔离 | done | regression/performance 改用显式输出流；并发验证其他线程 stdout 保持不变；完整套件 267 项：245 通过、22 跳过 |
| P3-149 | 任务 ID 归属与复用验证 | done | command/request/document 三字段冲突返回 TASK_ID_CONFLICT，原状态不变且不执行操作；匹配请求保留原 handler 重放路径 |
| P3-150 | 任务启动取消预检 | done | failed/cancelled 任务不可原地重启；创建到 running 之间被取消时拒绝执行；相关 71 项测试通过 |
| P3-151 | 已完成 HTML 批请求重放 | done | request_id 工作区级登记；相同请求校验参数、源文件清单及源/产物哈希后重放，MCP 验证未再次渲染；276 项测试通过（22 跳过） |
| P3-152 | 中断的 HTML 批任务完成恢复 | done | 遗留 running 请求经完整 manifest 与哈希验证后升级成功并重放；缺失或损坏证据继续拒绝，定向 70 项测试通过（2 跳过） |
| P3-153 | HTML 批请求记录容量与恢复 | done | 新请求改为每 request_id 独立 16 KiB 记录，旧 4 MiB JSON 只读兼容；超额拒绝、损坏阻断及旧记录恢复验证通过 |
| P3-154 | 批请求记录写入故障隔离 | done | 创建故障阻止转换；终态写入故障保留 manifest/产物，后续经哈希验证恢复；定向 73 项测试通过（2 跳过） |
| P3-155 | 跨进程 HTML 批请求重放 | done | 两个独立 CLI 进程复用同一 request_id；第二次返回 replayed 且 DOCX 内容/时间不变，改输出目录返回冲突 |
| P3-156 | HTML 批请求状态查询 | done | 新增只读 CLI/MCP 查询，读取新旧记录状态、参数、manifest 与恢复建议；工具目录 77 项，88 项定向测试通过（2 跳过） |
| P3-157 | MCP smoke 带参数调用 | done | 增加 --arguments-json；带参数调用限已核实的本地只读查询命令，批转换/打包均拒绝；39 项相关测试通过 |
| P3-158 | HTML 批请求证据验证查询 | done | CLI/MCP 查询增加 --verify，复用完整源/产物哈希验证；记录成功而文件损坏时以 warning 与 evidence_status=failed 区分 |
| P3-159 | 当前本地发布门槛审计 | done | 发现并解除 safe 与历史证据间的循环；真实 safe 15/15、release 3/3 通过，保留旧失败产物 |
| P3-160 | 本地发布门槛顺序自动化 | done | 新增 `local-release-gates` CLI/MCP，真实五步运行全通过并留存 safe/release 产物；失败即停，不使用远程 Git 或启动 WPS |
| P3-161 | Writer 结构检查范围 | done | 新增 `writer-structure` CLI/MCP，标题/样式/书签和警告计数、至多 200 条样本、截断标记与离线证据边界；293 项测试通过（22 跳过） |
| P3-162 | Writer 结构分页与精确查询 | done | 加入类别分页、`next_offset`、SHA-256 来源校验和书签精确查询/同名歧义报告；295 项测试通过（22 跳过） |
| P3-163 | Writer 书签内容检查 | done | `writer-structure --include-text` 有界读取唯一受支持书签；区分空值、歧义、范围不支持、无效范围，CLI/MCP 一致；297 项测试通过（22 跳过） |
| P3-164 | Writer 结构 WPS 对照 | done | 新受控 DOCX 在本机 WPS 只读打开；4 段、标题级别、书签文本一致，样式为 ID 与本地化显示名差异；文件哈希不变，298 项测试通过（22 跳过） |
| P3-165 | Writer 结构自动对照报告 | done | 新增显式 `--run-wps` 的 CLI/MCP，逐项比较正文/标题/样式分组/书签/文件哈希，真实 6/6 通过并保存 JSON；304 项测试通过（22 跳过） |
| P3-166 | Writer 对照证据交接覆盖 | done | 本地包收录最新 Writer 对照 JSON；inspection 验证字节相同，readiness 区分缺失/失败/过期并实测 passed；305 项测试通过（22 跳过） |
| P3-167 | Writer 嵌套范围结构验证 | done | 独立夹具验证正文/表格/页眉/页脚书签；离线范围分类与 WPS 只读名称/文本观测相符，哈希不变；307 项默认测试通过（23 跳过），WPS 定向 2/2 通过 |
| P3-168 | Writer 嵌套书签文本读取 | done | 表格、页眉页脚同段唯一书签可有界只读；跨段、文本框、歧义范围拒绝；真实 WPS 3/3、全量 311 项通过（23 跳过），旧结构对照 6/6；写入边界未扩大 |
| P3-169 | Writer 嵌套书签对照工件 | done | `writer-structure-parity --scope nested --run-wps` 留存独立 JSON；真实 WPS 3/3 对照通过，包内字节、来源和脚本哈希纳入就绪检查；314 项全量测试通过（23 跳过） |
| P3-170 | Writer 嵌套书签边界强化 | done | 排除修订文本与文本框段落，修复不可达端点假偏移；超链接/制表符表格夹具本机 WPS 一致且哈希不变；319 项全量测试通过（24 跳过），结构 6/6、嵌套 3/3 对照重跑通过 |
| P3-171 | Writer 对照解析器来源校验 | done | 两份报告记录解析器、文本检查及对照逻辑的 4 文件 SHA-256；代码内容变化即判过期；真实 WPS 结构 7/7、嵌套 4/4 通过，320 项全量测试通过（24 跳过） |
| P3-172 | 注册文档身份生命周期审计 | done | 注册保存 SHA-256 与文件标识；同路径替换/外部编辑/旧记录在共同备份预检被拒绝，复制期间变更被发现；成功操作刷新基线；326 项全量测试通过（25 跳过），8 项真实 WPS 定向测试通过 |
| P3-173 | Writer 书签填充标记兼容性 | done | 失败根因是 WPS 保存末尾表格时新增空段落；仅允许该规范化并核对全部原正文与表格文本，两种标记布局真实 WPS 4/4 通过，备份与重放通过；328 项全量测试通过（26 跳过） |
| P3-174 | 备份后修改源文件稳定性 | done | 备份身份/字节证据贯通 Writer、Spreadsheet、Presentation COM 前后核验；受控原子替换在 COM 前/后均检测，8 项 Writer/Spreadsheet 与 1 项 Presentation 真实 WPS 测试通过；334 项全量测试通过（27 跳过） |
| P3-175 | 跨进程修改协调审计 | done | 工作区内按文档 ID 的跨进程文件锁覆盖修改、恢复、读回、身份刷新与重新注册；争用返回 `DOCUMENT_BUSY`，进程退出自动释放；336 项全量测试通过（27 跳过），Writer/Spreadsheet 注册加锁后 WPS 2/2 通过 |
| P3-176 | 共享状态原子持久化 | done | 文档与操作注册表分别使用有界跨进程状态锁和同目录原子替换；4 进程共 48 份不同文档/操作不丢更新，读取无半写，跨文档相同请求 ID 冲突；替换失败保留旧 JSON；339 项全量测试通过（27 跳过），真实 WPS 定向 2/2 通过 |
| P3-177 | 操作提交与文档身份一致性审计 | done | 操作记录保存提交时文件身份；刷新失败后可在原文件身份吻合时修复重放，外部变更则拒绝；身份采集失败留下不可验证记录阻止重做；Windows 锁初始化与原子替换读取竞争已修复，342 项全量测试通过（27 跳过），WPS 定向 2/2 通过 |
| P3-178 | 已保存未记账修改的恢复审计 | done | 主操作不存在但派生备份已落盘时检查源文件身份；未变允许安全重试，已变返回 `UNRECORDED_MUTATION_AMBIGUOUS` 且阻止自动重做；命令级与故障注入测试通过，344 项全量测试通过（27 跳过），真实 WPS 定向 2/2 通过 |
| P3-179 | 歧义修改请求检查 | done | 新增只读 `mutation-request-inspect` / `wps_agent_mutation_request_inspect`，汇总主操作、派生备份与当前文件身份；区分已记录、可修复、可重试、歧义与无证据；CLI/MCP 一致且 JSON 状态不变，stdio MCP 81-tool 冒烟通过 |
| P3-180 | 歧义修改恢复指引 | done | 检查结果按 8 种状态返回非破坏性恢复建议，歧义/文件变化/身份不可验证不建议自动覆盖或重放；validation-runbook 增加只读请求证据检查；345 项全量测试通过（27 跳过） |
| P3-181 | 歧义修改恢复演练 | done | 真实 WPS Writer/Spreadsheet 在一次性文件上保存后故意不写主记录；CLI/MCP 均报歧义，同请求重试被拦截且文件身份不变；当前/备份/哈希清单各两组留存在 `artifacts/recovery-drill/p3-181-final`，全量 347 项测试通过（29 跳过），WPS 演练 2/2 通过 |
| P3-182 | 恢复演练工件核验 | done | 只读核验两组件清单、固定路径、64 MiB 文件上限、当前/备份不同且 SHA-256 匹配；缺失、篡改、非对象清单及工作区外路径均报失败，未提供工件则明确标注 absent；真实 local-handoff-summary 报 passed；351 项全量测试通过（29 跳过） |
| P3-183 | 恢复演练便携包交接 | done | 打包前校验演练证据，拒绝已变/缺失工件且不覆盖旧包；有效时纳入两组件共六文件，并在打包后与 sync-package-readiness 中逐项核验包内 SHA-256；真实本地包 6/6 匹配、就绪 passed，353 项全量测试通过（29 跳过） |
| P3-184 | 便携恢复证据解包核验 | done | 本地包解至工作区内全新目录，使用解包后 `src` 独立核验两组清单与文件 SHA-256 均 passed；跨根目录自动测试通过，354 项全量测试通过（29 跳过） |
| P3-185 | Writer 表格书签填充可行性 | done | 一次性 DOCX 的单元格唯一同段书签经现有 WPS COM 填充后，书签值、邻接前后缀、旁边单元格、正文及备份身份均通过；公开写入范围保持正文-only，355 项全量测试通过（30 跳过），真实 WPS 1/1 通过 |
| P3-186 | Writer 有界表格书签填充 | done | 仅扩展唯一同段直属表格单元格书签；全段文本与表格行/列数读回、强制备份、COM 前后身份、CLI/MCP 重放及真实 WPS 临时文件通过；356 项测试通过（30 跳过） |
| P3-187 | Writer 表格书签拓扑与格式审计 | done | 语义拓扑读回覆盖网格、横/纵合并、单元格段落和嵌套表数；真实 WPS 横/纵合并、多段、样式夹具及邻接文本/格式通过；358 项默认测试通过（31 跳过） |
| P3-188 | Writer 表格书签超链接与域审计 | done | 真实 WPS 将关系型超链接/简单域转为复杂域后，两次填充均保留规范化目标、指令及显示文本；覆盖语义节点的目标在备份前拒绝，篡改锚点、关系 URL 或域指令的离线读回失败；362 项默认测试通过（32 跳过） |
| P3-189 | Writer 表格语义前置校验加固 | done | 缺失链接关系、空域、孤立分隔符、未闭合域和嵌套复杂域均在备份/WPS 前拒绝；关系 URL、锚点和域指令读回篡改检测通过；363 项默认测试通过（32 跳过） |
| P3-190 | Writer 表格书签绘图保留审计 | done | 新增 drawing 子树语义读回，比较内嵌/锚定类型、尺寸、定位、变换、图片目标和字节哈希；目标覆盖图片时备份前拒绝；真实 WPS 内嵌图片通过；366 项默认测试通过（33 跳过） |
| P3-191 | Writer 表格书签浮动与多图片审计 | done | 真实 WPS 保留 anchor 的相对定位/方形环绕、裁剪和图片哈希；双 inline 图片关系、裁剪和绘图子树保持；367 项默认测试（34 跳过）及五项 WPS 集成通过 |
| P3-192 | Writer 表格书签浮动层级审计 | done | 两个 anchor 使用不同 relativeHeight 与水平位置，真实 WPS 保存后层级排名、裁剪、位置、关系目标和图片哈希保持；全量 367 项测试通过（34 跳过） |
| P3-193 | Writer 表格书签浮动布局渲染审计 | done | WPS 保存前后 PDF 页图像中的红/蓝锚定图片掩码逐像素一致；DrawingML 宽度推算的重叠采样显示较高层红图；368 项默认测试（35 跳过）、6 项 WPS 集成通过 |
| P3-194 | Writer 表格书签锚点参照布局审计 | done | 栏/段落与页面/页面参照锚点经真实 WPS 写入后 PDF 掩码逐像素一致；页面坐标受 layoutInCell 限制并裁切到单元格边界；字符参照锚点实测会随字形宽度漂移，已增加备份前拒绝；预检单测通过 |
| P3-195 | Writer 浮动图片环绕与边缘裁切审计 | done | 真实 WPS 对单元格外坐标钳制到单元格边界；关闭 layoutInCell 后页面负坐标栅格裁切为 144x108；none、square、topAndBottom 环绕及裁切图片掩码/语义读回一致，邻近 After 字符框坐标不变 |
| P3-196 | Writer 浮动图片分页与多段文字流审计 | done | 多页真实 WPS 表格书签夹具前后页数和 PREFACE/AFTER-TABLE 标记页码及字符框相同；每页 PDF 栅格逐像素一致，绘图语义读回一致 |
| P3-197 | Writer 多锚点跨页层级与分页审计 | done | 红色第一页锚点与蓝色后续页表格锚点各自在预期页可见；relativeHeight 排名、前后标记页码/字符框、整页栅格及颜色掩码经真实 WPS 书签填充前后保持一致 |
| P3-198 | Writer Tight/Through 环绕语义与布局审计 | done | 按规范构造菱形 wrapPolygon；真实 WPS 保存后 tight/through 环绕节点及多边形、页图像与提取文本保持一致，书签填充读回通过 |
| P3-199 | Writer 环绕方向与浮动边距审计 | done | left/right/largest 与三组不对称 distT/B/L/R 经真实 WPS 保存后DrawingML 距离、长绕排文本及整页栅格一致；图片快照现明确记录四向距离 |
| P3-200 | Writer 环绕几何输入前置校验 | done | tight/through 缺 polygon、顶点不足、坐标越界、负距离四类无效输入均在备份/WPS 前拒绝；DOCX 字节保持一致；12 项 WPS 集成仍通过 |
| P3-201 | Writer 凹多边形环绕与自交审计 | done | 凹 L 形 tight/through 多边形经真实 WPS 保存后路径、文本和页栅格一致；自交及零面积多边形在备份前拒绝且文件字节不变；13 项 WPS 集成通过 |
| P3-202 | Writer 环绕多边形方向与闭合审计 | done | 顺/逆时针、显式/隐式闭合共 8 种 tight/through 输入均通过 WPS 书签填充；每种输入自身的 DrawingML、文本和 PDF 栅格前后保持一致。显式重复首点与隐式闭合的初始渲染并不等价，已记录此差异 |
| P3-203 | Writer 环绕多边形顶点归一化审计 | done | 凹轮廓的 4 个循环起点在 tight/through 下均逐文件通过 WPS 往返；原始 DrawingML 顶点序列与自身 PDF 栅格保存前后不变。不同起点之间的 PDF 栅格实测不同，禁止把顶点序列循环规范化为相同语义 |
| P3-204 | Writer 环绕多边形共线顶点与渲染审计 | done | 凹多边形直边插入共线中点后 tight/through 栅格均发生变化；两个输入各自的 DrawingML、文本及 WPS 保存前后栅格稳定。禁止简化共线顶点 |
| P3-205 | Writer 环绕多边形最小几何与边界审计 | done | 相邻点间距 1 单位及落在 1/21599 的边界邻域坐标，在 tight/through 下均通过离线预检；真实 WPS 4 个往返组合的 DrawingML、文本和 PDF 栅格一致 |
| P3-206 | Writer 环绕多边形近共线顶点审计 | done | 中点偏移 120/21600 的近共线顶点与严格共线输入在当前 1.5× PDF 栅格中像素一致；tight/through 两种输入各自经 WPS 往返后顶点序列和自身栅格稳定。该像素结论不外推到更高分辨率，读回应保留精确顶点 |
| P3-207 | Writer 环绕多边形高分辨率栅格审计 | done | 在 4× PDF 栅格下比较严格共线、120/21600 与 600/21600 两种偏移，tight/through 页面像素均相同；每个输入的精确 DrawingML 与 WPS 往返栅格稳定。仅说明当前 fixture/WPS/render 路径，不主张不同几何语义等价 |
| P3-208 | Writer 环绕多边形坐标词法校验审计 | done | `+10800`、带空白/前导零的整数快照规范为同一数值；真实 WPS 两种词法输入往返通过。小数和空坐标在备份/COM 前拒绝，目标 DOCX 字节不变 |
| P3-209 | Writer 环绕坐标边界与超大整数审计 | done | 真实 WPS tight/through 夹具覆盖合法坐标端点 0/21600；200 位坐标整数在备份/WPS 前拒绝，文件字节不变 |
| P3-210 | Writer 环绕坐标 ASCII 词法审计 | done | 坐标预检与快照共用 ASCII XML 整数解析器；正号/前导零/XML 空白归一，Unicode 数字、小数、空串和 200 位超界值在备份/WPS 前拒绝且文件字节不变 |
| P3-211 | Writer 环绕坐标 XML 空白边界审计 | done | tab/换行经 XML 属性空白折叠后与同一整数快照一致；NBSP 不属于 XML 空白折叠字符，在备份/WPS 前拒绝且文件字节不变 |
| P3-212 | Writer 环绕坐标带符号零审计 | done | `-0`/`+00` 与数值 0 快照一致；4 种正号/前导零/空白/带符号零词法在真实 WPS 书签填充后语义、文本和 PDF 栅格稳定 |
| P3-213 | Writer 环绕坐标异常符号组合审计 | done | `++21600`、单独 `+`、`21 600` 均因非法整数词法在备份/WPS 前拒绝，目标 DOCX 字节保持不变 |
| P3-214 | Writer 环绕坐标负值与负零边界审计 | done | `-1` 坐标在备份/WPS 前拒绝；`-0` 与 0 快照等价并经真实 WPS 往返，0/21600 端点已有 tight/through 覆盖 |
| P3-215 | Writer 环绕距离词法与数值审计 | done | 距离预检/快照共用 ASCII XML 整数解析；正号、前导零及 XML 空白规范为数值字符串且真实 WPS 往返通过；Unicode 数字、小数、空值及负值备份前拒绝 |
| P3-216 | Writer 环绕距离整数范围审计 | done | 距离限制为 Word signed-32 且 635 EMU/twip 对齐；2147483640 经真实 WPS 往返成功，非对齐值及 signed-32/UInt32 溢出和 200 位整数均备份前拒绝 |
| P3-217 | Writer 环绕距离缺省值归一审计 | done | 快照按 WPS 实测默认值分别归一：distT/B=0、distL/R=114300 EMU；五种 wrap 类型均完成省略/显式零真实 WPS 往返，语义与逐文档文本/PDF 栅格稳定 |
| P3-218 | Writer 单侧环绕与缺省距离组合审计 | done | left/right/largest 三种 wrapText 在省略四向距离下均经真实 WPS 书签填充，默认距离、DrawingML 快照、PDF 文本和 1.5× 栅格往返稳定 |
| P3-219 | Writer 混合显式/缺省环绕距离审计 | done | 三组方向组合通过真实 WPS；省略方向分别采用 distT/B=0、distL/R=114300 EMU，显式 635/1270 EMU 保持不变，语义、文本和 PDF 栅格稳定 |
| P3-220 | Writer wrapText 缺省值审计 | done | square 环绕省略 wrapText 与显式 bothSides 快照等价；真实 WPS 书签填充后结构、PDF 文本和栅格稳定 |
| P3-221 | Writer 多边形环绕 wrapText 缺省审计 | done | tight/through 省略 wrapText 与显式 bothSides 快照等价；两种模式真实 WPS 书签填充后 DrawingML、PDF 文本和栅格稳定 |
| P3-222 | Writer 上下环绕 wrapText 缺省 WPS 审计 | done | top_and_bottom 省略 wrapText 与显式 bothSides 快照等价；真实 WPS 书签填充后结构、PDF 文本和栅格稳定 |
| P3-223 | Writer 上下环绕单侧 wrapText 审计 | done | 真实 WPS 将 top_and_bottom 的 left/right/largest 均改写为 bothSides；三种组合现于快照预检阶段拒绝，验证备份/COM 未调用且 DOCX 字节不变 |
| P3-224 | Writer wrapNone 附带 wrapText 属性审计 | done | WPS 保留 wrapNone 上 left/right/largest 属性；三种组合的 DrawingML、PDF 文本和栅格稳定，无需额外限制 |
| P3-225 | Writer wrapNone 非法 wrapText 枚举审计 | done | wrapNone 的非法 wrapText 枚举在快照预检拒绝，目标 DOCX 字节不变且未创建备份/调用 COM |
| P3-226 | Writer 各环绕类型 wrapText 枚举边界审计 | done | wrapNone/square/tight/through/top_and_bottom 的非法 wrapText 均在快照预检拒绝，文件字节不变且备份/COM 未调用 |
| P3-227 | Writer wrapText 大小写与空白边界审计 | done | `Left`、前后空白和空属性均按严格枚举校验于备份前拒绝，原文件字节不变 |
| P3-228 | Writer 多边形环绕单侧 wrapText WPS 审计 | done | tight/through × left/right/largest 六种组合均经真实 WPS 保留结构，书签填充后 PDF 文本及栅格稳定 |
| P3-229 | Writer wrapNone 单侧属性视觉影响审计 | done | WPS 导出的 left/right/largest 三份 PDF 文本及所有页面像素完全一致，当前夹具中该属性无视觉影响 |
| P3-230 | Writer wrapNone 结构属性保真审计 | done | left/right/largest 均在快照中原样保留且互不等价；与 P3-229 的像素等价分开记录 |
| P3-231 | Writer wrapNone 缺省与显式 bothSides 审计 | done | 缺省与显式 bothSides 快照不同，但 WPS 导出 PDF 文本和页面像素完全一致 |
| P3-232 | Writer 环绕默认属性组合审计 | done | 五种 wrap 类型同时省略 wrapText 和四向距离，真实 WPS 书签填充后快照、文本与 PDF 栅格稳定 |
| P3-233 | Writer 显式单向距离与缺省 wrapText 组合审计 | done | 五种 wrap 类型在省略 wrapText 时均保留显式 distT=635 EMU，其余三向按 WPS 默认值归一，WPS 读回与 PDF 稳定 |
| P3-234 | Writer 其他显式距离方向与缺省 wrapText 审计 | done | distB/L/R 的真实 WPS 往返均保留显式 635 EMU，其他省略方向按侧默认值归一，文本与栅格稳定 |
| P3-235 | Writer 环绕默认边界组合回归 | done | 30 格矩阵覆盖五种 wrap × 省略/合法方向/非法枚举，确认默认快照归一和 top_and_bottom 不支持值预检 |
| P3-236 | Writer 多图环绕缺省属性归一审计 | done | 同一 DOCX 的 square+tight 两个 anchor 同时省略 wrapText/距离，逐图快照按各自默认归一且 WPS 读回稳定 |
| P3-237 | Writer 多 anchor 混合显式距离审计 | done | square/tight 两个 drawing 分别保留 distT=635 与 distL=1270，其他距离独立按默认值归一，WPS 读回稳定 |
| P3-238 | Writer 多 anchor 混合 wrapText 审计 | done | square:left 与 tight:largest 在同一 DOCX 中逐图保留，WPS 书签填充后快照和 PDF 稳定 |
| P3-239 | Writer 多 anchor 单项不支持属性预检审计 | done | 第二个 anchor 含不支持 top_and_bottom:left 时整份多图文档于备份/COM 前拒绝，源字节不变 |
| P3-240 | Writer 多 anchor 预检错误定位审计 | done | 预检错误详情指出 drawing_index=1 与 unsupported_top_and_bottom_wrap_text，精确指向第二个 anchor |
| P3-241 | Writer 环绕预检诊断序列化审计 | done | CLI 与 MCP adapter 均完整保留第二个 anchor 的 drawing_index 和不支持原因详情 |
| P3-242 | Writer drawing 预检诊断索引一致性审计 | done | 前置 inline drawing 与 anchor 混排时，第三个 drawing 的诊断索引为 2，与快照顺序一致 |
| P3-243 | Writer 多个无效 drawing 诊断完整性审计 | done | 两个不支持 anchor 都出现在错误详情中，索引 0/1 与 wrapText 不支持原因分别对应 |
| P3-244 | Writer 多错误诊断 CLI/MCP 传递审计 | done | 前置 inline drawing 后的两个 anchor 错误列表经 CLI/MCP 完整保留，索引为 1/2 且顺序不变 |
| P3-245 | Writer 绘图诊断错误码契约审计 | done | BOOKMARK_SCOPE_UNSUPPORTED、drawing_index/reason 详情及 CLI/MCP failed 状态一致，备份/COM 前拒绝且源字节不变；409 项通过/65 项跳过，本地门禁 5/5 |
| P3-246 | Writer 未解析绘图诊断索引一致性 | done | 所有 14 类 unresolved 生成路径统一携带零基 drawing_index；非法 wrapText 的详情经 CLI/MCP 原样传递、源字节不变；410 项通过/65 项跳过，WPS parity 7/7 与 4/4，本地门禁 5/5 |
| P3-247 | Writer 绘图诊断 schema 覆盖矩阵 | done | 覆盖 13 类 unresolved reason，逐项验证 drawing_index 与 reason/attribute/relationship_id 字段；411 项通过/65 项跳过 |
| P3-248 | Writer 绘图关系诊断上下文审计 | done | 缺失图片关系的 rId、包内相对 target、drawing_index 经预检/CLI/MCP 一致保留；未泄露工作区路径或包内容，源字节不变；412 项通过/65 项跳过 |
| P3-249 | Writer 外部图片关系边界审计 | done | External image link 仅输出内部 target/mode/hash 元数据、无网络访问，源 DOCX 不变；413 项通过/65 项跳过 |
| P3-250 | Writer 外部图片 target 边界审计 | done | 覆盖缺失、畸形、64 KiB 外链及内部 ../ target；无网络、外链不读媒体 entry、无包外路径读取；414 项通过/65 项跳过 |
| P3-251 | Writer 图片关系 TargetMode 审计 | done | omitted/Internal 读取包内媒体，External 不读媒体，未知值生成 indexed invalid_relationship_target_mode 且不读媒体；415 项通过/65 项跳过，WPS parity 7/7 与 4/4 |
| P3-252 | Writer 图片关系 target 解析审计 | done | 相对/根相对 target 正常解析，缺失项带稳定索引；归一化后越出包根的 target 返回 target_outside_package，即使恶意 ZIP entry 存在也不读取；416 项通过/65 项跳过，WPS parity 7/7 与 4/4 |
| P3-253 | Writer 绘图关系诊断序列化审计 | done | 未知 TargetMode 与 package-root 越界错误经 direct preflight/CLI/MCP 保持 code、reason、index、details 一致；backup/COM 未调用且源字节不变；417 项通过/65 项跳过 |
| P3-254 | Writer 多关系错误聚合审计 | done | 未知 TargetMode 与越界 target 两条错误按 index 0/1 顺序经 direct/CLI/MCP 完整传递，backup/COM 未调用；418 项通过/65 项跳过 |
| P3-255 | Writer 绘图关系错误详情边界审计 | done | 超长 relationship ID/target/mode 均截至 256 字符并标记截断，重复解析结果稳定；短值和合法关系保持原样；419 项通过/65 项跳过 |
| P3-256 | Writer 有界关系诊断序列化审计 | done | 超长 ID/target/mode 的截断值及标志经 direct preflight、CLI、MCP 完整一致，backup/COM 未调用且源字节不变；420 项通过/65 项跳过 |
| P3-257 | Writer 多图诊断有界性审计 | done | 双图一项超长/一项短错误的截断标志与索引绑定正确，details 顺序经 direct/CLI/MCP 保持；421 项通过/65 项跳过 |
| P3-258 | Writer 诊断总 payload 上限审计 | done | 150 条超长关系异常稳定压缩为 127 条明细加 1 条 omitted_count 摘要，总数 128、JSON <120 KB、索引顺序稳定；422 项通过/65 项跳过，WPS parity 7/7 与 4/4 |
| P3-259 | Writer 诊断截断摘要传递审计 | done | 150 错误生成的 128 条 details 与 omission summary 经 direct/CLI/MCP 完整保留，CLI/MCP validation=failed，backup/COM 未触发；423 项通过/65 项跳过 |
| P3-260 | Writer 诊断条数边界审计 | done | 127/128 条完整保留；129 条保留 127 明细并以 omitted_count=2 摘要占第 128 项，无 off-by-one；424 项通过/65 项跳过 |
| P3-261 | Writer 序列化诊断字节上限审计 | done | 每个关系字段限制为 UTF-8 96 字节（含截断标记）；150 个含引号/反斜线的最大 JSON 转义输入经 CLI/MCP JSON 均不超过 120,000 字节，保留 127 条明细、omitted_count=23 和 failed 状态；Unicode 码点边界测试通过；全量 426 项通过/65 项跳过 |
| P3-262 | MCP tools/list 游标分页 | done | 81 个工具按目录顺序稳定遍历为 2 页（50+31），无重无漏；无效/过期游标返回 JSON-RPC -32602；每页保留 cache 元数据；smoke/config-audit 遍历全页且无重复；MCP 定向测试 19 项通过，全量 428 项通过/65 项跳过；project-status 通过 |
| P3-263 | 桌面 MCP 客户端联调审计 | done | 只读检查 Claude Desktop 进程存在；Claude Code 2.1.293 的 `claude mcp list` 显示未配置 server，Claude Desktop 配置文件未发现；电脑 UI 检查接口两次初始化失败；未修改配置/文档；真实客户端 initialize/tools/list/tools/call 门槛明确保持未验证 |
| P3-264 | MCP 分页性能基线 | done | Python 3.12.14 / Windows 10，200 次完整遍历均为 81 工具、50+31 两页，目录顺序精确且无重复；整轮 p50 5.078ms/p95 6.726ms，逐页 wire JSON 65,054/41,965 UTF-8 字节；报告 `docs/P3_MCP_PAGINATION_PERFORMANCE_BASELINE_20261009.md`；不设跨机器门槛 |
| P3-265 | 刷新 MCP 性能基线目录守卫 | done | `mcp-smoke` 与 `mcp-config-audit` 性能场景均由 47 提升至 81 工具最小值；4 项 performance 定向测试通过；safe regression 15/15、sync-package-coverage/readiness 通过；实际 performance-baseline 6/6、未启动 WPS |
| P3-266 | MCP stdio 分页端到端契约 | done | 真实子进程 stdio 验证 initialize、50+31 全量目录顺序和 cache 元数据；无效游标通过 wire 返回 -32602 且服务继续；只读 wps_agent_tasks 成功；请求 ID 对齐、EOF 后退出码 0；完整测试 430 项通过/65 项跳过 |
| P3-267 | 限制 MCP tools/list 游标长度 | done | 长度超过 128 字符的游标在 base64 解码前返回 -32602；测试确认 oversized 输入未触发 decoder；有效全页遍历和现有错误路径保留；全量 431 项通过/65 项跳过 |
| P3-268 | 文档化 MCP tools/list 游标分页 | done | 客户端配置与工具 schema 文档现说明总目录 81、单页最多 50、nextCursor 不透明且必须原样迭代至缺省；澄清 --once-json 一次一页、smoke/config-audit 聚合全页；文档新鲜度通过 |
| P3-269 | MCP 配置审计分页失败路径测试 | done | 隔离 fake server 验证跨页重复工具使审计失败并保留 count=2/pages=2/duplicate=1；重复 nextCursor 在第 2 页后失败并给出错误，不会请求第 3 页；配置审计测试 4 项通过；全量 433/65 |
| P3-270 | 加固 MCP smoke 畸形响应处理 | done | initialize/tools/list/tools/call 的 null 或非对象 result 安全降级为结构化失败；畸形列表页摘要不抛异常；null-result 回归测试通过，MCP server/smoke 定向 20 项通过，全量 434/65 |
| P3-271 | 刷新 MCP 分页加固后的本地同步包 | done | Safe regression 15/15 的 artifact `regression-run-20261008T173106394967Z-p3-271-passing-safe.json` 已包含；本地包 315 项、无失败，coverage/readiness 通过；project-status、workspace-health、documentation-freshness 均通过；package SHA256 `0E049F7E478AAE76D77755D87CE4FC0D2F54E02361A364D5853006E9D51DCCBC` |
| P3-272 | MCP 目录审计拒绝空白工具名 | done | `mcp-smoke` 与 `mcp-config-audit` 均拒绝空名称与纯空白名称，即使目录数量达标也失败；两组定向审计覆盖通过；全量 436/65 |
| P3-273 | 校验 MCP 工具命名建议 | done | 共用校验器限制 1-128 ASCII 字符集合 `[A-Za-z0-9_.-]`，非法名与重复名独立计数；空格、斜杠、非 ASCII、超长和有效长度边界定向测试通过；全量 438/65 |
| P3-274 | 验证 MCP stdio 畸形请求后恢复 | done | 真实 mcp-server 子进程依次接收畸形 JSON 与数组/标量 JSON，返回 `-32700`/`-32600` 且 null ID；同进程随后成功 initialize 并在 EOF 正常退出；定向 29 项通过，全量 439/65 |
| P3-275 | 加固 MCP JSON-RPC 请求信封校验 | done | 按 MCP 基础协议校验 `jsonrpc`、method、string/integer 非 null ID 和 object params；notification 不响应；无 ID 的 tools/call 不执行；handler/真实 stdio 均覆盖，MCP 定向 33 项通过，全量 443/65 |
| P3-276 | 校验 MCP initialize 版本协商 | done | Legacy stdio 明确支持 `2025-11-25`；initialize 校验 protocolVersion/capabilities/clientInfo，未知版本协商回退至支持版本，缺失/畸形参数返回 `-32602` 并保留 ID；MCP 定向 35 项通过，全量 445/65 |
| P3-277 | 强制 MCP initialize 生命周期顺序 | done | 持久 stdio 在 initialize 和 initialized notification 前拒绝常规请求，拒绝重复 initialize，合法顺序可继续；one-shot 明确为诊断入口；MCP 定向 36 项通过，全量 446/65 |
| P3-278 | 拒绝 MCP stdio JSON 重复对象键 | done | 专用 JSON parser 在任意对象深度拒绝重复 member；handler 和真实 stdio 验证 null-ID `-32600`、不触发 HTML 输出副作用，后续 tools/list 成功；MCP 定向 38 项通过，全量 448/65 |
| P3-279 | 限制 MCP stdio 输入行长度 | done | 单行最多 1,048,576 字符；TextIO 使用限量 `readline` 并以 8,192 字符块 drain 超长记录；精确边界和超限后恢复测试通过，MCP 定向 40 项通过，全量 450/65 |
| P3-280 | 拒绝 MCP 非标准 JSON 数值常量 | done | 专用 parser 在顶层及嵌套值拒绝 NaN/Infinity/-Infinity，返回 null-ID `-32700`；真实 stdio 随后 tools/list 成功；MCP 定向 42 项通过，全量 452/65 |
| P3-281 | 强制 MCP stdio 会话请求 ID 唯一 | done | 持久会话记录所有合法 string/integer ID（含方法校验失败请求）；重用 ID 在 dispatch 前返回 `-32600`，重复 HTML 转换无副作用，后续唯一 ID 可继续；MCP 定向 43 项通过，全量 453/65 |
| P3-282 | 对齐 MCP 输出 schema 与结构化结果 | done | 全部 81 个工具的 output contract 描述实际 `{mcp_call, errors}` 结构化 envelope；成功与工具执行错误的字段/JSON 类型测试通过；MCP 相关 54 项通过，全量 455/65 |
| P3-283 | 对未知 MCP 工具返回协议错误 | done | 未知工具名在 adapter 前返回 JSON-RPC `-32602`，adapter 不调用；已知工具的执行失败仍为 `isError` tool result；handler/子进程覆盖通过，MCP/server/schema/adapter 定向 64 项通过，全量 457/65 |
| P3-284 | 按 inputSchema 校验 MCP 工具参数 | done | adapter 与 MCP boundary 按 81 个 catalog schema 校验 JSON 类型、required/unknown、enum、数值范围和数组元素；无效参数在 adapter 前返回 `-32602`；MCP/schema/adapter 定向 67 项通过，全量 460/65 |
| P3-285 | 配置 MCP 客户端审计使用持久 stdio | done | 单个服务进程内完成 initialize、initialized、全部分页 tools/list；核对 ID、deadline、EOF exit 和 stderr，不再借助 one-shot 跳过生命周期；MCP 配置审计定向 8 项通过，全量 462/65 |
| P3-286 | 实现 MCP ping utility request | done | legacy 协议 ping 对无 params/空 params 返回空 result，非空 params 返回 `-32602`；覆盖 handler 和初始化后持久 stdio；MCP server/config audit 定向 43 项通过，全量 464/65 |
| P3-287 | 校验配置审计返回的工具描述与 schema | done | persistent tools/list 分页审计校验每个 descriptor 的工具名、input/output object schema 及可选字段形状；跨页畸形数据返回最多 20 条字段级诊断；配置审计定向 10 项通过，全量 466/65 |
| P3-288 | 限制配置 MCP 审计输出缓冲 | done | stdout 单行上限 1 MiB、响应队列容量 8，stderr 分 8,192 字符块持续 drain 且仅保留 8,192 字符；超限错误有界并回收子进程；审计定向 12 项通过，全量 468/65 |
| P3-289 | 规范化异常 MCP 审计响应 | done | 畸形 JSON、深层 JSON、无效 UTF-8 均返回有界审计失败；UTF-8 在 reader thread 内转换为诊断，子进程均被回收，随后独立正常审计通过；定向审计 13 项通过，全量 469/65 |
| P3-290 | 校验 MCP descriptor 的嵌套 schema | done | 递归检查 properties、patternProperties、$defs/definitions、items/prefixItems、组合 schema、required/dependentRequired、类型/数值/字符串/布尔关键字；每页最多 20 条 page/index/schema-path 诊断；审计定向 14 项通过，全量 470/65 |
| P3-291 | 校验配置审计的 MCP initialize 元数据 | done | initialize 要求非空 serverInfo.name/version，检查 capabilities/tools 元数据及 listChanged 布尔类型；5 类坏握手有界失败，后续有效审计继续通过；配置审计定向 15 项通过，全量 471/65 |
| P3-292 | 要求 initialize 声明 tools capability | done | tools/list 前必须确认 capabilities.tools 存在且为 object；缺失能力在 handshake 阶段有界失败；合法服务审计通过；定向 15 项、全量 471/65 |
| P3-293 | 校验可选 MCP implementation 元数据 | done | title/description/websiteUrl/icons 均为可选；存在时校验类型、HTTP(S)/data icon URI、mimeType/sizes/theme，不联网；有效完整元数据和 7 类畸形值覆盖通过；定向 16 项，全量 472/65 |
| P3-294 | 校验配置 MCP 进程参数类型 | done | spawn 前要求 command 非空字符串、args 为字符串列表、env 为字符串到字符串映射；5 类畸形配置均通过 mock 证明不会启动命令；审计定向 17 项通过，全量 473/65 |
| P3-295 | 拒绝 MCP 进程配置中的无效字符 | done | spawn 前拒绝 command/args/env NUL、空/含 `=` 的环境变量名；配置验证不回显环境值、args 仅报告数量；secret marker 不出现在序列化结果；审计定向 17 项，全量 473/65 |
| P3-296 | 确认有界 MCP 配置错误不泄露进程设置 | done | env 值/完整 args 不回显，command/cwd 摘要最多 256 字符；secret marker 不在结果中，所有错误路径均不 spawn；审计定向 18 项，全量 474/65 |
| P3-297 | 限制 MCP 客户端配置文件读取 | done | JSON parse 前最多读取 1 MiB + 1 字节；超限不 spawn，边界恰好 1 MiB 的有效 UTF-8 JSON 配置通过；审计定向 20 项，全量 476/65 |
| P3-298 | 校验 MCP 配置 JSON 结构 | done | 顶层必须为 object，mcpServers 必须为 object；6 种畸形结构均有界失败且不 spawn；审计定向 21 项，全量 477/65 |
| P3-299 | 拒绝 MCP 配置 JSON 歧义值 | done | 递归拒绝重复成员名和 NaN/Infinity 等非标准数值常量；6 种原始 JSON 输入均有界失败、不泄露原文且不 spawn；审计定向 22 项，全量 478/65 |
| P3-300 | 限制 MCP 配置 JSON 嵌套深度 | done | 在递归解码前限制 64 层容器；65 层被拒且 json.loads/Popen 均未调用，恰好 64 层通过；字符串内括号和转义不误判；定向 23 项，全量 479/65 |
| P3-301 | 拒绝 MCP 配置中的孤立 Unicode surrogate | done | 检查嵌套值和对象键；孤立高/低 surrogate 有界失败、不泄露值且不 spawn，合法代理对与 BMP Unicode 通过；定向 24 项，全量 480/65 |
| P3-302 | 限制配置 MCP 审计子进程超时 | done | CLI、MCP schema、直接 API 共用 1–120 秒边界，默认 15 秒；非法值在配置读取和 spawn 前拒绝；保留子进程超时回收测试；全量 482/65 |
| P3-303 | 限制配置 MCP 审计预期工具数 | done | CLI、MCP schema、直接 API 共用 1–10,000 边界；非法值在配置读取/spawn 前拒绝，默认值不变；全量 483/65 |
| P3-304 | 限制配置 MCP server 名称 | done | CLI、MCP schema、API 共用非空及 256 字符边界；非法值在配置读取/spawn 前拒绝且不回显；adapter 同时落实 minLength/maxLength/pattern；全量 484/65 |
| P3-305 | 对齐 MCP adapter 字符串 schema 校验 | done | adapter 执行 minLength/maxLength/pattern；空白/边界/超长值行为通过测试，三类畸形 pattern 均有界失败且不泄露参数；全量 486/65 |
| P3-306 | 拒绝畸形 MCP schema 约束元数据 | next | 在比较前校验 adapter 消费的约束元数据类型与关系；结构化失败、不抛异常、不泄露参数 |

进展记录：
- 2026-10-09: P3-298 已完成 MCP 配置根节点与 `mcpServers` 对象形状校验；6 种畸形结构均有界失败且不启动子进程，全量测试 477 passed/65 skipped，safe regression 15/15；实现和下一项范围见 `docs\P3_NEXT_MCP_CONFIG_JSON_AMBIGUITY_SCOPE.md`。
- 2026-10-09: P3-299 已拒绝 MCP 配置中的递归重复成员与 NaN/Infinity 非标准常量；6 种原始 JSON 变体均不 spawn、诊断不泄露配置内容；当前 next 为 P3-300 嵌套深度限制。
- P3-299 release: 全量 478 passed/65 skipped，local-release-gates 5/5，safe regression passed；package readiness passed，未启动 WPS。
- 2026-10-09: P3-300 已在 json.loads 前限制 JSON 容器深度为 64 层；65 层输入在解析及 spawn 前失败，64 层边界与字符串转义测试通过；全量 479 passed/65 skipped。当前 next 为 P3-301。
- P3-300 release: local-release-gates 5/5 passed，package readiness passed，WPS 未启动。
- 2026-10-09: P3-301 已拒绝配置 JSON 字符串和对象键中的孤立 UTF-16 surrogate；有效代理对与非 ASCII Unicode 保持可用，定向 24 项、全量 480/65。当前 next 为 P3-302 子进程超时上限。
- P3-301 release: local-release-gates 5/5 passed，package readiness passed，WPS 未启动。
- 2026-10-09: P3-302 已统一配置审计超时范围为 1–120 秒、默认 15 秒，CLI/MCP schema/API 均覆盖边界并在 spawn 前拒绝非法输入；全量测试 482 passed/65 skipped，当前 next 为 P3-303。
- P3-302 release: local-release-gates 5/5 passed，package readiness passed，WPS 未启动。
- 2026-10-09: P3-303 已统一 `expected_min_tools` 为 1–10,000，非法值在读取配置前失败；全量 483 passed/65 skipped，当前 next 为 P3-304 server 名称边界。
- P3-303 release: local-release-gates 5/5 passed，package readiness passed，WPS 未启动。
- 2026-10-09: P3-304 已统一 server 名称非空/最多 256 字符约束，schema 的 pattern/长度约束由 adapter 实际执行；空白和超长值不读取配置、不 spawn、不回显；全量 484 passed/65 skipped。当前 next 为 P3-305。
- 2026-10-09: P3-305 已补齐 adapter 的 minLength/maxLength/pattern 验证；catalog 关键字扫描通过，空/空白/精确上限/超限及无效 pattern 用例通过；全量 486 passed/65 skipped。当前 next 为 P3-306。
- P3-305 release: local-release-gates 5/5 passed，package readiness passed，WPS 未启动。
- P3-304 release: local-release-gates 5/5 passed，package readiness passed，WPS 未启动。
- 2026-10-03: P3-004 已为 `regression-run` 增加 `--artifact-dir`，safe profile 生成 `artifacts\regression\regression-run-20261003T063513662051Z-regression-artifact-p3-004-001.json`，报告见 `docs\P3_REGRESSION_ARTIFACT_EXPORT_REPORT.md`。
- 2026-10-03: P3-005 已形成 CI 交接文档，覆盖 safe/WPS 调用命令、artifact 留存路径、通过门槛和失败分诊，见 `docs\REGRESSION_CI_HANDOFF.md`。
- 2026-10-03: P3-006 已执行失败恢复演练，构造 `p3_006_failed_writer_replace` 终态失败任务，验证 `task-recovery`、备份清单和 Writer snapshot 证据，报告见 `docs\P3_RECOVERY_HARDENING_DRILL.md`。
- 2026-10-03: P3-007 已新增 `security-audit`，审计 6 个修改类 MCP/CLI 工具的 request_id、task_id、dry-run、备份和 WPS/文件系统边界，报告见 `docs\P3_SECURITY_BOUNDARY_AUDIT.md`。
- 2026-10-03: P3-008 已新增 `performance-baseline`，采集 6 个不启动 WPS 的核心命令基线，总耗时约 2176ms、总输出约 245KB，报告见 `docs\P3_PERFORMANCE_BASELINE.md`。
- 2026-10-03: P3-009 已刷新 MCP desktop/config 集成证据，`mcp-config-audit` 与 `mcp-smoke --tool-name wps_agent_security_audit` 均通过 38-tool 工具面；同时修复 smoke harness 对无参工具的参数假设，报告见 `docs\P3_DESKTOP_MCP_INTEGRATION_REFRESH.md`。
- 2026-10-03: P3-010 已选择 Writer 表格单元格更新作为下一个高级能力，并定义 fixture、dry-run、backup、validation、MCP 和 WPS smoke 要求，见 `docs\P3_ADVANCED_WPS_CAPABILITY_SCOPE.md`。
- 2026-10-03: P3-011 已实现 `writer-table-write` 与 `wps_agent_writer_table_write`，真实 WPS 写入 `FINAL_STATUS` 通过备份、COM 写入、读回验证和幂等重放；报告见 `docs\P3_WRITER_TABLE_WRITE_REPORT.md`。
- 2026-10-03: P3-012 已新增 `writer-table-smoke` 与 `wps_agent_writer_table_smoke`，并将 Writer 表格更新纳入 WPS regression profile；safe profile 仍不启动 WPS，完整 WPS profile 结构化记录了既有 `spreadsheet-calc-smoke` timeout，报告见 `docs\P3_WRITER_TABLE_REGRESSION_INTEGRATION_REPORT.md`。
- 2026-10-03: P3-013 已定位 `spreadsheet-calc-smoke` timeout 与固定输出文件覆盖/提示等待有关；已增加结构化 COM timeout、`--timeout-seconds`、同路径保护、保存前关闭 alerts 并删除既有输出，完整 WPS profile 4/4 通过，报告见 `docs\P3_SPREADSHEET_CALC_TIMEOUT_HARDENING_REPORT.md`。
- 2026-10-03: P3-014 已新增只读 `wps-process-audit` / `wps_agent_wps_process_audit`，采集当前 WPS 相关进程并给出不自动 kill 用户进程的安全清理建议；报告见 `docs\P3_WPS_PROCESS_LIFECYCLE_AUDIT_REPORT.md`。
- 2026-10-03: P3-015 已刷新 Phase 3 release readiness；后续 P3-022 已将当前证据推进到 96 个单元测试、safe regression 6/6、WPS regression 4/4、44-tool MCP 工具面；报告见 `docs\PHASE3_RELEASE_READINESS_REFRESH.md`。
- 2026-10-03: P3-016 已完成同步就绪交接；P3-023 已将其刷新为本地打包交接，远程目标仅保留为可选未来路径，报告见 `docs\CLOUD_SYNC_READINESS_HANDOFF.md`。
- 2026-10-03: P3-017 已生成本地 cloud-sync zip 包 `artifacts\cloud-sync\wps-ai-agent-cli-phase3-sync-20261003.zip`，SHA256 为 `8F679FC6C5F64D22F5F0DDF12B2420750AE7783FF02A702DFE7FE215ABA4B18F`；用户随后确认不需要远程上传/推送，见 `docs\P3_REMOTE_CLOUD_TARGET_SELECTION_REPORT.md`。
- 2026-10-03: P3-017 已产品化同步打包命令 `cloud-sync-package`，可复现生成 `artifacts\cloud-sync\wps-ai-agent-cli-phase3-sync-cli.zip`，117 个条目，SHA256 为 `476690E1450A894F3E6CA9C96EAC628C0AC56C1CF0DC6A8B549993EFB5D01B2C`。
- 2026-10-03: 用户确认不必远程 Git，仅在当前工作区继续工作；P3-017 已按本地工作区模式收口，远程上传不再作为阻塞项。
- 2026-10-03: P3-018 已完成本地工作区连续性审计，盘点 artifacts 25 个约 2.6MB、fixtures 21 个约 1.1MB、`.wps-agent` 备份 20 个约 435KB，并列出保留项与需授权清理候选，见 `docs\P3_LOCAL_WORKSPACE_CONTINUITY_AUDIT.md`。
- 2026-10-03: P3-019 已新增只读 `cleanup-plan` / `wps_agent_cleanup_plan`，输出保守清理策略、受保护路径、最新证据和需授权候选；未执行任何删除，见 `docs\P3_LOCAL_CLEANUP_POLICY.md`。
- 2026-10-03: P3-020 已新增 `scripts\local_repro_bundle.ps1`，可本地连续运行单元测试、`cleanup-plan`、safe regression 和 `cloud-sync-package`，不使用远程 Git 或云端服务；说明见 `docs\P3_LOCAL_REPRODUCIBILITY_BUNDLE.md`。
- 2026-10-03: P3-021 已形成清理审批检查点，当前 27 组候选、约 1.81MB；未获得明确授权，因此未删除任何文件，见 `docs\P3_CLEANUP_APPROVAL_CHECKPOINT.md`。
- 2026-10-03: P3-022 已新增只读 `project-status` / `wps_agent_project_status`，汇总本地 next 任务、当前 MCP 工具面、cleanup 姿态、最新 artifact 与同步包 hash，见 `docs\P3_LOCAL_PROJECT_STATUS_SUMMARY.md`。
- 2026-10-03: P3-023 已刷新 README、MCP 文档、cloud handoff 和 release readiness 中的旧工具数、旧 next 任务和远程同步假设，见 `docs\P3_DOCUMENTATION_FRESHNESS_SWEEP.md`。
- 2026-10-03: P3-024 已在文档扫尾后刷新本地同步包，`artifacts\cloud-sync\wps-ai-agent-cli-phase3-sync-cli.zip` 验证时为 127 个条目且无失败文件；当前 hash 可通过 `project-status` 查看，见 `docs\P3_LOCAL_PACKAGE_REFRESH.md`。
- 2026-10-03: P3-025 已执行授权闸门检查；未获得明确类别或路径授权，因此未删除任何文件，见 `docs\P3_APPROVED_CLEANUP_EXECUTION_GATE.md`。
- 2026-10-03: P3-026 已新增只读 `cleanup-approval-manifest` / `wps_agent_cleanup_approval_manifest`，按清理类别导出候选路径和审批短语，见 `docs\P3_CLEANUP_APPROVAL_MANIFEST_EXPORT.md`。
- 2026-10-04: P3-027 已新增只读 `workspace-health` / `wps_agent_workspace_health`，组合 next 任务、回归证据、同步包状态、清理授权姿态和本地-only 状态，见 `docs\P3_LOCAL_WORKSPACE_HEALTH_SUMMARY.md`。
- 2026-10-04: P3-028 已在 workspace-health 新增后刷新本地同步包，验证时 135 个条目且无失败文件，见 `docs\P3_POST_HEALTH_LOCAL_PACKAGE_REFRESH.md`。
- 2026-10-04: P3-029 已汇总 Phase 3 本地-only 状态、health、清理闸门、回归证据和同步包证据，见 `docs\P3_LOCAL_ONLY_STATUS_CONSOLIDATION.md`。
- 2026-10-04: P3-030 已选择下一项非破坏性能力为 MCP tool catalog snapshot，并定义范围、验证和安全约束，见 `docs\P3_NEXT_ADVANCED_CAPABILITY_SCOPE.md`。
- 2026-10-04: P3-031 已新增只读 `mcp-catalog-snapshot` / `wps_agent_mcp_catalog_snapshot`，汇总 47 个 MCP 工具、分类、WPS 要求、修改类工具和 safety-note 覆盖情况，见 `docs\P3_MCP_CATALOG_SNAPSHOT.md`。
- 2026-10-04: P3-032 已在 MCP 工具目录快照后刷新本地同步包，验证时 141 个条目且无失败文件，见 `docs\P3_POST_CATALOG_LOCAL_PACKAGE_REFRESH.md`。
- 2026-10-04: P3-033 已刷新 README、MCP client 配置、MCP schema 草案、回归 manifest 和 release readiness 中的当前 47-tool 工具面与 `mcp-catalog-snapshot` 说明，见 `docs\P3_CATALOG_SNAPSHOT_DOCUMENTATION_REFRESH.md`。
- 2026-10-04: P3-034 已在工具目录文档刷新后重新生成本地同步包，并用 project-status、workspace-health 和 MCP catalog snapshot 验证 47-tool、本地-only、无清理删除状态，见 `docs\P3_POST_CATALOG_DOCUMENTATION_PACKAGE_REFRESH.md`。
- 2026-10-04: P3-035 已定义 MCP catalog drift guard 范围：只读、基于显式 baseline、比较工具数/分类/WPS 要求/修改类工具/safety-note 覆盖，并作为 safe regression gate，见 `docs\P3_MCP_CATALOG_DRIFT_GUARD_SCOPE.md`。
- 2026-10-04: P3-036 已新增只读 `mcp-catalog-drift` / `wps_agent_mcp_catalog_drift` 和 `config\mcp_catalog_guard.json` baseline；safe regression 新增 catalog drift 场景，当前 48-tool baseline 无漂移，见 `docs\P3_MCP_CATALOG_DRIFT_GUARD_IMPLEMENTATION.md`。
- 2026-10-04: P3-037 已在 MCP catalog drift guard 后刷新本地同步包，验证时 148 个条目且无失败文件，并确认 project-status、workspace-health 和 drift guard 均通过，见 `docs\P3_POST_DRIFT_GUARD_LOCAL_PACKAGE_REFRESH.md`。
- 2026-10-04: P3-038 已选择下一项非破坏性能力为 regression evidence summary，用于只读汇总 safe/WPS 最新回归 artifact 和通过状态，见 `docs\P3_NEXT_NONDESTRUCTIVE_CAPABILITY_SCOPE.md`。
- 2026-10-04: P3-039 已新增只读 `regression-evidence` / `wps_agent_regression_evidence`，汇总最新 safe/WPS 回归 artifact，通过状态、场景数和结果 ID，见 `docs\P3_REGRESSION_EVIDENCE_SUMMARY.md`。
- 2026-10-04: P3-040 已在 regression-evidence 后刷新本地同步包，验证时 153 个条目且无失败文件，并确认 project-status、workspace-health、regression-evidence 和 catalog drift 均通过，见 `docs\P3_POST_REGRESSION_EVIDENCE_LOCAL_PACKAGE_REFRESH.md`。
- 2026-10-04: P3-041 已选择下一项非破坏性能力为 local handoff summary，用于一次性只读汇总本地交接状态，见 `docs\P3_NEXT_LOCAL_HANDOFF_SUMMARY_SCOPE.md`。
- 2026-10-04: P3-042 已新增只读 `local-handoff-summary` / `wps_agent_local_handoff_summary`，组合 project status、workspace health、regression evidence、catalog drift 和 sync package 证据，见 `docs\P3_LOCAL_HANDOFF_SUMMARY.md`。
- 2026-10-04: P3-043 已在 local-handoff-summary 后刷新本地同步包，验证时 158 个条目且无失败文件，并确认 local handoff、project-status、workspace-health 和 catalog drift 均通过，见 `docs\P3_POST_LOCAL_HANDOFF_LOCAL_PACKAGE_REFRESH.md`。
- 2026-10-04: P3-044 已选择下一项非破坏性能力为 artifact retention summary，用于只读汇总保留证据、清理候选、审批姿态和同步包状态，见 `docs\P3_NEXT_ARTIFACT_RETENTION_SUMMARY_SCOPE.md`。
- 2026-10-04: P3-045 已新增只读 `artifact-retention-summary` / `wps_agent_artifact_retention_summary`，汇总保留证据、清理候选、审批姿态和同步包状态；未删除文件，见 `docs\P3_ARTIFACT_RETENTION_SUMMARY.md`。
- 2026-10-04: P3-046 已在 artifact-retention-summary 后进入本地包刷新，当前 next 为 P3-047；最终包证据见 `docs\P3_POST_ARTIFACT_RETENTION_LOCAL_PACKAGE_REFRESH.md`。
- 2026-10-04: P3-047 已选择下一项非破坏性能力为 validation runbook，用于只读输出本地验证、打包、可选 WPS 和清理复核步骤，见 `docs\P3_NEXT_VALIDATION_RUNBOOK_SCOPE.md`。
- 2026-10-04: P3-048 已新增只读 `validation-runbook` / `wps_agent_validation_runbook`，输出本地验证步骤但不执行命令，见 `docs\P3_VALIDATION_RUNBOOK.md`。
- 2026-10-04: P3-049 已在 validation-runbook 后进入本地包刷新，当前 next 为 P3-050；最终包证据见 `docs\P3_POST_VALIDATION_RUNBOOK_LOCAL_PACKAGE_REFRESH.md`。
- 2026-10-04: P3-050 已选择下一项非破坏性能力为 documentation freshness guard，用于只读扫描当前文档和配置的新鲜度，见 `docs\P3_NEXT_DOCUMENTATION_FRESHNESS_SCOPE.md`。
- 2026-10-04: P3-051 已新增只读 `documentation-freshness` / `wps_agent_documentation_freshness`，检查当前文档和配置中的旧工具数、旧 expected-min-tools 或旧 next 任务引用，见 `docs\P3_DOCUMENTATION_FRESHNESS_GUARD.md`。
- 2026-10-04: P3-052 已在 documentation-freshness 后进入本地包刷新，当前 next 为 P3-053；最终包证据见 `docs\P3_POST_DOCUMENTATION_FRESHNESS_LOCAL_PACKAGE_REFRESH.md`。
- 2026-10-04: P3-053 已选择下一项非破坏性能力为 regression history summary，用于只读汇总最近 safe/WPS 回归 artifact 和通过趋势，见 `docs\P3_NEXT_REGRESSION_HISTORY_SCOPE.md`。
- 2026-10-04: P3-054 已新增只读 `regression-history` / `wps_agent_regression_history`，读取现有回归 artifact 并汇总最新状态和近期通过趋势，见 `docs\P3_REGRESSION_HISTORY_SUMMARY.md`。
- 2026-10-04: P3-055 已在 regression-history 后进入本地包刷新，当前 next 为 P3-056；最终包证据见 `docs\P3_POST_REGRESSION_HISTORY_LOCAL_PACKAGE_REFRESH.md`。
- 2026-10-04: P3-056 已选择下一项非破坏性能力为 sync package inspection，用于只读检查本地同步包内容、hash 和打包时最新回归 artifact 收录情况，见 `docs\P3_NEXT_SYNC_PACKAGE_INSPECT_SCOPE.md`。
- 2026-10-04: P3-057 已新增只读 `sync-package-inspect` / `wps_agent_sync_package_inspect`，检查已有同步包而不重新打包、删除文件、启动 WPS 或使用远程 Git，见 `docs\P3_SYNC_PACKAGE_INSPECT.md`。
- 2026-10-04: P3-058 已在 sync-package-inspect 后进入本地包刷新，当前 next 为 P3-059；最终包证据见 `docs\P3_POST_SYNC_PACKAGE_INSPECT_LOCAL_PACKAGE_REFRESH.md`。
- 2026-10-04: P3-059 已选择下一项非破坏性能力为 sync package content summary，用于只读展开同步包内容分布和 artifact 条目，见 `docs\P3_NEXT_SYNC_PACKAGE_SUMMARY_SCOPE.md`。
- 2026-10-04: P3-060 已新增只读 `sync-package-summary` / `wps_agent_sync_package_summary`，按顶层目录、artifact 条目和最大条目汇总已有同步包内容，见 `docs\P3_SYNC_PACKAGE_SUMMARY.md`。
- 2026-10-04: P3-061 已在 sync-package-summary 后进入本地包刷新，当前 next 为 P3-062；最终包证据见 `docs\P3_POST_SYNC_PACKAGE_SUMMARY_LOCAL_PACKAGE_REFRESH.md`。
- 2026-10-04: P3-062 已选择下一项非破坏性能力为 sync package manifest，用于只读列出同步包条目并支持 prefix 过滤，见 `docs\P3_NEXT_SYNC_PACKAGE_MANIFEST_SCOPE.md`。
- 2026-10-04: P3-063 已新增只读 `sync-package-manifest` / `wps_agent_sync_package_manifest`，按路径列出已有同步包条目、大小和顶层目录，见 `docs\P3_SYNC_PACKAGE_MANIFEST.md`。
- 2026-10-04: P3-064 已在 sync-package-manifest 后进入本地包刷新，当前 next 为 P3-065；最终包证据见 `docs\P3_POST_SYNC_PACKAGE_MANIFEST_LOCAL_PACKAGE_REFRESH.md`。
- 2026-10-07: P3-065 已选择下一项非破坏性能力为 sync package coverage，用于只读比较包内条目和工作区同步根目录覆盖情况，见 `docs\P3_NEXT_SYNC_PACKAGE_COVERAGE_SCOPE.md`。
- 2026-10-07: P3-066 已新增只读 `sync-package-coverage` / `wps_agent_sync_package_coverage`，按包创建时间作为截止点报告缺失条目、额外条目和包后新增文件，见 `docs\P3_SYNC_PACKAGE_COVERAGE.md`。
- 2026-10-07: P3-067 已在 sync-package-coverage 后刷新本地同步包，当前 next 为 P3-068；最终验证与打包步骤见 `docs\P3_POST_SYNC_PACKAGE_COVERAGE_LOCAL_PACKAGE_REFRESH.md`。
- 2026-10-07: P3-068 已选择下一项非破坏性能力为 sync package readiness，用于汇总同步包 inspect、summary 与 coverage 的本地交接状态，见 `docs\P3_NEXT_SYNC_PACKAGE_READINESS_SCOPE.md`。
- 2026-10-07: P3-069 已新增只读 `sync-package-readiness` / `wps_agent_sync_package_readiness`，当前 next 为 P3-070；实现记录见 `docs\P3_SYNC_PACKAGE_READINESS.md`。
- 2026-10-07: P3-070 已在 sync-package-readiness 后刷新本地同步包，当前 next 为 P3-071；最终验证与打包步骤见 `docs\P3_POST_SYNC_PACKAGE_READINESS_LOCAL_PACKAGE_REFRESH.md`。

## 每轮开发节奏

1. 选取一个阶段任务。
2. 明确输入、输出、错误码和验证方法。
3. 先写最小测试，再实现命令或核心逻辑。
4. 在真实 WPS 环境中补充实测记录。
5. 更新任务状态和版本矩阵。

## 最新实测证据

- 2026-10-02: WPS Writer `kwps.Application` 已通过 PowerShell COM fallback 完成打开 PRD、保存副本、关闭。
- 2026-10-02: WPS Spreadsheets `ket.Application` 已通过 PowerShell COM fallback 完成打开测试工作簿、保存副本、关闭。
- 2026-10-02: WPS Presentation `kwpp.Application` 已通过 PowerShell COM fallback 完成打开测试演示、保存副本、关闭。
- 2026-10-02: WPS Spreadsheets 公式计算验证通过，`D4 = B4 + C4`，raw value `18.0`，display text `18`。
- 2026-10-02: WPS Writer DOCX 到 PDF 转换验证通过，使用 `ExportAsFixedFormat`，输出 5 页 PDF。
- 2026-10-02: Phase 0 可行性报告完成，建议 Phase 1 以核心 CLI 和验证闭环为范围 conditional go。
- 2026-10-02: Phase 1 已实现 `register-document`、`documents`、`backup-document`，并验证备份幂等重放。
- 2026-10-02: Phase 1 已实现 `writer-replace`，支持正文范围 dry-run、强制备份、WPS COM 替换、结果验证和 request_id 幂等重放。
- 2026-10-02: Phase 1 已实现 `validate-document`，Writer 正文文本和 Spreadsheet 单元格值验证均已通过真实文件验证。
- 2026-10-02: Phase 1 已实现 `operation` 与 `operations`，可查询 request_id 对应操作结果和历史操作列表。
- 2026-10-02: Phase 1 已实现 `scan-dir`，可扫描目录并标注支持文件的组件与注册状态。
- 2026-10-02: Phase 1 MVP 汇总报告完成，记录当前能力边界与下一优先级。
- 2026-10-02: Phase 1 已实现段落范围 Writer 替换，`--paragraph-index 1` 实测通过并支持幂等重放。
- 2026-10-03: Phase 1 已实现 Spreadsheet A1 范围读取与写入，`A8:B9` 真实 WPS COM 写入、读回校验、备份和幂等重放均已通过。
- 2026-10-03: Phase 1 已实现 Presentation 文本替换，真实 WPS COM 将标题替换为 `Phase 1 presentation replace verified`，备份、读回校验和幂等重放均已通过。
- 2026-10-03: Phase 1 已实现 Spreadsheet 公式写入与重算，真实 WPS COM 写入 `E4:E6` 公式并读回缓存值 `[77, 40, 117]`，备份和幂等重放均已通过。
- 2026-10-03: Phase 1 已实现 `snapshot-document`，真实 Writer、Spreadsheet、Presentation 文件均已输出结构快照；同时修复 Windows GBK 控制台无法输出特殊字符 JSON 的问题。
- 2026-10-03: Phase 1 已实现 `batch-report`，`fixtures/phase0` 实测返回 6 个支持文件、2 个已注册文件快照、4 个未注册跳过项，快照失败数为 0。
- 2026-10-03: Phase 1 已实现 `list-backups` 与 `restore-backup`，探针文件真实恢复验证通过；恢复前会自动创建 pre-restore 备份，并支持 request_id 幂等重放。
- 2026-10-03: Phase 1 release candidate 审计完成，`docs/PHASE1_RELEASE_CANDIDATE_REPORT.md` 已记录最终能力、证据、边界与 Phase 2 建议入口。
- 2026-10-03: Phase 2 已实现长任务状态模型，`task-status-create/update/task-status/task-statuses` 实测通过 pending → running → succeeded 生命周期、进度、终态和 result_ref。
- 2026-10-03: Phase 2 已将 `--task-id` 接入选定修改命令，真实 `spreadsheet-write` 实测同时完成 WPS 写入、operation 记录和 task status succeeded 终态。
- 2026-10-03: Phase 2 已实现 `task-recovery` 与 `task-recovery-playbooks`，覆盖 succeeded、failed、cancelled、pending、interrupted_or_running、ambiguous_missing_status 恢复场景；真实 `task_sheet_write_tracked_001` 与缺失任务探针均已输出结构化恢复手册。
- 2026-10-03: Phase 2 已实现 `mcp-tools` 与 `mcp-tool-schema`，当前 31 个 CLI 命令均映射为 MCP 工具契约草案，包含输入 schema、输出契约、WPS 依赖、修改属性和 CLI 示例；草案记录见 `docs/MCP_TOOL_SCHEMA_DRAFT.md`。
- 2026-10-03: Phase 2 已实现 `mcp-call` 本地 adapter，支持 schema 查找、JSON 参数校验、CLI argv 映射、底层 `CommandResponse` 捕获和递归保护；`wps_agent_tasks` 实测通过 adapter 调用现有 `tasks` response 层。
- 2026-10-03: Phase 2 已实现 `mcp-server` JSON-RPC/stdio 原型，支持 `initialize`、`tools/list` 和 `tools/call`；`tools/list` 当前返回 32 个工具，`tools/call` 已通过 server → adapter → CLI response 调用 `wps_agent_tasks`。
- 2026-10-03: Phase 2 已实现 `mcp-smoke` 可重复 smoke harness，覆盖 initialize、tools/list、tools/call，并新增 `config/mcp_client_config.example.json` 与 `docs/MCP_SERVER_CLIENT_CONFIG.md`；Phase 2 当时 `tools/list` 返回 38 个工具，P3-054 后当前工具面为 54 个工具。
- 2026-10-03: Phase 2 已实现 `mcp-config-audit`，通过 `config/mcp_client_config.example.json` 校验 config、cwd、Python command、PYTHONPATH、args 和 configured `tools/list` smoke；Phase 2 当时 `tools/list` 返回 38 个工具，P3-054 后当前工具面为 54 个工具。
- 2026-10-03: Phase 2 最终交付报告完成，详见 `docs/PHASE2_FINAL_HANDOFF_REPORT.md`。
- 2026-10-03: Phase 3 已启动，`docs/PHASE3_PRODUCTION_READINESS_PLAN.md` 记录生产就绪 workstreams、风险清单、验收门槛和首个回归 manifest 任务。
- 2026-10-03: Phase 3 已实现 `config/regression_manifest.json`、`regression-manifest` 与 `regression-run`，safe profile 覆盖 5 个 CLI/MCP/config smoke 场景并实测通过；WPS profile 已列入 manifest，默认不执行以避免意外启动桌面 WPS。
- 2026-10-03: Phase 3 已运行 WPS-required regression profile，`writer-com-smoke`、`spreadsheet-calc-smoke`、`writer-convert-smoke` 均 passed；输出文件位于 `fixtures/phase3`，报告见 `docs/P3_WPS_REGRESSION_SMOKE_REPORT.md`。
- 生成文件: `smoke_writer_copy.docx`、`fixtures/phase0/phase0_calculation_fixture_copy.xlsx`、`fixtures/phase0/phase0_presentation_fixture_copy.pptx`、`fixtures/phase0/phase0_calculation_verified.xlsx`
- 详细记录: `docs/PHASE0_FINDINGS.md`、`docs/CONVERSION_MATRIX.md`、`docs/PHASE0_FEASIBILITY_REPORT.md`
