# Phase 6 Windows results — main@655d76c

- 日期：2026-10-15
- 机器：Windows 10.0.19045；Python 3.12.14
- WPS：Writer、表格、演示的 FileVersion 都是 12.8.2.18913（`office6`）
- 提交：`655d76c`
- 诊断 JSON：`scripts/real_wps_verify_p6/RESULTS-655d76c/`。路径里的用户名已换成 `<user>`。

`.docx` 的打开命令仍是 `wps.exe "%1"`，没有 `/Automation`。`AssocQueryString` 对三个扩展名的命令分别是 `wps.exe "%1"`、`et.exe "%1"`、`wpp.exe "%1"`。

`open-documents` 写到磁盘的 `instances` 没有 `attached_via`。下面的 `attached_via` 来自同一次附着用的 COM 返回（文档还开着时调用 `_run_open_documents_com`）。

## Writer，双击 `report.docx`：(a)

`Invoke-Item` 打开了 WPS 文字。`open-documents --component writer --register`：`ok: true`，`errors` 为空，`documents` 里是这份 `report.docx`，`document_id` 为 `doc_4c68ae9d6dc9e5bc`。`attached_via` 是 `running_object_table`。

诊断 `diag-writer-doubleclick.json`：

- 九个 ProgID 的 `active_object` 都是 false。`kwps.Application` 的 HRESULT 是 `0x800401E3`。
- ROT 有这条文档：`display_name` 和 `document_full_name` 都是 `report.docx`，`app_name` 是 `Microsoft Word`，`app_path` 是 `office6`，`app_version` 是 `12.0`。
- 进程命令行：`wps.exe "…\report.docx"`，没有 `/Automation`。窗口标题 `report.docx - WPS 文字`。

`export-open-document-text`：`ok: true`，`errors` 为空。`writer.txt` 是 `Quarterly report`、`Status: DRAFT`、`Owner: Finance`。

`close_unchanged_document` 返回 `closed`，但这个 `wps.exe` 还在。之后 `open-documents` 列到的是另一份临时目录里的 `report.docx`（早前评测留下的），不是这一份。这个进程是本步骤启动的，已结束，再做下一个组件。

记下的 `wps.exe`：`C:\Program Files (x86)\Kingsoft\WPS Office\12.8.2.18913\office6\wps.exe`。

## 表格，打开 `book.xlsx`：(a)

`Invoke-Item`、`cmd start` 和 `explorer.exe` 都没有启动 `et.exe`。进程跟踪看到的是 `OpenWith.exe -Embedding`。没有改打开命令。随后按注册表里的打开命令直接启动了 `et.exe "…\book.xlsx"`，窗口标题 `book.xlsx - WPS 表格`。

`open-documents --component spreadsheets --register`：`ok: true`，`errors` 为空，`document_id` 为 `doc_bba9573e52bf0b4d`。`attached_via` 是 `running_object_table`。

诊断 `diag-spreadsheets-doubleclick.json`：

- 没有 ProgID 的 `active_object` 为 true。
- ROT 有 `book.xlsx`，`app_name` 是 `Microsoft Excel`，`app_path` 是 `office6`，`app_version` 是 `12.0`。
- 进程命令行：`et.exe "…\book.xlsx"`。

`export-open-document-text`：`ok: true`，`errors` 为空。导出的文字是 `seed`。

关闭返回 `closed`。进程仍在，命令行仍是这份测试文件，已结束该进程。

## 演示，打开 `deck.pptx`：(a)

和表格一样：ShellExecute 启动的是 `OpenWith.exe -Embedding`，没有 `wpp.exe`。按注册表命令直接启动 `wpp.exe "…\deck.pptx"` 后，窗口先是 `WPS演示`，诊断时标题为 `deck.pptx - WPS 演示`。

`open-documents --component presentation --register`：`ok: true`，`errors` 为空，`document_id` 为 `doc_e7320b3667c6f2d2`。`attached_via` 是 `running_object_table`。

诊断 `diag-presentation-doubleclick.json`：

- 没有 ProgID 的 `active_object` 为 true。
- ROT 有 `deck.pptx`，`app_name` 是 `Microsoft PowerPoint`，`app_path` 是 `office6`，`app_version` 是 `12.0`。
- 进程命令行：`wpp.exe "…\deck.pptx"`。

`export-open-document-text`：`ok: true`，`errors` 为空。导出的文字是 `Quarterly review`、`Status: DRAFT`。

关闭返回 `closed`。进程仍在，已结束该进程。

三个组件都不是 (b)。没有出现 `WPS_INSTANCE_NOT_AUTOMATABLE`。

## Writer 对照组，`/Automation`

没有 WPS 在运行时：`wps.exe /Automation "…\report.docx"`。窗口标题 `report.docx - WPS 文字`。

诊断 `diag-writer-automation.json`：

- `kwps.Application` 的 `active_object` 为 true，HRESULT `0x00000000`，`app_name` 是 `Microsoft Word`，`version` 是 `12.0`。这一次探测里 `documents` 是空数组。
- ROT 仍有这份 `report.docx`，`app_name`、`app_path`、`app_version` 与双击那次相同。
- 进程命令行：`wps.exe /Automation "…\report.docx"`。

紧接着的 `open-documents --component writer`：`ok: true`，`errors` 为空，列出这份 `report.docx`。`attached_via` 是 `active_object`。

关闭返回 `closed`，随后结束了这个 `wps.exe`。

## 复核（2026-10-15）

以上是上机时记录的原文，没有改动。复核结论：

- **P6-002 和 P6-004 完成，G1 达成。** 三个组件都走 (a)：`GetActiveObject` 拿不到，经 ROT 附着后列出了文档，文本也导出了。没有出现 `NO_RUNNING_WPS_INSTANCE`，也不需要 `WPS_INSTANCE_NOT_AUTOMATABLE`。
- **表格和演示没有经过 shell。** 在这台机器上，对 `.xlsx`、`.pptx` 用 `Invoke-Item` 打开时弹出的是“打开方式”（`OpenWith.exe`），不会启动 WPS。所以这两个组件改为直接运行注册表里的打开命令（`et.exe "%1"`、`wpp.exe "%1"`）。这和双击运行的是同一条命令，打开命令也没有改，所以计入 G1。双击在这台机器上会先弹出选择框，这是 Windows 的默认程序设置，不是本项目的问题。
- **WPS 通过 COM 报的名字是 `Microsoft Word`、`Microsoft Excel`、`Microsoft PowerPoint`。** 判断是不是 WPS 的条件（`Test-WpsApplication`）这次是靠安装路径里的 `Kingsoft`、`WPS` 通过的。为了照顾装在别的目录的情况，现在也接受路径里带 `office6`（WPS 12 的程序目录名）。Microsoft Office 的路径是 `Office16` 之类，不会误判。
- **登记开着的文档时读到了文件内容**（`register` 会计算 SHA-256）。这说明 WPS 允许别的程序在它开着文档时读取文件。P6-008 的修复就是以此为依据。
- **`close_unchanged_document` 关闭文档后，WPS 进程不会退出。** 这和 runner 的设计一致：runner 只结束自己启动的进程。手动步骤里由操作人结束进程，也是对的。
