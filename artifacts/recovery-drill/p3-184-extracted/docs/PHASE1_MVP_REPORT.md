# Phase 1 MVP 汇总报告

## 当前结论

Phase 1 的 Agent 可调用基础已经成形。当前 CLI 已覆盖稳定 `document_id`、备份、备份清单与恢复、dry-run、幂等、Writer 写操作、Spreadsheet A1 范围读写与公式重算、Presentation 文本替换、验证钩子、验证快照、操作台账、目录扫描和批量报告。后续可以在这个安全底座上继续扩展更多 Writer、Spreadsheets 和 Presentation 操作。

## 已实现命令

| 命令 | 能力 | 验证状态 |
| --- | --- | --- |
| `inspect-env` | 检测 Windows、WPS ProgID、PowerShell COM fallback | passed |
| `plan` | 输出阶段路线图 | passed |
| `tasks` | 输出阶段任务状态 | passed |
| `register-document` | 注册文件并返回稳定 `document_id` | passed |
| `documents` | 列出已注册文档 | passed |
| `backup-document` | 按 `document_id` 创建备份，支持 dry-run 与幂等 | passed |
| `list-backups` | 列出全部或指定 `document_id` 的可恢复备份 | passed |
| `restore-backup` | 恢复指定备份，恢复前自动创建 pre-restore 保护备份，并支持幂等 | passed |
| `writer-replace` | Writer 正文或 1-based 段落范围文本替换，支持 dry-run、备份、验证与幂等 | passed |
| `validate-document` | Writer 正文文本验证与 Spreadsheet 单元格值验证 | passed |
| `snapshot-document` | 输出 Writer 段落结构、Spreadsheet 公式错误扫描、Presentation 文本对象计数 | passed |
| `operation` | 按 request_id 查询单个操作结果 | passed |
| `operations` | 列出历史操作 | passed |
| `scan-dir` | 扫描目录中的 WPS 支持文件并标注注册状态 | passed |
| `batch-report` | 合并目录扫描、注册状态和验证快照，输出逐文件批量报告 | passed |
| `spreadsheet-read` | 读取注册表格的 A1 范围并输出 JSON 矩阵 | passed |
| `spreadsheet-write` | 写入注册表格的 A1 范围，支持备份、COM 写入、读回验证与幂等 | passed |
| `spreadsheet-formula-write` | 写入公式矩阵，触发 WPS 重算，并用缓存值矩阵验证结果 | passed |
| `presentation-replace` | 替换演示文稿文本框或占位符文本，支持 dry-run、备份、读回验证与幂等 | passed |

## 已实测样例

| 场景 | 结果 |
| --- | --- |
| Writer open/save/close | passed |
| Spreadsheets open/save/close | passed |
| Presentation open/save/close | passed |
| Spreadsheet 公式写入与计算验证 | passed |
| Writer DOCX 到 PDF | passed |
| Writer 正文文本替换 | passed |
| Writer 段落范围文本替换 | passed |
| Writer 替换幂等重放 | passed |
| Writer 正文文本验证 | passed |
| Spreadsheet 单元格值验证 | passed |
| 目录扫描 | passed |
| 备份清单查询 | passed |
| 安全恢复与 pre-restore 保护备份 | passed |
| 恢复幂等重放 | passed |
| Spreadsheet A1 范围读取 | passed |
| Spreadsheet A1 范围写入与读回验证 | passed |
| Spreadsheet 写入幂等重放 | passed |
| Spreadsheet 公式写入与 WPS 重算 | passed |
| Spreadsheet 公式缓存值读回验证 | passed |
| Writer 段落结构快照 | passed |
| Spreadsheet 公式错误扫描快照 | passed |
| 批量报告合并目录扫描与快照 | passed |
| Presentation 文本 dry-run | passed |
| Presentation 文本替换与读回验证 | passed |
| Presentation 替换幂等重放 | passed |
| Presentation 文本对象计数快照 | passed |

## 当前边界

- `writer-replace` 当前覆盖正文范围和 1-based 段落范围，不覆盖页眉、页脚、批注、文本框和其他 OOXML 部件。
- Spreadsheet 当前覆盖 A1 范围读写、公式写入、WPS 重算、缓存值读取和整簿公式错误扫描；尚未实现循环引用诊断。
- Presentation 当前覆盖文本框和占位符的纯文本替换；尚未覆盖表格、图表、SmartArt、备注页和富文本局部格式保持。
- 格式验证当前仍是基础级，尚未覆盖版面差异、字体、段落样式和图形对象。
- HTML 高保真转换仍处于 hold 状态，不能作为 MVP 承诺能力。

## 下一优先级

1. 成熟会话与任务服务：长任务状态、进度、可中断执行和资源回收。
2. Presentation 表格、备注页和更细粒度文本对象处理。
3. Writer 标题范围与书签范围替换。
4. MCP 复用：将 CLI 核心逻辑包装为 MCP 工具描述与示例配置。

## Phase 1 风险

| 风险 | 缓解 |
| --- | --- |
| COM 行为依赖本机 WPS 版本 | 每条新能力保留 smoke 和实测记录 |
| 写操作范围与 dry-run 范围不一致 | 每个写命令显式声明 scope，并用相同 scope 验证 |
| request_id 误复用 | 操作台账暴露 `operation` 查询，调用方可确认重放结果 |
| 备份目录增长 | 后续增加备份列表、清理策略和恢复命令 |
| 格式验证不足 | 逐步引入渲染、结构快照和差异报告 |
