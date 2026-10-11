# PRD v1.2 落实：已打开文档、选区编辑与 HTML 导出

来源：`docs/WPS_AI_Agent_CLI_PRD_v1.2.docx`（v1.2，2026-10-03）。

v1.2 相对 v1.1 的增量是：附着运行中实例、操作活动文档与当前选区、明确「当前页面」边界、对已打开文档直接导出 HTML。本文记录这些要求在代码中的落点、行为约束、未验证项和未做项。

## 需求与实现对照

| PRD 条目 | 实现 | 状态 |
| --- | --- | --- |
| 4.2 附着运行中实例，获取活动文档列表 | `open-documents`（MCP：`wps_agent_open_documents`） | 已实现。2026-10-09 本机附着到已打开的 Writer 12.0，列出 `open.docx` 并注册出稳定 `document_id`，没有启动第二个实例，也没有退出 |
| 4.2 稳定 `document_id`，避免依赖活动窗口 | 列表按路径匹配已注册文档并返回 `document_id`；`--register` 注册已保存的打开文档；后续命令都只接受 `document_id`，按完整路径在运行实例中查找文档 | 已实现 |
| 4.2 操作当前选区 | `writer-selection-read`、`writer-selection-replace`、`writer-selection-insert`、`writer-selection-delete`；`presentation-selection-read`、`presentation-selection-replace`、`presentation-selection-insert`、`presentation-selection-delete`；`spreadsheet-selection-read`、`spreadsheet-selection-replace`、`spreadsheet-selection-delete` | Writer/Presentation/Spreadsheet 活动选区读写均已实现；Writer/Presentation 支持折叠光标插入与选区删除（P3-413/414/416），选区替换尽量保留统一字符格式（P3-445）。表格支持单区域或 `multi_area` 常量填充、`values_json` 矩阵写入（P3-417）、选区 `ClearContents`（P3-419；最多 100 格），形状 TextFrame（P3-442）、图表 ChartTitle（P3-443）、AxisTitle（P3-446）与 Series Values（P3-447，TAB 拼接、点数一致）写回；形状几何仍拒绝 |
| 4.3「当前页面」边界 | 读选区时返回 `paragraph_index` 和尽力而为的 `page_number`，并固定标记 `page_info_verified: false`；没有任何按页码写入的命令 | 已实现。单页样例上读到 `paragraph_index` 1、`page_number` 1，字段仍标记为未验证，不作为页码准确性结论 |
| 4.4 已打开文档直接导出 HTML | `export-open-document`（MCP：`wps_agent_export_open_document`） | Writer（`Documents.Add` + `SaveAs2`）、Presentation（`SaveCopyAs` 12/23）、Spreadsheet（P3-403：临时 `SaveCopyAs` + 副本 `SaveAs` 44/45）均已支持；均不改名不关闭源文件 |
| 4.4b 已打开文档直接导出 PDF | `export-open-document-pdf`（MCP：`wps_agent_export_open_document_pdf`） | Writer 副本 `ExportAsFixedFormat`/`SaveAs` 17；Presentation 优先 `ExportAsFixedFormat`（失败退临时 `SaveCopyAs` + `SaveAs` 32）；Spreadsheet 对已打开工作簿 `ExportAsFixedFormat`。不改名不关闭源文件 |
| 4.4c 已打开文档原生格式副本 | `export-open-document-copy`（MCP：`wps_agent_export_open_document_copy`） | 同扩展名 `SaveCopyAs`；Writer 失败时退 `Documents.Add` + `SaveAs`。不改名不关闭源文件；不对格式做转换 |
| 4.4d 已打开文档导出纯文本 | `export-open-document-text`（MCP：`wps_agent_export_open_document_text`） | Writer 副本 Unicode/ANSI 文本 `SaveAs`；Presentation 按幻灯片抽取形状文本写 UTF-8；Spreadsheet 临时 `SaveCopyAs` + 副本文本 `SaveAs`。不改名不关闭源文件 |
| 4.4e 已打开文档主动保存 | `save-open-document`（MCP：`wps_agent_save_open_document`）；`save-as-open-document`（MCP：`wps_agent_save_as_open_document`，P3-444） | 对已注册且有磁盘路径的打开文档显式 `Save()`；dirty 时先备份上次已保存文件；已保存则成功且不写；拒绝只读。无路径未命名文档用 `save-as-open-document`（按 component+Name `SaveAs` 到原生路径并注册）。其它命令仍拒绝未保存，不会隐式保存 |
| 4.5 已打开文件的推荐流程 | 见下文「推荐调用流程」 | 已实现 |
| 4.2 修改前强制备份、干跑、请求 ID | `writer-selection-replace` 复用 `create_backup`、`guarded_com_mutation`、`replay_operation`、文档锁与可选 `--task-id` | 已实现 |

