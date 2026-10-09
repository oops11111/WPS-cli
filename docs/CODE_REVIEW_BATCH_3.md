# 代码审查报告：批次 3 补充（G-01 与函数级审查）

范围：`CODE_REVIEW_BATCH_3_6.md` 中 G-01 的修复，以及对 `spreadsheet_ops`、`writer_ops`、`presentation_ops`、`validators`、`spreadsheet_ranges` 的函数级审查。

环境限制同前：Linux，没有 WPS 与 PowerShell，所有 COM 行为都只做了离线 mock，没有真实验证。

## 已修复

### G-01 OOXML 解压大小限制（已完成）

新增 `ooxml.py`：

- `read_zip_part(archive, name, max_bytes)`：先检查 `ZipInfo.file_size`，再读取，并对实际读取字节数二次校验。
- `check_archive_limits`：限制条目数与总解压大小，结果按压缩包对象缓存。
- `parse_xml_part`：封装读取与解析。
- `load_workbook_guarded`：打开 xlsx 前先做压缩包检查。
- 超限抛 `OoxmlTooLargeError`，CLI 层转成结构化错误 `INPUT_TOO_LARGE`，退出码规则不变。

`document_text`、`writer_structure`、`presentation_text`、`html_roundtrip`、`writer_ops`、`spreadsheet_inspect`、`snapshots`、`validators` 已全部替换。默认上限：单部件 64 MB，总解压 512 MB，条目数 20000。测试在 `tests/test_ooxml_limits.py`，覆盖超大部件、总大小与条目数超限、xlsx 加载保护、非 zip 文件透传，以及 `INPUT_TOO_LARGE` 的 CLI 输出。

修复过程中出现过一次回归：`read_zip_part` 改成用 `ZipInfo` 读取后，测试中按名称监听 `archive.read` 的用例失败。已改回按名称读取，并保留测试。

### H-01 表格写入没有值校验（已完成）

位置：`spreadsheet_ops.write_spreadsheet_range`。

问题：

1. 以 `=`、`+`、`-`、`@` 开头的字符串会原样交给 COM。`Value2` 是否把 `=` 开头的字符串当作公式求值取决于 WPS，未在真实环境验证，但对 Agent 写入的外部文本来说，这是公式注入风险。
2. 数值类型没有检查，`NaN` 与 `Infinity` 会被序列化为非法 JSON 或写入脏值。
3. 布尔值在 PowerShell 脚本里先落入数值分支。

修复：`_validate_write_values` 在空值检查之后、范围检查之前运行，拒绝公式前缀字符串、非有限数、不支持的类型；PowerShell 脚本中布尔分支提前。`mcp_schema` 中的安全说明与 `docs/P3_SPREADSHEET_WRITE_GUARDRAILS.md` 已更新。测试在 `tests/test_spreadsheet_write_guard.py`。

注意：这会拒绝合法的负数字符串，例如 `"-5"`。调用方应传数值 `-5`。这是有意取舍。

### H-02 Writer 表格单元格写入缺少文本校验（已完成）

位置：`writer_ops.writer_table_write`。

问题：`text` 没有任何校验。含换行的文本会让 Word 产生多个段落，读回的单元格文本与写入值不相等，操作会在已经改动文件之后才报 `VALIDATION_FAILED`。书签路径已经限制了 4096 字符、单行，这里不一致。

修复：在备份与 COM 调用之前，拒绝超过 4096 字符、含 ASCII 控制字符（含换行、制表符、NUL）的文本，返回 `INVALID_ARGUMENT`。测试在 `tests/test_writer_table_write_guard.py`，断言被拒绝时不创建备份、不调用 COM。

## 审查后未改动的发现

### H-03（P3）`table_count_preserved` 只报告不参与校验

`writer_table_write` 在写入后表格数变化时，仍然返回成功，只在结果里给出 `table_count_preserved: false`。现有测试 `test_writer_table_write_accepts_table_count_normalization_when_cell_matches` 明确把这当作预期行为（WPS 保存时会合并相邻表格）。因此没有改成失败。调用方应检查该字段。

### H-04（P3）单元格内富内容在写入时会被丢弃

写入单元格文本时，按 Word 对象模型的常规行为，替换单元格文本会连带丢弃该单元格内的图片、域、超链接、嵌套表格、内容控件（未在真实 WPS 验证）。目前没有预检。备份与恢复流程可以回滚，但 Agent 看不到风险提示。

建议：在 `document_text` 增加 `docx_table_cell_rich_content` 之类的预检，检测到 `w:drawing`、`w:pict`、`w:object`、`w:hyperlink`、`w:fldChar`、`w:tbl`、`w:sdt` 时返回新错误码，或要求显式 `--allow-rich-content`。需要新增错误码与文档，本次未做。

### H-05（P3）Writer 查找文本的 255 字符限制

Word 的 `Find.Text` 有 255 字符上限，超出时 COM 会报错。`writer_replace` 没有预检，错误会以 `COM_OPERATION_FAILED` 返回，信息不友好。未在真实环境验证。建议在 `writer_replace` 入口加长度校验。

### H-06（P3）`validate_spreadsheet_read_range` 不支持带工作表名的范围

`Sheet1!A1:B2`、整列 `A:A`、整行 `1:1` 都返回 `INVALID_RANGE`。这是安全失败（拒绝而不是误读），也与"有限 A1 范围"的契约一致，只是错误信息来自 openpyxl，不够明确。实验结果：`A1`、`a1:b2`、`$A$1:$B$2` 通过，`B2:A1`、`A1:XFE1` 被正确拒绝。

### 一致性确认

- `presentation_ops`：`presentation_replace` 与 `_run_presentation_replace_com` 已经走 `guarded_com_mutation`，备份、写后校验路径与 Writer 一致，没有发现新问题。
- `validators.py` 的电子表格分支：现在通过受保护的 `load_workbook`，受 G-01 限制保护。

## 未覆盖

- 所有 COM 行为（`Value2` 是否求值公式、合并单元格的索引、Word 查找上限）没有真实 WPS 验证。
- `cli.py` 的拆分（G-02）、产物与文档整理（G-04、G-05）、依赖声明（G-06）、自我汇报模块（G-07）属于批次 3 到 6 报告中的其他项，本次未处理。
- `spreadsheet_ops` 与 `writer_ops` 的其他业务分支只靠现有用例覆盖。

## 验证

`PYTHONPATH=src python3 -m unittest discover -s tests`：479 个用例通过，67 个跳过（主要是 Windows 或 PowerShell 专用用例）。

> 更新：原「未改动」项中除 H-03（有意保留）外，已在后续提交中处理，见 `CODE_REVIEW_BATCH_6.md` 的「后续补完」一节。
