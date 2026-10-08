# 代码审查报告：批次 1（数据安全与一致性）与批次 2（COM 后端与外部进程）

审查环境：Linux，无 WPS、无 COM、无 PowerShell。所有结论来自静态阅读加 mock 复现。真实 WPS 行为未验证，相关条目已标注。

## 严重度定义

- P0：数据丢失、重复修改、注入、路径穿越。
- P1：错误的成功结果、契约破坏、竞态、进程泄漏、可导致文档损坏的路径。
- P2：健壮性、可维护性、性能。
- P3：测试与仓库卫生。

## 测试基线

安装 `python-docx`、`Pillow`、`pypdfium2`、`openpyxl`、`python-pptx` 后，共 424 个用例，其中 2 个失败、2 个错误、65 个跳过。

| 用例 | 原因 | 分类 |
|---|---|---|
| `test_cloud_sync` 的 2 个用例 | `cloud_sync.py` 调用 `powershell`，Linux 上不存在 | 环境，应加平台跳过 |
| `test_capabilities.test_probe_reports_registered_component_with_injected_resolver` | `probe_wps_capabilities` 在非 Windows 上先返回 `not_windows`，忽略注入的 resolver | 代码与测试耦合平台，见 F-13 |
| `test_cleanup_plan.test_build_cleanup_plan_is_read_only_and_identifies_candidates` | 断言写死 `fixtures\\phase3\\...` 反斜杠路径 | 测试写死路径分隔符 |

`test_mutation_source_stability` 在缺少 `python-pptx` 时整个模块导入失败。`pyproject.toml` 的 `test` extra 没有列出 `python-pptx` 和 `openpyxl`，但多个测试模块依赖它们。

## 发现清单

### F-01（P1）COM 超时异常未捕获，修改命令直接抛出 traceback，任务状态永久停在 running

位置：`writer_ops.py` 约 184、273、534 行，`presentation_ops.py` 190 行，`spreadsheet_ops.py` 1229、1384 行，`cli.py` 的 `_with_optional_task_status`。

对应的 `subprocess.run(..., timeout=120)` 没有任何 `except subprocess.TimeoutExpired`。同类的 sheet 重命名、新建、删除等函数都有处理，这 6 个函数是遗漏。

复现（mock `subprocess.run` 抛出 `TimeoutExpired`）：

- `cli.run([... "writer-replace", ..., "--request-id", "r1", "--task-id", "t1"])` 抛出 `TimeoutExpired`，没有 JSON 输出。
- `task_statuses.json` 中 `t1` 的 `state` 为 `running`，`terminal` 为 false，之后没有任何代码会把它改成终态，因为 `_with_optional_task_status` 调用 `response_factory()` 时没有 `try/finally`。
- 备份已创建，但操作记录未写入。

影响：对 Agent 来说，这正是最需要结构化错误的场景。任何未捕获异常都会让 CLI 输出 traceback，MCP 路径虽然会被 `run_cli` 转成结构化失败，但任务状态仍然卡住。

建议：
1. 这 6 个 COM 运行函数统一包装 `(OSError, subprocess.TimeoutExpired)`，返回 `COM_OPERATION_TIMEOUT`，并在 data 里写明"WPS 可能仍持有文档，修改结果未知"。
2. 抽出一个共享的 `run_powershell_script()` 辅助函数，统一处理脚本落盘、超时、清理、JSON 解析，替换约 20 处复制粘贴。
3. `_with_optional_task_status` 用 `try/except BaseException`，异常时把任务置为 `failed` 再抛出。

### F-02（P1）`restore-backup` 在目标文件写入失败时抛出未处理异常，且没有恢复原子性

位置：`backups.py` 的 `restore_backup`，最后的 `shutil.copy2(backup_file, target_path)`。

复现（mock 第二次 `copy2` 抛出 `PermissionError`，模拟 WPS 持有文件）：CLI 抛出 `PermissionError`，没有 JSON，没有操作记录。`mutation-request-inspect` 随后能看到 pre-restore 备份。

问题：
- 原地覆盖，不是写临时文件再 `os.replace`。进程崩溃或磁盘满会留下半截文件。
- Windows 下文档被 WPS 打开时 `PermissionError` 很常见，应返回结构化错误，如 `TARGET_LOCKED`。
- 恢复后没有验证目标文件的哈希与备份一致。

建议：写入同目录临时文件，校验哈希后 `os.replace`；捕获 `OSError` 返回结构化错误；恢复成功后比较目标哈希与备份哈希。

### F-03（P1）恢复不校验备份内容完整性，被篡改或损坏的备份会被直接写回

位置：`backups.py` 的 `restore_backup` 与 `_resolve_backup_file`。