## 命令行为

### `open-documents`

- 只用 `GetActiveObject` 语义附着（直接绑定 `ole32`/`oleaut32`，因为 PowerShell 7 没有 `Marshal.GetActiveObject`），不会启动 WPS，也从不对附着到的实例调用 `Quit()` 或 `Close()`。列表命令本身不 `Save()`；显式保存见 `save-open-document`。
- 依次尝试每个组件的全部 ProgID（`kwps`、`wps`、`Kingsoft Writer` 等）。
- 返回每个文档的 `name`、`full_name`、`saved`、`read_only`、`active`、`path_exists`、`document_id`、`registered`。
- 没有找到任何运行实例时返回 `NO_RUNNING_WPS_INSTANCE`；实例存在但没有文档时返回成功和空列表。
- 未保存的新文档（只有名称、没有路径）没有稳定 ID，`document_id` 为 `null`。
- 多个组件（文字、表格、演示）都会列出；选区读取支持 Writer、Presentation 与 Spreadsheet；选区写回支持 Writer、Presentation 文本选区与 Spreadsheet 单元格/区域/多区域常量或矩阵写入；HTML、PDF、纯文本与同格式原生副本导出支持 Writer、Presentation 与 Spreadsheet。

### `writer-selection-read`

读取已注册 Writer 文档在运行实例中的选区：`start`、`end`、`collapsed`、`selection_text`（最多 4096 字符，超出时 `selection_text_truncated`）、`paragraph_index`（1 起，尽力计算）、`page_number`（尽力获取，未验证）。选区取自该文档自己的 `ActiveWindow`，不使用全局活动窗口。

### `presentation-selection-read`

读取已注册 Presentation 在运行实例中的当前选区：`selection_kind`（none/slides/shapes/text/unknown）、`selection_text`（最多 4096 字符）、文本光标的 `text_range_start` / `text_range_length` / `collapsed`（`Length==0`）、尽力而为的 `slide_index` / `shape_name` / `shape_count`。优先使用该演示自己的 `Windows.Item(1)`，仅在同一路径时才回退到 `ActiveWindow`。`slide_info_verified` 固定为 false。不启动 WPS，也不 `Quit()`。

### `presentation-selection-replace`

流程与 Writer 选区写回对齐：校验文本 -> 读取选区 -> 预检 -> dry-run 预览 -> 备份 -> 按当前 `TextRange` 写入 -> 保存 -> 读回校验 -> 记录幂等。仅允许 `selection_kind=text`；幻灯片/形状整选拒绝为 `SELECTION_SPANS_STRUCTURE`。`saved=false`、只读、空选区、超大选区与 `expected_selection_text` 不匹配均在备份前拒绝（未保存提示改用 `save-open-document`，不隐式保存）。不启动 WPS，也不 `Quit()`；`selection_preserved` 固定为 false。

### `presentation-selection-insert`

在折叠文本光标（`selection_kind=text` 且 `text_range_length==0`）处插入单行文本。流程与 Writer 光标插入对齐：校验文本 -> 读取选区 -> 预检 -> dry-run -> 备份 -> 折叠 `TextRange.Text=` 插入 -> 保存 -> 读回 -> 幂等。可选 `--expected-start`（1-based `TextRange.Start`）。非折叠返回 `SELECTION_NOT_COLLAPSED`；非文本选区拒绝。不启动 WPS，也不 `Quit()`。

### `spreadsheet-selection-read`

读取已注册 Spreadsheet 在运行实例中的当前选区：`selection_kind`（none/cell/range/multi_area/non_range/unknown）、`address`、`sheet_name`、`cell_count`、`area_count`、`selection_text`（最多 4096 字符；多选区最多采样 100 格）、单格时尽力返回 `formula`；对 `non_range`（图表/形状等）尽力返回 `object_kind`/`object_name`/`has_text_frame`/`has_chart_title`（`object_info_verified` 固定为 false；形状读 TextFrame 文本，图表读 ChartTitle 文本）。优先使用该工作簿自己的 `Windows.Item(1)`，仅在同一路径时才回退到 `ActiveWindow`。不启动 WPS，也不 `Quit()`。完整单元格值请用 `address` 配合 `spreadsheet-read`。

### `spreadsheet-selection-replace`

