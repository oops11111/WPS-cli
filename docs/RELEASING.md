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

## 对外接口和稳定性

对外接口指调用方会依赖的东西，清单在 `config/public_interface.json`，由代码生成（P12-006）：

- CLI 的全局选项、命令和每个命令的参数（是否必填、可选值）；
- MCP 工具、对应的 CLI 命令、是否修改文档、参数和必填参数；
- 错误码。

改了这些而没更新清单，`tests/test_public_interface.py` 会失败，并列出变化（删除的标为 breaking）。确认是有意的改动后运行 `python scripts/public_interface.py --write`，把清单的变化和代码一起提交；评审时看这个文件的 diff 就知道接口变了什么。

响应 `data` 里的字段是运行时拼出来的，没有可读的结构，不在清单里，按下面的规则处理。

稳定性规则：

| 改动 | 1.0 之前 | 1.0 之后 |
| --- | --- | --- |
| 新增命令、参数（可选）、MCP 工具、错误码、`data` 里的字段 | 次版本 | 次版本 |
| 删除或改名命令、参数、MCP 工具、错误码、`data` 里的字段；参数改为必填；改变字段的类型或含义 | 次版本，`CHANGELOG.md` 写进 Changed 并点名 | 主版本；先在至少一个次版本里标为弃用（`CHANGELOG.md` 的 Deprecated，工具说明里写明替代），再删除 |
| 修复、文档、测试、内部重构，清单不变 | 修订号 | 修订号 |

调用方应当忽略不认识的 `data` 字段，所以新增字段不算破坏。

定 1.0 的检查清单（由你决定，满足下面各条后再考虑）：

1. 全部评测任务在要发布的提交上通过（Phase 12 的 M1）。
2. 至少在一个从没用过本项目的环境里，从 PyPI 安装后通过兼容检查（M2）。
3. 每个版本都同时发布在 GitHub Release 和 PyPI，并在 Windows 上检查过（M3）。
4. 最近一个次版本里，清单没有 breaking 的变化；有的话，先发一个只做弃用标注的次版本。

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
   - 都通过后，用 `gh release create` 建 GitHub Release，附上 wheel 和源码包；
   - 再由 `pypi` 任务把同一组文件上传到 PyPI（Trusted Publishing，见下文“PyPI”）。
6. 在 GitHub 的 Releases 页面和 <https://pypi.org/project/wps-ai-agent-cli/> 确认发布内容，再在 Windows 上检查一次：`python scripts/windows_check/run_windows_check.py wheel --version <版本号> --source pypi`（从 PyPI 安装，并核对文件和 GitHub Release 上的一致）。

标签打错了：在 Release 发布前，删掉远端标签（`git push origin :refs/tags/v<版本号>`）重打即可；Release 已发布的，先在 GitHub 上删除 Release，再删标签。

`tests/test_release.py` 检查 `CHANGELOG.md` 有 `[Unreleased]` 和当前版本号的标题、当前版本那一节有日期且不为空、发布说明的提取和标签检查，发布流程先检查、再跑回归、最后发布的顺序，以及 PyPI 上传用的是 GitHub Release 的同一组文件、不用 token。

标签由你推送，CI 不会自动打标签。

## PyPI

从 0.9.0 起，每个版本也发布到 PyPI，包名 `wps-ai-agent-cli`（P12-004）：

```bash
pip install wps-ai-agent-cli==<版本号>
```

上传用 Trusted Publishing：PyPI 信任本仓库 `release.yml` 的 `pypi` 任务的 OIDC 身份，仓库和 Secrets 里都不存 token。第一次发布前要你登记一次（之后不用再做）：

1. 登录 <https://pypi.org>，打开 Account settings → Publishing → Add a new pending publisher（GitHub）。
2. 填 PyPI Project Name `wps-ai-agent-cli`，Owner `oops11111`，Repository name `WPS-cli`，Workflow name `release.yml`，Environment name `pypi`。
3. 保存。第一次上传成功后，这个 pending publisher 就成为项目的正式 publisher。

GitHub 仓库里的 `pypi` environment 会在第一次运行时自动建立；想限制谁能发布，可以在 Settings → Environments → `pypi` 加上需要审批的人。

上传失败（比如还没登记）时 GitHub Release 不受影响。登记或修好之后，在 Actions 里对同一个标签的运行重跑 `pypi` 任务即可。PyPI 不允许重复上传同一个版本号的文件，所以已经上传过的版本不能改，只能发新版本。

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
