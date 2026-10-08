# WPS AI Agent CLI

面向 AI Agent 的 Windows 桌面版 WPS CLI。项目处于 Phase 3 本地生产就绪迭代，重点是可验证的 WPS 自动化、MCP 工具面、安全边界、回归证据和本地工作区持续开发。

## 当前阶段

- Phase 0/1/2: 已完成可行性验证、核心 CLI、恢复能力和 MCP server 原型
- 已实现: 环境探测、WPS ProgID 注册检测、结构化响应、任务清单、文档注册、备份/恢复、Writer/Spreadsheet/Presentation 修改命令、MCP adapter/server、回归套件和本地复现脚本
- MCP: legacy `2025-11-25` initialize 生命周期、分页工具发现、ping、参数/schema 校验和配置客户端持久 stdio 审计；审计会校验工具描述/schema，并限制子进程输出，当前工具面 81 项
- 最近验证: 默认测试套件 478 项通过、65 项跳过；P3-299 配置审计定向测试 22 项通过
- 当前实测: WPS Writer、Spreadsheets、Presentation 均已通过 PowerShell COM fallback 完成打开、保存副本和关闭；表格公式计算验证和 DOCX 到 PDF 转换验证已通过
- Phase 1: 已完成 release candidate 审计，详见 `docs/PHASE1_RELEASE_CANDIDATE_REPORT.md`
- 当前 Phase 3: 本地工作区持续开发，不依赖远程 Git 工作流；当前下一任务为限制 MCP 配置 JSON 嵌套深度，可用 `tasks --phase phase3 --status next` 或 `project-status` 查看

## 本地运行