流程与 Writer/Presentation 选区写回对齐：校验输入 -> 读取选区 -> 预检 -> dry-run 预览 -> 备份 -> 写入 -> 保存 -> 读回校验 -> 记录幂等。允许：
- `selection_kind` 为 `cell`/`range`/`multi_area` 且 `cell_count` 在 1–100；或
- `selection_kind=non_range` 且 `object_kind=shape` 且 `has_text_frame=true`（`fill_mode=shape_text`）；或
- `selection_kind=non_range` 且 `object_kind=chart` 且 `has_chart_title=true`（`fill_mode=chart_title`）。

写入模式：
- `--text`：单元格常量填充，或形状 TextFrame / 图表 ChartTitle 纯文本替换；
- `--values-json`：仅单元格矩形矩阵（形状/图表选区拒绝）。

写入前核对 `address`（单元格）或 `object_name`（形状/图表）与文本。无 TextFrame 的形状、无 ChartTitle API 的图表、系列/轴仍返回 `OBJECT_SELECTION_UNSUPPORTED`。`saved=false`、只读与 `expected_selection_text` 不匹配均在备份前拒绝（未保存提示 `save-open-document`）。不启动 WPS，也不 `Quit()`；`selection_preserved` 固定为 false。

### `spreadsheet-selection-delete`

对 cell/range/multi_area 执行 `ClearContents`（失败则逐格 `Value2=$null`）；对带 TextFrame 的形状清空形状文本；对带 ChartTitle 的图表清除标题（`HasTitle=false`）。护栏与 replace 对齐。无内容返回 `SELECTION_EMPTY`。dry-run、备份、读回与幂等齐全。不启动 WPS，不 `Quit()`。

### `writer-selection-replace`

流程：校验文本 -> 读取选区 -> 预检 -> dry-run 返回预览 -> 备份 -> 按范围（不是按 `Selection` 对象）写入 -> 保存 -> 读回校验 -> 记录幂等。

拒绝条件（均在备份之前，返回结构化错误）：

| 错误码 | 条件 |
| --- | --- |
| `DOCUMENT_HAS_UNSAVED_CHANGES` | 打开的文档有未保存修改（`saved=false` 或 COM `status=unsaved`）。备份和写后/导出源校验基于磁盘上的已保存版本，所以必须先用 `save-open-document` 显式保存；选区写回与导出都不会隐式保存（P3-439：错误文案统一提示该命令，不再写 “save it in WPS”） |
| `DOCUMENT_READ_ONLY` | 打开的文档是只读的。替换会在备份和写入之前拒绝；否则 WPS 会在只读文档上保存并卡住 |
| `SELECTION_EMPTY` | 选区折叠 |
| `SELECTION_TOO_LARGE` | 选区超过 4096 字符 |
| `SELECTION_SPANS_STRUCTURE` | 选区含段落标记、单元格标记等控制字符，或含域、图形等非文本对象；单行纯文本才允许替换，避免意外合并段落 |
| `SELECTION_MISMATCH` | 给出 `--expected-selection-text` 但与当前选区不一致；或预览与写入之间选区变化 |
| `INVALID_ARGUMENT` | 替换文本含换行、控制字符或超过 4096 字符 |

写入脚本会再次核对选区范围与文本（区分大小写），防止预览到写入之间用户移动了选区。写入后不会恢复用户选区（结果里 `selection_preserved: false`）。

### `writer-selection-insert`

在折叠光标（`start == end`）处插入单行文本。流程与选区替换对齐：校验文本 -> 读取选区 -> 预检 -> dry-run -> 备份 -> 按 `Range(start, start)` 写入 -> 保存 -> 读回 -> 幂等。

| 错误码 | 条件 |
| --- | --- |
| `SELECTION_NOT_COLLAPSED` | 选区未折叠；应先折叠光标，或改用 `writer-selection-replace` |
| `SELECTION_MISMATCH` | 给出 `--expected-start` 但与当前光标不一致；或预览与写入之间光标移动 |
| `DOCUMENT_HAS_UNSAVED_CHANGES` / `DOCUMENT_READ_ONLY` | 与替换相同 |
| `INVALID_ARGUMENT` | 插入文本为空、含换行/控制字符或超过 4096 字符 |

写入后不会恢复用户选区（`selection_preserved: false`）。

### `writer-selection-delete` / `presentation-selection-delete`

清空当前非空纯文本选区（等价于把选区文本置空）。护栏与对应组件的 selection-replace 相同：未保存/只读/空选区/超大/结构跨度/`expected_selection_text` 不匹配均在备份前拒绝。dry-run、备份、读回（删后探测文本不得仍等于被删文本）与幂等齐全。不启动 WPS，不 `Quit()`，不恢复用户选区。

