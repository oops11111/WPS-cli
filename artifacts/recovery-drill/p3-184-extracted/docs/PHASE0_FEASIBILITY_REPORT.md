# Phase 0 可行性报告

## 结论

建议进入 Phase 1 MVP，但范围应限定为 WPS 三组件核心 CLI、稳定 JSON 协议、document_id 会话模型、备份、状态查询、幂等和验证钩子。

HTML 高保真三模式不应直接进入承诺范围。当前只完成 WPS COM 与 Writer 到 PDF 转换验证，HTML 视觉优先、可编辑优先和受控往返仍需要独立样例和指标。

## Go No Go

| 范围 | 结论 | 理由 |
| --- | --- | --- |
| WPS 三组件基础控制 | Go | Writer、Spreadsheets、Presentation 均已通过 COM open/save/close smoke |
| 表格公式计算验证 | Go | 已写入 `=B4+C4`，WPS 计算后 raw value `18.0` 与 display text `18` 一致 |
| Writer 到 PDF 转换 | Go | `ExportAsFixedFormat` 已输出 5 页 PDF，文件非空且首页渲染可读 |
| pywin32 作为唯一后端 | No Go | 当前运行环境缺少 `pywin32`，且 `ensurepip` 在该宿主中不可用 |
| PowerShell COM fallback | Go | 已稳定完成三组件 smoke、公式计算和 PDF 导出 |
| HTML 高保真转换 | Hold | 尚未建立 HTML 样例、视觉指标和降级行为 |

## 已验证事实

- 主机为 Windows 10。
- WPS COM ProgID 已注册：
  - Writer: `kwps.Application`
  - Spreadsheets: `ket.Application`
  - Presentation: `kwpp.Application`
- `pwsh -EncodedCommand` 在当前宿主中会空输出并返回 `4294967295`。
- 临时 `.ps1` 文件执行方式可稳定驱动 WPS COM。
- Presentation 的 `Visible` 属性设置会抛出 COM 异常；当前实现将其作为 best-effort，不阻断 open/save/close。

## 产出物

| 类型 | 路径 |
| --- | --- |
| Writer smoke 输出 | `smoke_writer_copy.docx` |
| Spreadsheet fixture | `fixtures/phase0/phase0_calculation_fixture.xlsx` |
| Spreadsheet smoke 输出 | `fixtures/phase0/phase0_calculation_fixture_copy.xlsx` |
| Spreadsheet calculation 输出 | `fixtures/phase0/phase0_calculation_verified.xlsx` |
| Presentation fixture | `fixtures/phase0/phase0_presentation_fixture_v2.pptx` |
| Presentation smoke 输出 | `fixtures/phase0/phase0_presentation_fixture_copy.pptx` |
| Writer PDF 输出 | `fixtures/phase0/phase0_writer_export.pdf` |
| PDF 首页渲染 | `fixtures/phase0/pdf_render/phase0_writer_export_page1.png` |

## Phase 1 建议范围

### 必做

- CLI 命令协议稳定化。
- document_id 会话模型。
- 修改前强制备份。
- 请求 ID 与幂等保护。
- 长任务状态查询。
- Writer、Spreadsheets、Presentation 基础打开、保存副本、关闭。
- Spreadsheets 公式写入、计算、raw value 与 display text 核对。
- Writer 到 PDF 的最小转换能力。
- 结构化日志、错误码和验证结果输出。

### 暂缓

- HTML 可编辑优先。
- HTML 受控往返。
- PDF 反向转换。
- 默认开放任意 Python、宏或脚本执行。
- 高级演示动画、数据透视、图表深度编辑。

## Phase 1 进入条件

- 保留 PowerShell COM fallback，不把 `pywin32` 作为唯一运行路径。
- 所有修改命令必须先实现备份接口。
- 所有命令必须输出 `ok`、`request_id`、`backend`、`summary`、`validation` 和 `errors`。
- 每个 WPS 后端能力必须保留实测记录，不能用接口存在代替能力可用。
- HTML 转换只能作为实验能力，直到建立独立基线。

## 风险

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| WPS COM 版本差异 | 命令在不同机器上失败 | 维护 ProgID 和版本矩阵，保留诊断命令 |
| pywin32 不可用 | Python 直接 COM 路径不可用 | 保留 PowerShell COM fallback |
| Presentation COM 属性差异 | 可见性、窗口行为不稳定 | 将 UI 属性设置设为 best-effort |
| 转换结果依赖本机字体和 WPS 导出 | PDF 或 HTML 保真度波动 | 转换矩阵记录前提、保留能力和已知损失 |
| Agent 误用修改命令 | 文件不可恢复 | Phase 1 先实现备份、dry-run 和幂等 |