```powershell
python -m wps_ai_agent_cli inspect-env
python -m wps_ai_agent_cli plan
python -m wps_ai_agent_cli project-status
python -m wps_ai_agent_cli local-handoff-summary
python -m wps_ai_agent_cli artifact-retention-summary
python -m wps_ai_agent_cli validation-runbook
python -m wps_ai_agent_cli documentation-freshness
python -m wps_ai_agent_cli tasks --phase phase0
python -m wps_ai_agent_cli tasks --phase phase2
python -m wps_ai_agent_cli tasks --phase phase3
python -m wps_ai_agent_cli com-smoke --component writer --input input.docx --output output.docx
python -m wps_ai_agent_cli calc-smoke --input input.xlsx --output output.xlsx
python -m wps_ai_agent_cli convert-smoke --component writer --input input.docx --output output.pdf --format pdf
python -m wps_ai_agent_cli html-render --input page.html --output page.pdf --format pdf
python -m wps_ai_agent_cli html-editable --input page.html --output page.docx
python -m wps_ai_agent_cli html-roundtrip-plan --input owned-page.html
python -m wps_ai_agent_cli html-controlled-import --input owned-page.html --output controlled.docx
python -m wps_ai_agent_cli html-roundtrip-verify --docx controlled.docx --mapping controlled.docx.wpsmap.json
python -m wps_ai_agent_cli register-document --component writer --path input.docx
python -m wps_ai_agent_cli documents
python -m wps_ai_agent_cli backup-document --document-id doc_xxx --request-id req-001 --dry-run
python -m wps_ai_agent_cli backup-document --document-id doc_xxx --request-id req-001
python -m wps_ai_agent_cli list-backups --document-id doc_xxx
python -m wps_ai_agent_cli restore-backup --document-id doc_xxx --backup-name backup-file.ext --request-id req-restore --dry-run
python -m wps_ai_agent_cli writer-replace --document-id doc_xxx --find "old text" --replace "new text" --dry-run --request-id req-002
python -m wps_ai_agent_cli writer-fill-bookmark --document-id doc_xxx --bookmark-name ClientName --text "Northwind" --dry-run
python -m wps_ai_agent_cli writer-replace --document-id doc_xxx --find "old text" --replace "new text" --request-id req-002
python -m wps_ai_agent_cli writer-replace --document-id doc_xxx --paragraph-index 1 --find "old text" --replace "new text" --request-id req-003
python -m wps_ai_agent_cli validate-document --document-id doc_xxx --contains "expected text"
python -m wps_ai_agent_cli validate-document --document-id doc_xxx --cell D4 --equals 18
python -m wps_ai_agent_cli snapshot-document --document-id doc_xxx
python -m wps_ai_agent_cli writer-structure --document-id doc_xxx --limit 50
python -m wps_ai_agent_cli writer-structure --document-id doc_xxx --section bookmarks --bookmark-name ClientName --include-text --text-limit 200
python -m wps_ai_agent_cli writer-structure-parity --run-wps
python -m wps_ai_agent_cli operation --request req-002
python -m wps_ai_agent_cli operations
python -m wps_ai_agent_cli task-status-create --task-id task_xxx --command batch-report --operation-request-id req-002
python -m wps_ai_agent_cli task-status-update --task-id task_xxx --state running --progress-percent 45
python -m wps_ai_agent_cli task-status --task-id task_xxx
python -m wps_ai_agent_cli task-statuses
python -m wps_ai_agent_cli task-recovery --task-id task_xxx
python -m wps_ai_agent_cli task-recovery-playbooks
python -m wps_ai_agent_cli mcp-tools
python -m wps_ai_agent_cli mcp-tools --category spreadsheet --mutates-document true
python -m wps_ai_agent_cli mcp-catalog-snapshot
python -m wps_ai_agent_cli mcp-catalog-drift
python -m wps_ai_agent_cli mcp-tool-schema --name wps_agent_spreadsheet_write
python -m wps_ai_agent_cli mcp-call --name wps_agent_tasks --arguments-json "{\"phase\":\"phase2\"}"
python -m wps_ai_agent_cli mcp-server --once-json "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\",\"params\":{}}"
python -m wps_ai_agent_cli mcp-smoke --expected-min-tools 81 --tool-name wps_agent_tasks
python -m wps_ai_agent_cli mcp-config-audit --config config/mcp_client_config.example.json --server-name wps-ai-agent-cli --expected-min-tools 81
python -m wps_ai_agent_cli regression-manifest --profile safe
python -m wps_ai_agent_cli regression-run --profile safe
python -m wps_ai_agent_cli regression-evidence
python -m wps_ai_agent_cli regression-history
python -m wps_ai_agent_cli cleanup-plan
python -m wps_ai_agent_cli artifact-retention-summary
python -m wps_ai_agent_cli validation-runbook
python -m wps_ai_agent_cli documentation-freshness
python -m wps_ai_agent_cli cloud-sync-package --output artifacts\cloud-sync\wps-ai-agent-cli-phase3-sync-cli.zip
python -m wps_ai_agent_cli sync-package-inspect
python -m wps_ai_agent_cli sync-package-summary
python -m wps_ai_agent_cli sync-package-manifest --prefix docs --limit 20
python -m wps_ai_agent_cli sync-package-coverage
python -m wps_ai_agent_cli sync-package-readiness
python -m wps_ai_agent_cli scan-dir --path fixtures/phase0
python -m wps_ai_agent_cli batch-report --path fixtures/phase0
python -m wps_ai_agent_cli spreadsheet-read --document-id doc_xxx --sheet Sheet1 --range A1:B2
python -m wps_ai_agent_cli spreadsheet-sheets --document-id doc_xxx
python -m wps_ai_agent_cli spreadsheet-rename-sheet --document-id doc_xxx --old-name Sheet1 --new-name Archive --dry-run
python -m wps_ai_agent_cli spreadsheet-create-sheet --document-id doc_xxx --name Archive --index 2 --dry-run
python -m wps_ai_agent_cli spreadsheet-inspect --document-id doc_xxx --sheet Sheet1 --range A1:F1
python -m wps_ai_agent_cli spreadsheet-write --document-id doc_xxx --sheet Sheet1 --range A1:B2 --values-json "[[1,2],[3,4]]" --request-id req-004
python -m wps_ai_agent_cli spreadsheet-write --document-id doc_xxx --sheet Sheet1 --range A1:B2 --values-json "[[1,2],[3,4]]" --request-id req-004 --task-id task_sheet_write_001
python -m wps_ai_agent_cli spreadsheet-formula-write --document-id doc_xxx --sheet Sheet1 --range C1:C2 --formulas-json "[[\"=A1+B1\"],[\"=A2+B2\"]]" --expected-values-json "[[3],[7]]" --request-id req-005
python -m wps_ai_agent_cli presentation-replace --document-id doc_xxx --find "old title" --replace "new title" --request-id req-006
python -m unittest discover -s tests
```

如果没有安装为包，可以临时设置 `PYTHONPATH`:

```powershell
$env:PYTHONPATH = "src"
python -m wps_ai_agent_cli inspect-env
```

## 设计原则

- CLI 是主入口，MCP adapter 和 MCP server 原型复用同一核心逻辑；Phase 2 交付总结见 `docs/PHASE2_FINAL_HANDOFF_REPORT.md`，Phase 3 生产就绪计划见 `docs/PHASE3_PRODUCTION_READINESS_PLAN.md`，回归清单见 `docs/REGRESSION_MANIFEST.md`。
- 所有命令输出结构化 JSON，便于 Agent 解析。
- 修改类操作必须先有备份、请求 ID、状态查询和验证结果。
- Phase 0 只做可行性验证，不承诺未经实测的兼容性和成功率。