### `save-open-document`

对已注册且已有磁盘路径的打开文档显式 `Save()`。这是唯一会把内存未保存修改写回源文件的打开文档命令；选区/导出类命令仍在遇到 `Saved=false` 时拒绝，不会隐式保存。

- dry-run 只报告 `saved` / `would_modify`，不备份、不写入。
- 已经 `Saved=true`：成功、`wrote=false`、不备份。
- 有未保存修改：先备份磁盘上的上次已保存版本，再 `Save()`；校验 `saved=true` 且文档仍打开。
- 只读拒绝为 `DOCUMENT_READ_ONLY`（备份前）。无路径的未命名文档没有 `document_id`，应改用 `save-as-open-document`。

### `save-as-open-document`
对运行实例中**尚无磁盘路径**的打开文档执行 `SaveAs` 到新的原生路径（Writer `.docx` / Spreadsheet `.xlsx` / Presentation `.pptx`），成功后按路径注册 `document_id`。

- 用 `--component` + `--name`（`open-documents` 返回的 `Name`）定位；重名未命名文档返回 `AMBIGUOUS_OPEN_DOCUMENT`；已有磁盘路径返回 `DOCUMENT_ALREADY_PATHED`（改用 `save-open-document` / `export-open-document-copy`）。
- 拒绝已存在输出、错误扩展名、只读；无先前源文件可备份。
- dry-run / 幂等齐全；不启动 WPS，不 `Quit()`。
- 不启动 WPS，不 `Quit()`，不 `Close()`。

### `export-open-document`

- 支持 Writer、Presentation 与 Spreadsheet；输出必须是新的 `.html` 或 `.htm` 路径；已存在则返回 `OUTPUT_EXISTS`，不覆盖。
- 要求文档已保存。
  - Writer：在运行实例中以 `Documents.Add(源文件路径)` 建立副本，对副本 `SaveAs2(输出, 10)`（失败退 `SaveAs`），再不保存地关闭副本。
  - Presentation：对已打开演示执行 `SaveCopyAs(输出, 12)`（失败退 format 23），不改名、不关闭源文件；若写出的是 ZIP/包字节而非 HTML，返回 `EXPORT_OUTPUT_NOT_HTML`。
  - Spreadsheet：本机 `SaveCopyAs` 不接受 FileFormat；先 `SaveCopyAs` 到临时 xlsx，再对副本 `SaveAs(输出, 44)`（失败退 45）并关闭副本、删除临时文件；不改名、不关闭源文件；非 HTML 字节返回 `EXPORT_OUTPUT_NOT_HTML`。
- 导出后校验：输出文件存在且非空、源文件哈希未变、源文档仍在运行实例中打开。
- 结果总是带 `known_losses`，说明 HTML 导出有损、图片与样式可能在伴随目录中、保真度需实测。

### `export-open-document-pdf`

- 支持 Writer、Presentation 与 Spreadsheet；输出必须是新的 `.pdf` 路径；已存在则返回 `OUTPUT_EXISTS`，不覆盖。
- 要求文档已保存。
  - Writer：`Documents.Add(源文件路径)` 建副本，对副本 `ExportAsFixedFormat(输出, 17)`（失败退 `SaveAs` 17），再不保存地关闭副本。
  - Presentation：对已打开演示 `ExportAsFixedFormat(输出, 2)`；失败则临时 `SaveCopyAs` 再对副本 `SaveAs(输出, 32)` 并关闭副本。不改名、不关闭源文件。
  - Spreadsheet：对已打开工作簿 `ExportAsFixedFormat(0, 输出)`（失败退参数顺序对调）。不改名、不关闭源文件。
- 写出的字节若不是 `%PDF`，返回 `EXPORT_OUTPUT_NOT_PDF`。
- 导出后校验：输出存在且非空、源文件哈希未变、源文档仍在运行实例中打开。
- 结果带 `known_losses`：PDF 不可再当原生文档编辑，域/公式/动画会被压平。

### `export-open-document-copy`

- 支持 Writer、Presentation 与 Spreadsheet；输出路径扩展名必须与源文件相同；已存在则返回 `OUTPUT_EXISTS`，不覆盖。
- 要求文档已保存。对已打开文档执行 `SaveCopyAs(输出)`；Writer 若无 `SaveCopyAs` 则退 `Documents.Add` + `SaveAs` 并关闭副本。
- 不改名、不关闭源文件；不对扩展名做格式转换。
- 对 `.docx` / `.xlsx` / `.pptx` 校验输出以 `PK` 包头开头，否则返回 `EXPORT_OUTPUT_NOT_PACKAGE`。
- 导出后校验：输出存在且非空、源文件哈希未变、源文档仍在运行实例中打开。