`create_backup` 已把 `source_identity.source_sha256` 记入 `operations.json`，但恢复时没有使用。

复现：备份后把备份文件内容改成 `GARBAGE`，`restore-backup` 返回 `ok=true`，目标文件内容变成 `GARBAGE`。

建议：恢复前从操作记录查找该备份的哈希并比对，不一致返回 `BACKUP_CHANGED_AFTER_CREATION`（该错误码已在 `verify_backup_source` 中使用）。没有记录的旧备份应要求显式确认参数。

### F-04（P1，未在真实 WPS 验证）PowerShell 脚本在 `finally` 中无条件 `$app.Quit()`，可能关闭用户已打开的 WPS 会话

位置：`com_backend.py`、`writer_ops.py`、`spreadsheet_ops.py`、`presentation_ops.py` 中约 17 处 `Quit()`。

脚本使用 `New-Object -ComObject`。WPS 的 COM 服务器如果是单实例，调用会连接到用户正在使用的实例，此时 `Quit()` 会关闭用户的所有窗口，未保存内容可能丢失。`docs/` 中的进程生命周期审计没有覆盖"连接已有实例"的场景（我在其中检索 `Quit`、`attach`、`existing instance` 均无结果）。

建议：先在真实 Windows 上验证。如果属实，需在脚本启动前用 `Get-Process` 记录已有 WPS 进程，只对本次新建的实例调用 `Quit()`，或改为只关闭本次打开的文档。

### F-05（P1）`run_conversion_smoke` 和 `run_com_smoke` 没有"输出不得等于输入"的校验

位置：`com_backend.py` 的 `validate_smoke_inputs`、`run_conversion_smoke`、`_run_powershell_com_smoke`。

`run_spreadsheet_calc_smoke` 有这个校验，另外两个没有。

复现（mock `subprocess.run`）：`run_conversion_smoke("writer", p, p, "pdf")` 返回 `ok=True`，传给脚本的 `input_path` 与 `output_path` 相同。在真实环境中，这会让 `ExportAsFixedFormat` 把 PDF 写到原 docx 路径，原文档被覆盖，且没有备份。这些命令是 Agent 可直接调用的 CLI 命令。

建议：把校验放进 `validate_smoke_inputs`，同时拒绝输出路径已存在的情况，或要求显式 `--overwrite`。`run_spreadsheet_calc_smoke` 的 `Remove-Item -Force` 会先删除已有输出文件再保存，SaveAs 失败时原输出就丢了，应改为保存到临时文件再替换。

### F-06（P2）`conversion` 与 `com-smoke` 的超时未处理，且超时后 WPS 进程成为孤儿

位置：`com_backend.py` 143、504 行。

只有 `run_spreadsheet_calc_smoke` 捕获了 `TimeoutExpired`。另外所有超时场景下，`subprocess.run` 只会终止 PowerShell 进程，被它拉起的 WPS 进程继续运行并持有文件。代码没有任何清理或检测逻辑（`taskkill`、`Stop-Process` 在代码中零匹配，与"不自动杀进程"的文档策略一致）。

建议：超时后调用已有的 `audit_wps_processes` 并把结果放入错误详情，让 Agent 知道有残留进程，不自动终止。

### F-07（P2）`state_store.read_json_state` 不处理 JSON 损坏

位置：`state_store.py`。

复现：把 `documents.json` 截断成 `{"documents": {`，`documents` 命令抛出 `JSONDecodeError`，没有 JSON 输出，所有依赖状态的命令都会失败。

写入端是原子的（`mkstemp` 加 `fsync` 加 `os.replace`），所以正常情况下不会发生。但磁盘满、手工编辑或同步软件介入时会触发。建议捕获 `JSONDecodeError`，把坏文件改名为 `.corrupt-<时间戳>`，返回结构化错误 `STATE_CORRUPT`，不要静默回退到默认值，否则会丢失所有文档注册和幂等记录。

### F-08（P2）`stable_document_id` 对路径做 `.lower()`，在区分大小写的文件系统上会产生碰撞

位置：`sessions.py` 的 `stable_document_id`。

复现：`A.docx` 与 `a.docx` 在 Linux 上得到相同的 `document_id`。目标平台是 Windows，所以实际影响小。但 Windows 上开启了目录级大小写敏感（WSL 互操作）时也会触发。建议用 `os.path.normcase`。

### F-09（P2）可重入加锁会阻塞到超时

位置：`mutation_lock.py`。

复现：同一进程内对同一个 key 嵌套两次 `document_mutation_lock`，第二次会等满超时后抛出 `DocumentBusyError`。当前调用链没有触发，因为内部备份用的是 `f"{request_id}:backup"` 这样的不同 key。但这依赖一个隐含约定，将来有人在 `coordinated_mutation` 内再调用同一个 `request_id` 就会死等 30 秒。建议在锁里加线程本地的持有计数，或至少在文档里写明约定。

