# PRD v1.2 落实：已打开文档、选区编辑与 HTML 导出

来源：`docs/WPS_AI_Agent_CLI_PRD_v1.2.docx`（v1.2，2026-10-03）。

v1.2 相对 v1.1 的增量是：附着运行中实例、操作活动文档与当前选区、明确「当前页面」边界、对已打开文档直接导出 HTML。本文记录这些要求在代码中的落点、行为约束、未验证项和未做项。

## 需求与实现对照

| PRD 条目 | 实现 | 状态 |
| --- | --- | --- |
| 4.2 附着运行中实例，获取活动文档列表 | `open-documents`（MCP：`wps_agent_open_documents`） | 已实现，离线与假 COM 测试通过，未在真实 WPS 验证 |
| 4.2 稳定 `document_id`，避免依赖活动窗口 | 列表按路径匹配已注册文档并返回 `document_id`；`--register` 注册已保存的打开文档；后续命令都只接受 `document_id`，按完整路径在运行实例中查找文档 | 已实现 |
| 4.2 操作当前选区 | `writer-selection-read`、`writer-selection-replace` | 已实现，仅 Writer |
| 4.3「当前页面」边界 | 读选区时返回 `paragraph_index` 和尽力而为的 `page_number`，并固定标记 `page_info_verified: false`；没有任何按页码写入的命令 | 已实现边界声明，页码行为待实测 |
| 4.4 已打开文档直接导出 HTML | `export-open-document`（MCP：`wps_agent_export_open_document`） | 已实现，仅 Writer，未在真实 WPS 验证 |
| 4.5 已打开文件的推荐流程 | 见下文「推荐调用流程」 | 已实现 |
| 4.2 修改前强制备份、干跑、请求 ID | `writer-selection-replace` 复用 `create_backup`、`guarded_com_mutation`、`replay_operation`、文档锁与可选 `--task-id` | 已实现 |

## 命令行为

### `open-documents`

- 只用 `GetActiveObject` 语义附着（直接绑定 `ole32`/`oleaut32`，因为 PowerShell 7 没有 `Marshal.GetActiveObject`），不会启动 WPS，也从不对附着到的实例调用 `Quit()`、`Save()` 或 `Close()`。
- 依次尝试每个组件的全部 ProgID（`kwps`、`wps`、`Kingsoft Writer` 等）。
- 返回每个文档的 `name`、`full_name`、`saved`、`read_only`、`active`、`path_exists`、`document_id`、`registered`。
- 没有找到任何运行实例时返回 `NO_RUNNING_WPS_INSTANCE`；实例存在但没有文档时返回成功和空列表。
- 未保存的新文档（只有名称、没有路径）没有稳定 ID，`document_id` 为 `null`。
- 多个组件（文字、表格、演示）都会列出；选区编辑和导出目前只支持 Writer。

### `writer-selection-read`

读取已注册 Writer 文档在运行实例中的选区：`start`、`end`、`collapsed`、`selection_text`（最多 4096 字符，超出时 `selection_text_truncated`）、`paragraph_index`（1 起，尽力计算）、`page_number`（尽力获取，未验证）。选区取自该文档自己的 `ActiveWindow`，不使用全局活动窗口。

### `writer-selection-replace`

流程：校验文本 -> 读取选区 -> 预检 -> dry-run 返回预览 -> 备份 -> 按范围（不是按 `Selection` 对象）写入 -> 保存 -> 读回校验 -> 记录幂等。

拒绝条件（均在备份之前，返回结构化错误）：