### `export-open-document-text`

- 支持 Writer、Presentation 与 Spreadsheet；输出必须是新的 `.txt` 路径；已存在则返回 `OUTPUT_EXISTS`，不覆盖。
- 要求文档已保存。
  - Writer：`Documents.Add` 建副本，对副本 `SaveAs2/SaveAs` 格式 7（Unicode 文本；失败退格式 2），再关闭副本。
  - Presentation：只读遍历幻灯片形状文本，写出 UTF-8 `.txt`（`ExtractShapeText`），不改源文件。
  - Spreadsheet：临时 `SaveCopyAs` 后对副本 `SaveAs` 格式 42（失败退 20），再关闭并删除临时文件。
- 写出的字节若是 ZIP/PDF 等非文本，返回 `EXPORT_OUTPUT_NOT_TEXT`。
- 导出后校验：输出存在且非空、源文件哈希未变、源文档仍打开。结果带 `known_losses`（格式/图片/图表丢失）。

## 推荐调用流程

1. `open-documents --register` 列出并注册已打开且已保存的文档，拿到 `document_id`。若文档有路径但 `saved=false`，先用 `save-open-document --dry-run` 预览，再显式保存。
2. `writer-selection-read --document-id ...` 查看用户当前选区。
3. 有选中文本时 `writer-selection-replace` / `writer-selection-delete`（或 Presentation 对应命令）用 `--dry-run --expected-selection-text "<上一步读到的文本>"` 预览；仅有折叠光标时用 `*-selection-insert --dry-run --expected-start <start>`。
4. 去掉 `--dry-run`，带固定的 `--request-id` 执行。
5. 需要 HTML 时 `export-open-document --document-id ... --output new.html`。需要 PDF 时 `export-open-document-pdf --document-id ... --output new.pdf`。需要同格式磁盘副本时 `export-open-document-copy --document-id ... --output new.docx|xlsx|pptx`。需要纯文本时 `export-open-document-text --document-id ... --output new.txt`。
6. 检查结果中的 `validation_passed`、`backup`、`source_unchanged`。

定位优先用选区、段落、书签和关键词，不要依赖页码。

## 验证情况

- Linux 离线测试 `tests/test_open_documents.py`：对 COM 层打桩，覆盖附着失败、列表、选区读取、全部拒绝路径、备份、幂等重放、读回失败、超时、导出的输出校验与源文件哈希变化。
- `tests/test_open_documents_powershell.py`：设置 `pwsh` 后，把真实生成的 PowerShell 脚本放到一个用 C# 实现的假 COM 对象上执行，验证脚本逻辑：按路径查找文档、状态返回、范围替换、`-cne` 比较、未保存拒绝、导出副本。没有 `pwsh` 时跳过。生成的脚本也用 PowerShell 解析器检查过语法。
- 2026-10-09 在本机 WPS Writer 12.0 上用临时副本验证了四个命令。先打开 `writer_table_fixture.docx` 的副本并选中 `Body marker`，再附着，没有对这个实例调用 `Quit()`。
  - `open-documents --register` 返回该文档，`saved=true`，`document_id` 为 `doc_fd09bd30bb328be6`。
  - `writer-selection-read` 返回选区 `Body marker`（0 到 11）、`paragraph_index` 1、`page_number` 1，`page_info_verified` 仍为 false。
  - `writer-selection-replace` 的 dry-run 没有改文件；正式替换为 `PRD12` 后 `validation_passed` 为 true，`selection_preserved` 为 false。
  - `export-open-document` 走 `SaveAs2`，输出非空 HTML，其中同时有 `PRD12` 和原文 `outside table`。`source_unchanged` 与 `source_still_open` 都为 true。
- 同一天补测了四个边界，临时文件哈希都没有变，结束后没有残留进程：
  - 未保存：内存里插入文本后，`saved=false`。选区替换和 HTML 导出都返回 `DOCUMENT_HAS_UNSAVED_CHANGES`。
  - 只读：`open-documents` 报 `read_only=true`。第一次选区替换等到 120 秒超时，WPS 停在 `open.docx (只读) *` 且拒绝 COM 关闭。现已在备份和写入之前返回 `DOCUMENT_READ_ONLY`，重测立即拒绝且文件未改。
  - 隐藏：`Visible=false` 时仍能附着，`ActiveWindow` 不为空，按路径列出文档，选区读取成功。
  - 分页：在第一段后插入分页符和 `PAGE2MARK`。选区读取返回该文本、`paragraph_index` 3、`page_number` 2，`page_info_verified` 仍为 false。