另外 `.wps-agent/locks/` 每个 request_id 创建一个永不清理的锁文件。批量任务会无限增长。

### F-10（P2）`process_audit` 对 PowerShell 输出不做容错

位置：`process_audit.py` 的 `json.loads(stdout)`。

PowerShell 在 stdout 混入警告或 BOM 时会抛出 `JSONDecodeError`，函数没有捕获，其它同类调用都有处理。

### F-11（P2）能力探测性能

位置：`capabilities.py`。

每个 smoke 或修改命令都会调用 `probe_wps_capabilities()`。在有 pywin32 但 CLSID 解析失败时，会对 9 个 ProgID 逐个启动 PowerShell，每次最多 10 秒。建议缓存探测结果到工作区，带 TTL。

### F-12（P3）CLI 失败时进程退出码恒为 0

位置：`cli.py` 的 `run`。

`backup-document --document-id nope` 返回 `ok=false` 但退出码为 0。`docs/REGRESSION_CI_HANDOFF.md` 把"退出码为 0"写进了验收条件，这是有意的 JSON 信封设计。但普通 shell 脚本和 CI 步骤会把失败当成功。建议增加 `--strict-exit` 之类的开关，默认保持现状。

### F-13（P3）`probe_wps_capabilities` 在非 Windows 上忽略注入的 resolver

位置：`capabilities.py`。`is_windows` 为 false 时，`resolve` 直接返回 `not_windows`，使注入参数在测试里无效，这是上面那个失败用例的根因。注入了 `clsid_resolver` 时应跳过平台判断。

## 已确认安全的点

1. 脚本参数传递：所有 PowerShell 脚本通过 `json.dumps(...)` 放入单引号 here-string。`json.dumps` 默认 `ensure_ascii=True`，且输出单行，因此没有换行，也就不会出现以 `'@` 开头的行，参数无法逃逸 here-string。中文路径也被转义成 `\uXXXX`。
2. `capabilities._resolve_with_powershell` 拼接的 ProgID 来自常量，无注入面。
3. 整个包中没有 `shell=True`、`eval`、`exec`、`pickle`。
4. `html_render.py` 加载的 Playwright 脚本做了较好的隔离：拒绝覆盖已有输出、写临时文件再重命名、只允许 `resource_root` 内的本地文件、网络请求一律拦截、限制单文件和总字节数、输出做魔数校验。
5. `_resolve_backup_file` 用 `resolve()` 加 `relative_to` 防路径穿越，符号链接场景也被覆盖。
6. 备份流程：备份后重新计算源和备份的哈希，对 `DOCUMENT_CHANGED_DURING_BACKUP`、`DOCUMENT_CHANGED_AFTER_BACKUP` 都有检查，COM 修改前后都有源文件身份校验。
7. `atomic_write_json` 使用临时文件、`fsync`、带重试的 `os.replace`。
8. 锁顺序一致：先 request 锁，再 document 锁，再 state 锁，没有发现反向获取路径。

## 小项

- `html_render.py` 超时后只终止 node，Edge 子进程可能残留。
- `html_render_playwright.cjs` 依赖 `require('playwright')`，仓库里没有 `package.json`，也没有在 README 说明如何安装。
- `powershell_executable()` 优先选 `pwsh`。`pwsh` 的 `ConvertFrom-Json` 与 Windows PowerShell 5.1 在日期字符串处理上有差异，建议在文档中固定或在脚本里显式处理。
- `file_identity` 对每次备份读取整个文件多次（源两次，备份一次），大文件有性能代价。

## 修复优先级建议

1. F-01、F-02、F-03、F-05：直接关系到数据安全和结构化契约，改动小，建议先做并补测试。
2. F-04：先在真实 WPS 环境验证，再决定改法。
3. F-07 到 F-11：健壮性改进。
4. F-12、F-13 与测试依赖问题：跟随批次 6 的仓库整理处理。

## 建议补充的测试

- 对 6 个遗漏超时处理的函数各加一个 mock `TimeoutExpired` 的用例，断言返回结构化错误、任务状态为 `failed`。
- `restore-backup`：目标被锁、备份被篡改、复制中途失败三个用例。
- `read_json_state`：损坏文件用例。
- `convert-smoke` 与 `com-smoke`：输出等于输入的拒绝用例。
- 并发：两个进程同时对同一 `request_id` 执行修改，断言只有一个真正执行。

## 修复状态

F-01、F-02、F-03、F-05，以及 F-06 中冒烟命令的超时处理，已在 PR #2 中修复并带测试。F-04 需要先在真实 WPS 验证。F-07 到 F-13 尚未处理。