| 错误码 | 条件 |
| --- | --- |
| `DOCUMENT_HAS_UNSAVED_CHANGES` | 打开的文档有未保存修改。备份和写后文件校验基于磁盘上的已保存版本，所以必须先保存 |
| `SELECTION_EMPTY` | 选区折叠 |
| `SELECTION_TOO_LARGE` | 选区超过 4096 字符 |
| `SELECTION_SPANS_STRUCTURE` | 选区含段落标记、单元格标记等控制字符，或含域、图形等非文本对象；单行纯文本才允许替换，避免意外合并段落 |
| `SELECTION_MISMATCH` | 给出 `--expected-selection-text` 但与当前选区不一致；或预览与写入之间选区变化 |
| `INVALID_ARGUMENT` | 替换文本含换行、控制字符或超过 4096 字符 |

写入脚本会再次核对选区范围与文本（区分大小写），防止预览到写入之间用户移动了选区。写入后不会恢复用户选区（结果里 `selection_preserved: false`）。

### `export-open-document`

- 只支持 Writer，输出必须是新的 `.html` 或 `.htm` 路径；已存在则返回 `OUTPUT_EXISTS`，不覆盖。
- 要求文档已保存。在运行实例中以 `Documents.Add(源文件路径)` 建立一个副本，对副本 `SaveAs2(输出, 10)`（过滤后的 HTML；失败时退回 `SaveAs`），然后不保存地关闭副本。原文档不会被另存、改名或关闭，所以不会像对原文档直接 `SaveAs2` 那样被改指向 HTML。
- 导出后校验：输出文件存在且非空、源文件哈希未变、源文档仍在运行实例中打开。
- 结果总是带 `known_losses`，说明 HTML 导出有损、图片与样式在伴随目录中、保真度需实测。

## 推荐调用流程

1. `open-documents --register` 列出并注册已打开且已保存的文档，拿到 `document_id`。
2. `writer-selection-read --document-id ...` 查看用户当前选区。
3. `writer-selection-replace --dry-run --expected-selection-text "<上一步读到的文本>"` 预览。
4. 去掉 `--dry-run`，带固定的 `--request-id` 执行。
5. 需要 HTML 时 `export-open-document --document-id ... --output new.html`。
6. 检查结果中的 `validation_passed`、`backup`、`source_unchanged`。

定位优先用选区、段落、书签和关键词，不要依赖页码。

## 验证情况

- Linux 离线测试 `tests/test_open_documents.py`：对 COM 层打桩，覆盖附着失败、列表、选区读取、全部拒绝路径、备份、幂等重放、读回失败、超时、导出的输出校验与源文件哈希变化。
- `tests/test_open_documents_powershell.py`：设置 `pwsh` 后，把真实生成的 PowerShell 脚本放到一个用 C# 实现的假 COM 对象上执行，验证脚本逻辑：按路径查找文档、状态返回、范围替换、`-cne` 比较、未保存拒绝、导出副本。没有 `pwsh` 时跳过。生成的脚本也用 PowerShell 解析器检查过语法。
- 没有在真实 WPS 上验证。真实 WPS 上仍需确认（对应 PRD 6.3 的 Phase 0 假设）：
  - `kwps.Application` 等 ProgID 的 `GetActiveObject` 是否能附着到用户正在使用的实例；
  - `Document.ActiveWindow.Selection`、`Range.Paragraphs`、`Selection.Information(3)` 的行为和页码准确性；
  - `Documents.Add(<docx 路径>)` 是否复制内容而不是当作模板打开，以及对隐藏窗口、只读文档的表现；
  - 过滤 HTML（格式 10）在 WPS 中是否可用，以及导出损失；
  - 范围写入后 `Document.Save()` 对已打开文档的行为，以及保存后文件身份校验是否通过。

## 未做项

- 表格和演示的选区、活动对象操作与 HTML 导出（演示可以用 `SaveCopyAs`，表格需另行评估）。
- 精确「第 N 页」操作，PRD 明确要求实测后再决定，不作首版承诺。
- 对未保存修改的文档，不尝试保存或合并，直接拒绝。
- 在选区内保留富文本格式的替换（当前是纯文本范围替换，字符格式沿用 WPS 范围赋值的默认行为，未验证）。
