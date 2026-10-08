# Phase 0 实测记录

## 2026-10-02 环境与 COM 探测

### 结论

- 当前主机是 Windows 10。
- WPS 三组件 COM ProgID 已注册：
  - Writer: `kwps.Application`
  - Spreadsheets: `ket.Application`
  - Presentation: `kwpp.Application`
- 当前捆绑 Python 缺少 `pywin32`，但 PowerShell COM 可作为 Phase 0 等效验证后端。
- `pwsh -EncodedCommand` 在当前宿主中会空输出并返回 `4294967295`，不适合作为 smoke 后端。
- 临时 `.ps1` 文件执行方式可成功驱动 WPS Writer COM。

### 已验证能力

| 能力 | 组件 | 后端 | 结果 | 证据 |
| --- | --- | --- | --- | --- |
| ProgID 注册检测 | Writer | PowerShell COM probe | passed | `kwps.Application=True` |
| ProgID 注册检测 | Spreadsheets | PowerShell COM probe | passed | `ket.Application=True` |
| ProgID 注册检测 | Presentation | PowerShell COM probe | passed | `kwpp.Application=True` |
| 打开文档 | Writer | PowerShell COM | passed | 打开 PRD `.docx` 成功 |
| 保存副本 | Writer | PowerShell COM | passed | `smoke_writer_copy.docx` 已生成 |
| 关闭文档与退出应用 | Writer | PowerShell COM | passed | smoke 命令返回 `validation.status=passed` |
| 打开工作簿 | Spreadsheets | PowerShell COM | passed | 打开 `phase0_calculation_fixture.xlsx` 成功 |
| 保存工作簿副本 | Spreadsheets | PowerShell COM | passed | `phase0_calculation_fixture_copy.xlsx` 已生成 |
| 关闭工作簿与退出应用 | Spreadsheets | PowerShell COM | passed | smoke 命令返回 `validation.status=passed` |
| 打开演示文稿 | Presentation | PowerShell COM | passed | 打开 `phase0_presentation_fixture_v2.pptx` 成功 |
| 保存演示副本 | Presentation | PowerShell COM | passed | `phase0_presentation_fixture_copy.pptx` 已生成 |
| 关闭演示与退出应用 | Presentation | PowerShell COM | passed | smoke 命令返回 `validation.status=passed` |
| 写入公式并计算 | Spreadsheets | PowerShell COM | passed | `D4 = B4 + C4`，raw value `18.0`，display text `18` |
| DOCX 导出 PDF | Writer | PowerShell COM | passed | `ExportAsFixedFormat` 输出 5 页 PDF，242418 bytes |

### 当前限制

- Phase 0 可行性报告仍需形成 go/no-go 结论，属于 P0-008。
- `pywin32` 仍不可用；当前实现已支持 PowerShell COM fallback，后续可继续评估是否必须引入 `pywin32`。

## 下一步

1. 汇总 Phase 0 可行性报告。
2. 给出进入 Phase 1 的 go/no-go 结论。
3. 列出 Phase 1 前必须补齐的风险和测试资产。
