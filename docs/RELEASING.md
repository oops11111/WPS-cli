# 版本与发布

Phase 4 出口标准 E6 的一部分（P4-012）。

## 版本号规则

版本号格式为 `主.次.修订`，含义参照语义化版本。1.0.0 之前：

| 改动 | 升哪一位 | 例子 |
| --- | --- | --- |
| 破坏已有调用方的改动 | 次版本 | 删除或改名 CLI 命令、参数、MCP 工具、错误码，删除或改变响应里的字段，改变默认行为 |
| 新功能，已有调用方不受影响 | 次版本 | 新命令、新的可选参数、新的 MCP 工具、新的回归档 |
| 修复、文档、测试、内部重构 | 修订号 | 修正错误文案、修 bug 而不改接口 |

升到 1.0.0 表示 CLI 和 MCP 接口进入稳定期，由你决定，不随某个阶段自动发生。1.0.0 之后，破坏性改动升主版本。

版本号只写在 `src/wps_ai_agent_cli/__init__.py` 的 `__version__` 里。`pyproject.toml` 从那里读取，MCP `initialize` 返回的 `serverInfo.version` 也是它。

## 变更记录

每个改变用户可见行为的 PR 都在 `CHANGELOG.md` 的 `[Unreleased]` 下加一行，分 Added、Changed、Fixed、Removed。只改测试、文档或内部结构的 PR 可以不写。

## 发布步骤

1. 按上面的规则定版本号，改 `__version__`。
2. 把 `CHANGELOG.md` 的 `[Unreleased]` 改成 `[<版本号>] - <日期>`，上面再加一个空的 `[Unreleased]`。
3. 提交、合并到 `main`，等 CI 通过。
4. 在合并提交上打标签 `v<版本号>` 并推送。
5. 从该提交的 CI 运行里下载 `dist` 产物（wheel 和源码包）。

`tests/test_release.py` 检查 `CHANGELOG.md` 有 `[Unreleased]` 和当前版本号的标题，并检查 MCP 返回的版本号与包版本一致。

目前不发布到 PyPI，也不自动打标签。

## CI 构建

CI 的 `build` 任务用 `python -m build` 生成 wheel 和源码包，在新的虚拟环境里安装 wheel，运行 `wps-agent inspect-env`、`wps-agent tasks` 和一次 MCP `initialize`，然后把 `dist/` 作为 `dist` 产物保存 30 天。

## wheel 里有什么

wheel 包含 CLI（`wps-agent`）、MCP 服务器、任务目录和 HTML 渲染脚本。不包含以下仓库内容，需要时要用源码目录安装（`pip install -e .`）：

- `config/`：回归清单、MCP 配置样例和项目计划。`regression-run` 用的是 `config/regression_manifest.json`，只装 wheel 时会报 `REGRESSION_MANIFEST_NOT_FOUND`。
- `fixtures/`：回归档和评测用的样例文件。
- `scripts/`：Agent 评测和 Windows 实测脚本。

所以 P4-013 在干净机器上按 README 从源码目录安装，再跑 safe 档回归。