- 只读 HTML 导出：导出脚本不读取 `ReadOnly`，只对 `Documents.Add` 出来的副本做 `SaveAs2`。假 COM 在 `WPSFAKE_READONLY=1` 时仍写出 HTML，源文件字节不变。
- 2026-10-09 本机 Writer 12.0 补测：以 `Documents.Open(..., ReadOnly=$true)` 打开 `writer_table_fixture.docx` 临时副本（`read_only=true`、`saved=true`），`export-open-document` 走 `SaveAs2` 写出 321256 字节 HTML 与伴随目录，`source_unchanged` / `source_still_open` / `validation_passed` 均为 true，源 SHA-256 未变；结束后 holder 正常退出，无残留 wps/et/wpp。单机结果，不作跨版本结论。
- 2026-10-09 本机 Presentation 12.0：对已打开 disposable pptx 执行 `export-open-document`，`SaveCopyAsHtml` 写出 2519 字节 HTML 与 `export.files`，`source_unchanged` / `source_still_open` / `validation_passed` 均为 true。同日 `presentation-selection-read`：无窗口打开返回 `SELECTION_UNAVAILABLE`；有窗口时可附着并返回 `selection_kind`。同日 `presentation-selection-replace`：对可见窗口内文本框选中的 `P3-401 mark` dry-run 后写回 `P3-401 done`，`validation_passed` 为 true；写回后需从 Shape/TextRange 重新读回（原 TextRange 引用在赋值后可能失效）。单机结果，不作跨版本结论。
- 2026-10-09 本机 Spreadsheets：对可见窗口打开的 disposable xlsx 选中 `$A$1`，`spreadsheet-selection-read` 返回 `selection_kind=cell`、`address=$A$1`、`selection_text=P3-402 mark`。同日 `export-open-document` 走 `SaveCopyAsThenSaveAsHtml` 写出 19479 字节 HTML，`source_unchanged` / `source_still_open` / `validation_passed` 均为 true。同日 `spreadsheet-selection-replace`：`$A$1` 上 `P3-404 mark`→`P3-404 done`，`validation_passed=true`。单机结果，不作跨版本结论。
- 2026-10-10 本机 WPS 12.0：`export-open-document-pdf` 对已打开 Writer 走副本 `ExportAsFixedFormat`，写出 243541 字节 `%PDF-1.7`；对已打开表格走 `ExportAsFixedFormat`，写出 27913 字节 PDF。两者 `source_unchanged` / `source_still_open` / `validation_passed` 均为 true，源文件仍打开。同日已打开演示走 `SaveCopyAsThenSaveAsPdf` 写出 21554 字节 PDF。单机结果，不作跨版本结论。
- 2026-10-10 本机 WPS 12.0：`export-open-document-copy` 对已打开 Writer 因无可用 `SaveCopyAs` 走 `DocumentsAddSaveAs`，写出 26721 字节 `PK` docx；对已打开表格走 `SaveCopyAs`，写出 8781 字节 xlsx。同日已打开演示 `SaveCopyAs` 写出 37198 字节 pptx。源哈希未变、文档仍打开、`validation_passed=true`。单机结果，不作跨版本结论。
- 2026-10-10 本机 WPS 12.0：`writer-selection-insert` 在折叠光标 `start=end=0` 处 dry-run 后插入 `P3-413 mark`，`read_back_text` 匹配、`validation_passed=true`、有备份。单机结果，不作跨版本结论。
- 2026-10-10 本机 WPS 12.0：`presentation-selection-insert` 在空文本框折叠光标 `text_range_start=1`/`collapsed=true` 处插入 `P3-414 mark`，`read_back_text` 匹配、`validation_passed=true`。单机结果，不作跨版本结论。
- 2026-10-10 本机 WPS 12.0：`export-open-document-text` 对已打开 Writer 走 `SaveAsUnicodeText` 写出 10115 字节 txt；对已打开表格走 `SaveCopyAsThenUnicodeText` 写出 28 字节 txt。同日已打开演示 `ExtractShapeText` 写出 18 字节 txt。源哈希未变、文档仍打开、`validation_passed=true`。单机结果，不作跨版本结论。
- 2026-10-10 本机 Spreadsheets：选中 `$A$1:$B$1`（`a`/`b`），`spreadsheet-selection-replace` 常量填充为 `P3-405 fill`，`cell_count=2`、`cells_matched=true`、`validation_passed=true`。同日矩阵模式 `values=[["c","d"]]`，`fill_mode=matrix`、`read_back_values=["c","d"]`、`validation_passed=true`。单机结果，不作跨版本结论。
- 2026-10-10 本机 WPS 12.0：`writer-selection-delete` 选中 `P3-416-DEL` dry-run 后删除，`validation_passed=true`、有备份、同 request_id 幂等重放；`presentation-selection-delete` 文本框选中同标记删除，`read_back_text=""`、`validation_passed=true`。单机结果，不作跨版本结论。
- 2026-10-10 本机 Spreadsheets：多区域 `$A$1,$C$1` 上 `values_json=[["x","y"]]`，`fill_mode=matrix`、`cells_matched=true`、`validation_passed=true`。单机结果，不作跨版本结论。
- 2026-10-10 本机 WPS 12.0：`save-open-document` 对已打开 Writer 脏文档 dry-run 后 `Save()`，`wrote=true`、有备份、`validation_passed=true`、同 request_id 幂等重放。同日已打开脏表格与脏演示同样 dry-run 后 `Save()`，`wrote=true`、有备份、`source_still_open=true`、`validation_passed=true`、同 request_id 幂等重放。单机结果，不作跨版本结论。
- 2026-10-10 本机 Spreadsheets：`$A$1` 上 `P3-419 mark` 经 `spreadsheet-selection-delete` `ClearContents` 清空，`cells_matched=true`、`validation_passed=true`。单机结果，不作跨版本结论。
- 2026-10-10 本机 Spreadsheets：多区域 `$A$1,$C$1` 常量填充 `P3-422 fill` 成功；对 `ChartObject`（`Chart 1`）选区，`spreadsheet-selection-read` 返回 `selection_kind=non_range`/`object_kind=chart`，`spreadsheet-selection-replace` 与 `spreadsheet-selection-delete` 均在备份前返回 `OBJECT_SELECTION_UNSUPPORTED`。单机结果，不作跨版本结论。
- 2026-10-10 本机 Spreadsheets：多区域 `$A$1,$C$1`（`P3-427-A`/`P3-427-C`）经 `spreadsheet-selection-delete` `ClearContents` 清空，`cells_matched=true`、`read_back_values=["",""]`、`validation_passed=true`、有备份、同 request_id 幂等重放。单机结果，不作跨版本结论。
- 2026-10-10 本机 Writer：`Documents.Add` 未命名文档经 `open-documents` 列出 `document_id=null`、`path_exists=false`；`save-open-document` 对虚构 id 返回 `DOCUMENT_NOT_FOUND`。单机结果，不作跨版本结论。
- 2026-10-11 本机 Writer：未命名 `文字文稿1` 经 `save-as-open-document` SaveAs 到 disposable docx（9956 字节），`wrote=true`/`path_matched=true`/`validation_passed=true`，并注册 `document_id`（P3-444）。单机结果，不作跨版本结论。
- 2026-10-11 本机 Writer：粗体 16pt 选区 `P3-445 mark` 经 `writer-selection-replace`→`P3-445 done`，`formatting_preserved=true`/`formatting_mode=uniform_character`，读回仍 Bold 且 Size=16（P3-445）。混排格式仍不支持。单机结果，不作跨版本结论。
- 2026-10-11 本机 Spreadsheets：轴标题选区 `P3-446-Chart` 读回 `has_axis_title=true`/`P3-446 axis`；`spreadsheet-selection-replace`→`P3-446 done`，`fill_mode=axis_title`、`validation_passed=true`、有备份（P3-446）。单机结果，不作跨版本结论。
- 2026-10-11 本机 Spreadsheets：系列选区 `P3-447-Chart`/`series_name=val` 读回 `has_series_values=true`（TAB 拼接 `10`/`20`）；`spreadsheet-selection-replace`→`30`/`40`，`fill_mode=series_values`、`validation_passed=true`、有备份（P3-447）。几何仍不支持。单机结果，不作跨版本结论。
- 2026-10-10 本机 Spreadsheets：连续区域 `$A$1:$B$1`（`selection_kind=range`）经 `spreadsheet-selection-delete` 清空，`cells_matched=true`、`validation_passed=true`、有备份、同 request_id 幂等重放。单机结果，不作跨版本结论。
- 2026-10-10 本机 Spreadsheets：`$A$1` 公式 `=1+2`（显示 `3`）经 `spreadsheet-selection-delete` 清空后 `read_back_text=""`、读回 `formula=null`、`validation_passed=true`、有备份、同 request_id 幂等重放。单机结果，不作跨版本结论。
- 2026-10-10 本机 Spreadsheets：矩形形状 `P3-433-Rect` 选区读回 `selection_kind=non_range`/`object_kind=shape`；`spreadsheet-selection-replace` 与 `spreadsheet-selection-delete` 均在备份前返回 `OBJECT_SELECTION_UNSUPPORTED`（探测已避免把工作表形状误判为 chart）。单机结果，不作跨版本结论。
- 2026-10-10 本机 Spreadsheets：已打开含 `P3-434-PLAIN` 与公式 `=10+5`（显示 15）的工作簿经 `export-open-document` HTML（`SaveCopyAsThenSaveAsHtml`，19565 字节）导出；去标签后纯文本标记保留，显示值与 `x:fmla` 保留，`source_unchanged`/`source_still_open`。单机结果，不作跨版本结论。
- 2026-10-10 本机 Presentation：整形状选区 `selection_kind=shapes`/`shape_name=P3-435-Rect`；`presentation-selection-replace` 与 `presentation-selection-delete` 均在备份前返回 `SELECTION_SPANS_STRUCTURE`。单机结果，不作跨版本结论。
- 2026-10-11 本机 Spreadsheets：脏工作簿（内存改 `B1`、选中 `$A$1`=`P3-436 mark`）上 `spreadsheet-selection-replace` 返回 `DOCUMENT_HAS_UNSAVED_CHANGES` 且未创建备份；随后 `save-open-document` `wrote=true`/`validation_passed=true`。单机结果，不作跨版本结论。
- 2026-10-11 Writer/Presentation 选区 replace/insert/delete 与表格一致：`saved=false` 时于备份前返回 `DOCUMENT_HAS_UNSAVED_CHANGES`（提示 `save-open-document`）。离线单测覆盖；本机脏 Writer 上 `writer-selection-replace` 拒绝且无备份，随后 `save-open-document` `wrote=true`/`validation_passed=true`。同日脏演示上 `presentation-selection-replace` 同样拒绝且无备份，随后 `save-open-document` 成功。单机结果，不作跨版本结论。
- 2026-10-11 本机脏 Writer：`export-open-document` 返回 `DOCUMENT_HAS_UNSAVED_CHANGES` 且文案提示 `save-open-document`；保存后 HTML 导出 38203 字节、`source_still_open=true`（P3-439/P3-440）。单机结果，不作跨版本结论。
- 2026-10-11 本机 Spreadsheets：矩形 `P3-442-Rect` 选区读回 `non_range`/`shape`/`has_text_frame=true`/`P3-442 mark`；`spreadsheet-selection-replace`→`P3-442 done`，`fill_mode=shape_text`、`validation_passed=true`、有备份（P3-442）。单机结果，不作跨版本结论。
- 2026-10-11 本机 Spreadsheets：图表 `P3-443-Chart` 选区读回 `non_range`/`chart`/`has_chart_title=true`/`P3-443 title`；`spreadsheet-selection-replace`→`P3-443 done`，`fill_mode=chart_title`、`validation_passed=true`、有备份（P3-443）。WPS 上 ChartObject 选区多为 ChartArea，经 `Selection.Parent.HasTitle` 识别。系列/轴仍不支持。单机结果，不作跨版本结论。
- 仍未覆盖：更复杂的分页（分节、页眉、文本框）下页码是否仍然准确。

## 未做项

- 表格图表形状**几何/样式**编辑（P3-442/P3-443/P3-446/P3-447：已支持形状 TextFrame、图表 ChartTitle/AxisTitle 纯文本与选中 Series Values TAB 写回；几何仍为 `OBJECT_SELECTION_UNSUPPORTED`；单元格多区域常量/矩阵写入见 P3-407/P3-417）。
- 精确「第 N 页」操作，PRD 明确要求实测后再决定，不作首版承诺（读选区仅尽力返回 `page_number` 且 `page_info_verified=false`；P3-431 离线闸门禁止已打开文档 MCP/CLI 接受按页定位输入）。
- 除 `save-open-document` / `save-as-open-document` 外，其它命令对未保存修改仍直接拒绝，不隐式保存或合并。无路径未命名文档经 P3-444 `save-as-open-document` 可另存并注册；在此之前仅能列出且 `document_id=null`（P3-428）。
- 选区内**混排**字符格式与段落格式的精确重建仍不支持（P3-445：已对 Writer/Presentation 选区替换做统一字符格式快照回写——font name/size/bold/italic/underline/color；混排 run 仍不重建）。
