# MCP client smoke

- Config: `C:\Users\admin\AppData\Roaming\Claude\claude_desktop_config.json`, server `wps-agent`
- Server: {'name': 'wps-ai-agent-cli', 'version': '0.11.3'}; protocol 2025-11-25 (asked for 2025-11-25)
- Server environment: MCP SDK default variables plus the entry's env (NODE_PATH, WPS_AGENT_WORKSPACE)
- Python running this script: 3.12.15
- Written by `scripts/windows_check/mcp_client_smoke.py`; nothing in this file was typed by hand.

**Passed.**

| Step | Result | Detail |
| --- | --- | --- |
| read the client config | ok | "C:\\Users\\admin\\AppData\\Local\\wps-agent\\venv\\Scripts\\wps-agent.exe" |
| the entry sets WPS_AGENT_WORKSPACE | ok | "C:\\Users\\admin\\AppData\\Local\\wps-agent-data" |
| initialize | ok | {"name": "wps-ai-agent-cli", "version": "0.11.3", "protocolVersion": "2025-11-25"} |
| tools/list | ok | "87 tools" |
| register the workbook | ok | "doc_ff68bb1cec9c35b8" |
| read sales_gbk!A1:F3 | ok | [["地区", "门店编号", "销量", "增长率", "销售额", "备注"], ["华东", "007", 1200, 0.125, 1234.5, "旗舰店"], ["华南", "008", 3.5, -0.03, 99, "含,逗号"]] |
| write sales_gbk!F2 | ok |  |
| read the written cell back | ok | [["wps-agent MCP smoke"]] |
| the write left a backup | ok | 1 |
| the backup is under WPS_AGENT_WORKSPACE | ok | ".wps-agent\\backups\\doc_ff68bb1cec9c35b8\\book.20261109T163733340181Z.xlsx" |
| nothing was written where the server was started | ok |  |

Removed this run's backup folder `C:\Users\admin\AppData\Local\wps-agent-data\.wps-agent\backups\doc_ff68bb1cec9c35b8`.
