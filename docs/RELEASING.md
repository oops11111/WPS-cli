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
4. 在 `main` 的合并提交上打标签并推送：

   ```bash
   git checkout main && git pull
   git tag v<版本号>
   git push origin v<版本号>
   ```

5. 推送标签会触发 `.github/workflows/release.yml`：
   - 用 `scripts/release_notes.py` 检查标签等于 `v<__version__>`，并取出 `CHANGELOG.md` 里这个版本的一节作为发布说明；标签不对、这一节没有日期或是空的，就停下，不发布；
   - 构建 wheel 和源码包，在新的虚拟环境里只装 wheel，在仓库以外跑 `inspect-env` 和 safe 档回归；
   - 都通过后，用 `gh release create` 建 GitHub Release，附上 wheel 和源码包。
6. 在 GitHub 的 Releases 页面确认发布内容，再按 P5-009 在 Windows 上只装这个 wheel 检查一次。

标签打错了：在 Release 发布前，删掉远端标签（`git push origin :refs/tags/v<版本号>`）重打即可；Release 已发布的，先在 GitHub 上删除 Release，再删标签。

`tests/test_release.py` 检查 `CHANGELOG.md` 有 `[Unreleased]` 和当前版本号的标题、当前版本那一节有日期且不为空、发布说明的提取和标签检查，以及发布流程先检查、再跑回归、最后发布的顺序。

目前不发布到 PyPI。标签由你推送，CI 不会自动打标签。

## CI 构建

CI 的 `build` 任务用 `python -m build` 生成 wheel 和源码包，在新的虚拟环境里安装 wheel，运行 `wps-agent inspect-env`、`wps-agent tasks` 和一次 MCP `initialize`，再在仓库以外的目录里跑 safe 档回归（要求全部通过，且清单来自安装的包），然后把 `dist/` 作为 `dist` 产物保存 30 天。

## wheel 里有什么

wheel 包含 CLI（`wps-agent`）、MCP 服务器、任务目录、HTML 渲染脚本，以及 safe 档回归要用的三个配置文件的副本（`wps_ai_agent_cli/resources/`）：

| 仓库里的文件 | 包里的副本 |
| --- | --- |
| `config/regression_manifest.json` | `resources/regression_manifest.json` |
| `config/mcp_catalog_guard.json` | `resources/mcp_catalog_guard.json` |
| `config/mcp_client_config.regression.template.json` | `resources/mcp_client_config.regression.template.json` |

命令收到这几个默认路径时，依次使用：当前目录下的这个文件、所在源码目录里的文件、包里的副本。所以只装 wheel 时，在任意目录运行 `wps-agent regression-run --profile safe` 都能通过（P5-007）。改了 `config/` 里的这三个文件，要同样复制到 `src/wps_ai_agent_cli/resources/`，`tests/test_packaged_resources.py` 会检查两边是否一致。

仍然不包含以下仓库内容，需要时用源码目录安装（`pip install -e .`）：

- `fixtures/`：wps 档、compat 档回归和评测用的样例文件。只装 wheel 时这两档的场景找不到输入文件。
- `scripts/`：Agent 评测和 Windows 实测脚本。
- `config/` 里其余的文件：MCP 配置样例、项目计划等。
