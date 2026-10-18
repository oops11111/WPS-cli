# Phase 12 计划：全量评测、干净环境、发布 0.9.0，为 1.0 做准备

状态：**active**（2026-10-17 确认，六项决定均按默认建议）。本地任务 P12-001、P12-004 到 P12-008 已完成；**M1 已达成**（P12-002 在 `29175b1` 上 33/34，P12-003 修复后在 `a21b050` 上重跑两个任务都通过）；PyPI 发布已略去（M3 不再要求）；新增复杂 HTML 测试，转换缺口已补齐（P12-011、P12-013 已完成）；P12-012 已完成；剩下 P12-009、P12-010 在 Windows 上做，见下文“上机步骤”。

## 目标

Phase 11 之后，PRD v1.2 的核心需求都已实现，已打开文档的 16 个评测任务连续三轮 16/16。但项目评估（2026-10-17）指出，离“可以正式交给用户用”还差三块：

1. **按文件操作的评测太久没重跑。** 34 个评测任务里有 18 个不是已打开文档任务：备份与恢复、按文件写入 Writer/表格/演示、HTML 表格转文档、Writer 转 PDF 等。它们在 Windows 上最后一次跑是 Phase 4、5（当时 3/4 和 6 个通过），之后七个版本的改动都没有在它们身上重测。
2. **只在一个环境里验证过。** 一台 Windows 10、一个 WPS 版本（12.8.2.18913），而且这个账户上已经跑过上百次评测。从来没有在“从没用过本项目的账户”上，从安装开始走一遍。前几个阶段的问题大多出在真实 WPS 和假 COM 行为不同，换一个环境很可能还有没见过的情况。
3. **用户装不方便，接口也没有定稳。** 没有发布到 PyPI，只能从 GitHub Release 下载 wheel。版本还是 0.x，几乎每个阶段都在给结果加字段，没有一份“哪些东西算对外接口”的清单，也就没法判断什么时候可以定 1.0。

Phase 12 做这三件事，最后发布 0.9.0。是否以及何时定 1.0，仍由你决定，不在本阶段的出口标准里。

## 输入：Phase 11 留下的缺口和项目评估

| 缺口 | 出处 |
| --- | --- |
| 18 个按文件操作的评测任务在 Phase 5 之后没在 Windows 上重跑 | `scripts/windows_check/results/` 里的评测都是 `--prefix wps-open-` 或 `--only` |
| 没有在干净的账户或机器上从安装开始验证过 | P5-010（任务目录里唯一的 todo） |
| 兼容矩阵只有一个 WPS 版本 | `docs/COMPATIBILITY_MATRIX.md`，P5-010 |
| 没有发布到 PyPI | `docs/RELEASING.md` |
| 没有对外接口清单和稳定性规则，无法判断 1.0 | 项目评估 |
| 写入后剩 3 次额外核对；撤回的删除没有 Windows 场景；`0x800A01A8`；PRD 未做项（几何、混排格式、准确页码） | `docs/PHASE11_PLAN.md` 开头 |

## 出口标准

每一条都要有可机器读取的记录（测试、结果 JSON 或提交到仓库的结果文档），只按实测结果判定。

| # | 出口标准 | 怎么算达成 |
| --- | --- | --- |
| M1 | 全部评测任务在当前版本上通过 | Windows：一条 `run_windows_check.py eval --repeat 3 --min-passes 2`（不加 `--prefix`，34 个任务全跑）在本阶段的 `main` 上，每个任务至少 2/3，`wrong_tool_calls` 合计 0，`unverified_writes` 0。没通过的任务在本阶段内查清原因并修复后重跑；因环境原因（比如 Claude API 额度）没跑成的，记下原因后只重跑这些任务 |
| M2 | 干净环境从安装开始可用 | Windows：在一个从没运行过本项目的 Windows 账户上（同机新建的本地账户即可，WPS 已安装并是默认程序），只用 GitHub Release 上 0.9.0 的 wheel 安装（原为从 PyPI 安装，PyPI 发布已略去），不克隆仓库，依次通过：`inspect-env`；兼容矩阵的 C1 到 C6；`run_windows_check.py undo` 6/6（这一步需要仓库里的脚本，可以在安装后再克隆，但被测的包必须来自这个 wheel）。结果写进 `docs/COMPATIBILITY_MATRIX.md` 的新一节 |
| M3 | 发布到 PyPI（**已略去**，2026-10-17） | 离线：发布流程在创建 GitHub Release 之后用 Trusted Publishing（OIDC，不存 token）把同一组 wheel 和 sdist 上传到 PyPI；`run_windows_check.py wheel` 增加 `--source pypi`，从 PyPI 安装并核对文件的 SHA-256 与 GitHub Release 上的一致；离线测试。你：在 PyPI 上为 `wps-ai-agent-cli` 登记一次 pending publisher。Windows：`wheel --version 0.9.0 --source pypi` 通过全部条件 |
| M4 | 对外接口清单和稳定性规则 | 离线：从代码生成一份对外接口清单（CLI 命令和参数、MCP 工具和参数、错误码），提交到仓库；`data` 里的字段在运行时才生成，没有可读的结构，不进清单，由稳定性规则约束（P12-006 时调整）；测试在接口变化而清单没更新时失败；`docs/RELEASING.md` 写明 1.0 前后的稳定性规则（哪些变化算破坏性、弃用要提前几个版本、`data` 新增字段算不算破坏）和定 1.0 的检查清单 |
| M5 | 发布 0.9.0 | 按 `docs/RELEASING.md` 发布 `v0.9.0`（只发布 GitHub Release），包含本阶段的改动和 M1 发现的修复；在 Windows 上检查 wheel（`wheel --version 0.9.0`） |

## 已做的决定

2026-10-17 确认，均按默认建议：

| 决定 | 结论 | 依据 |
| --- | --- | --- |
| Phase 12 做什么 | 上面五件事 | 都来自项目评估；全量评测最便宜，也最能说明按文件那一侧的现状 |
| 干净环境用什么 | 同一台机器上新建一个本地 Windows 账户 | 不用新机器就能验证“从没用过本项目”：用户级的 WPS 配置、注册的打开命令、Python 包都从零开始 |
| PyPI 怎么发 | Trusted Publishing（GitHub Actions 的 OIDC），包名 `wps-ai-agent-cli`（2026-10-17 查过 PyPI 上还没有这个名字），在 GitHub Release 之后上传同一组文件 | 不在仓库或 Secrets 里存 token；同一组文件保证 GitHub 和 PyPI 上的 SHA-256 一致 |
| M1 没通过怎么办 | 在本阶段内查清并修复，再只重跑没通过的任务；不降低门槛 | 这 18 个任务就是用来发现按文件那一侧的回退的 |
| 略去 PyPI 发布（2026-10-17 你决定） | M3 不再要求；`pypi` 任务保留但默认关闭（仓库变量 `PUBLISH_TO_PYPI` 为 `true` 时才运行）；M2 改为从 GitHub Release 的 wheel 安装；M5 只发布 GitHub Release；P12-009 改为 `wheel --version 0.9.0` | 发布流程和 `--source pypi` 检查都已做好、有测试，以后要发时只需登记并打开变量 |
| 1.0 | 本阶段只准备清单和规则，不定 1.0 | 定 1.0 意味着承诺接口，按 `docs/RELEASING.md` 由你决定 |
| 版本号 | 0.9.0 | M3、M4 给发布流程和 `wheel` 检查加了新能力；M1 的修复也可能改变行为；按规则升次版本 |

## 任务拆分

| 任务 | 对应标准 | 内容 | 在哪做 |
| --- | --- | --- | --- |
| P12-001 | M1 | 确认 `run_windows_check.py eval` 不加 `--prefix` 时跑全部 34 个任务、准备步骤和清理对按文件的任务也正确（它们不打开 WPS 窗口）；离线检查不需要 WPS 的任务的判定测试都还在、都能过（已完成：不加 `--prefix` 和 `--only` 时跑仓库里全部 34 个任务，有测试；按文件的需要 WPS 的任务，runner 记下开始前的 WPS 进程，结束后结束命令留下的进程并写进清理结果） | 本地 |
| P12-002 | M1 | 在 Windows 上：全部 34 个任务一条命令各跑 3 次（已完成：`29175b1` 上 33/34，见下文“P12-002 结果”） | Windows |
| P12-003 | M1 | 按 P12-002 的结果修复没通过的任务，再只重跑它们（已完成：`restore-backup` 接受指向同一文件的 `backup_name` 和 `backup_path`（#114）；`a21b050` 上重跑 `restore-latest-backup` 2/3、`restore-dry-run` 3/3，见下文“P12-003 结果”） | 本地 + Windows |
| P12-004 | M3 | 发布流程加 PyPI 上传（Trusted Publishing，`id-token: write`，`pypa/gh-action-pypi-publish`）；`docs/RELEASING.md` 写明一次性的 PyPI 登记步骤（已完成：`release.yml` 的 `pypi` 作业在 `release` 之后下载同一组文件，用 `pypa/gh-action-pypi-publish` 和 `pypi` 环境上传；`docs/RELEASING.md` 的“PyPI”一节写了一次性登记步骤和失败后的重跑） | 本地 + 你 |
| P12-005 | M3 | `run_windows_check.py wheel --source pypi`：从 PyPI 安装指定版本，核对 SHA-256 与 GitHub Release 一致；离线测试（已完成：`wheel --source pypi` 用 pip 从 PyPI 下载，SHA-256 与 Release 列出的对比，结果和标题写明来源；离线测试） | 本地 |
| P12-006 | M4 | 生成对外接口清单的脚本和提交的清单文件；接口变化而清单没更新时失败的测试；`docs/RELEASING.md` 的稳定性规则和 1.0 检查清单（已完成：`src/wps_ai_agent_cli/public_interface.py` 从 argparse、MCP 工具定义和源码里的错误码生成 `config/public_interface.json`：85 个命令、85 个工具、200 个错误码；`scripts/public_interface.py` 检查或 `--write` 重写；`tests/test_public_interface.py` 在两者不一致时失败并列出哪些变化算破坏性；`docs/RELEASING.md` 的“对外接口和稳定性”一节） | 本地 |
| P12-007 | M2 | `docs/COMPATIBILITY_MATRIX.md` 加“干净环境”一节的检查项和记录格式；`docs/` 里写干净账户上从安装开始的步骤（已完成：`docs/COMPATIBILITY_MATRIX.md` 的“干净环境”一节；`run_windows_check.py --installed` 让检查和评测 runner 用安装的包，`prereq` 要求它来自 `site-packages`，`RESULTS.md` 写明被测包） | 本地 |
| P12-008 | M5 | 定版本 0.9.0，整理 `CHANGELOG.md`，合并后由你推送 `v0.9.0` 标签（本地部分已完成：版本 0.9.0，`CHANGELOG.md` 的 `[0.9.0]` 一节；合并后由你推送 `v0.9.0`） | 本地 + 你 |
| P12-009 | M5 | 在 Windows 上：`wheel --version 0.9.0`（原为 `--source pypi`，PyPI 发布已略去） | Windows |
| P12-011 | （新增） | 复杂 HTML 测试：一份报告（`report.html`）、一份预算表（`budget.html`）、一份带动画的演示（`launch.html`），放在 `fixtures/html_complex/`；三个评测任务各把一份转换为 docx、xlsx 或 pptx，再用 WPS 转为 PDF；离线判定测试；记下转换丢了什么（已完成，见下文“复杂 HTML 转换”） | 本地 |
| P12-013 | （新增） | 补齐 P12-011 发现的转换缺口（已完成，见下文“补齐缺口”） | 本地 |
| P12-012 | （新增） | 在 Windows 上：`eval --prefix html-complex- --repeat 3 --min-passes 2`；在 WPS 演示里放映 `launch.pptx`，确认动画和切换（已完成：报告、演示 3/3，预算表修复后 3/3，放映确认动画和切换正确，见下文“P12-012 结果”） | Windows |
| P12-010 | M2 | 在 Windows 的新账户上：从 GitHub Release 的 wheel 安装 0.9.0，跑 `inspect-env`、C1 到 C6、`undo` | Windows |

## 建议顺序

1. 本地任务先做：P12-001，P12-004 到 P12-007。
2. 第一次上机做 P12-002；有没通过的就做 P12-003。
3. 做 P12-008，发布 0.9.0（只发 GitHub Release）。
4. 第二次上机做 P12-009 和 P12-010（P12-010 在新账户上做）。

## 上机步骤

### 第一次：P12-002（合并本阶段的本地任务之后，在 `main` 上）

```powershell
git checkout main; git pull
python scripts/windows_check/run_windows_check.py eval --repeat 3 --min-passes 2
```

不加 `--prefix`，34 个任务全跑；中断后用 `eval --resume <结果目录>` 接着跑。把结果目录推到 `cursor/phase12-windows-<提交号>`。有没通过的任务就做 P12-003，修好后只用 `--only` 重跑它们。

### 发布：P12-008

合并后推送 `v0.9.0` 标签，发布流程建 GitHub Release。`pypi` 任务默认关闭，不运行（PyPI 发布已略去）。

### 复杂 HTML：P12-012（可以和第二次一起做）

```powershell
python scripts/windows_check/run_windows_check.py eval --prefix html-complex- --repeat 3 --min-passes 2
```

### 第二次：P12-009 和 P12-010

```powershell
python scripts/windows_check/run_windows_check.py wheel --version 0.9.0
```

P12-010 在新建的本地账户上按 `docs/COMPATIBILITY_MATRIX.md` 的“干净环境”一节做：把 Release 上的 wheel 装进新虚拟环境，用这个虚拟环境的 Python 运行 `run_windows_check.py --installed prereq --skip-claude` 和 `--installed undo`，用它的 `wps-agent` 跑 C1 到 C6，记录按那一节的格式写。

## 复杂 HTML 转换（P12-011）

2026-10-17 你要求：分别生成一个复杂的 HTML 文档、表格和演示动画，转换为 WPS 格式并测试。

### 输入

`fixtures/html_complex/`：

| 文件 | 内容 |
| --- | --- |
| `report.html` | 中文经营报告：`<header>`/`<main>`/`<section>`，h1 到 h3，加粗、斜体、下划线、删除线、上下标、行内样式，外链、邮件和电话链接、一个 `javascript:` 链接，引用块，带嵌套列表的有序列表，带 `<caption>`、`<thead>`/`<tfoot>`、`rowspan` 和 `colspan` 的表格，`<figure>` 里的图片和图注，`<pre>` 代码，`<details>`，内嵌和外链 CSS，脚本 |
| `budget.html` | 预算表：四个表，跨行跨列的表头，整数、小数、负数、空单元格，`=SUM(...)` 公式，前导零工号，千分位、货币、百分比、两种日期写法、科学计数法，带 `<br>` 和链接的单元格，嵌套表格，重名表题，超长且含 `/?[]` 的表题，一张图片 |
| `launch.html` | 发布会演示：六个 `<section>`，`@keyframes` 动画、`transition`、`data-transition` 切换效果、逐条延迟出现的列表，演讲者备注（`<aside class="notes">`），表格，图片，SVG，视频，脚本 |
| `chart.png` | 三份共用的图片 |

### 评测任务

| 任务 | 做什么 | 判定 |
| --- | --- | --- |
| `html-complex-report-to-docx` | `report.html` → `report.docx` → WPS 导出 `report.pdf` | 标题、正文、引用、嵌套列表项、代码、邮件链接的文字都在；表格第 3 行是“华东 … 2,050”；没有脚本和 `javascript:` 链接；`convert_smoke` 用 writer；PDF 至少 1000 字节 |
| `html-complex-budget-to-xlsx` | `budget.html` → `budget.xlsx` → WPS 导出 `budget.pdf` | 四个工作表名（含重名和非法字符的处理）；数值单元格是数字（含小数和负数）；前导零工号仍是文本；`convert_smoke` 用 spreadsheets；PDF |
| `html-complex-launch-to-pptx` | `launch.html` → `launch.pptx` → WPS 导出 `launch.pdf` | 六页的标题和正文文字都在；没有脚本和 SVG 文字；`convert_smoke` 用 presentation；PDF |

三个任务都要 WPS（WPS 打开转换结果并导出 PDF，证明文件能被 WPS 打开）。判定只查现在应当保留的内容，下面列出的缺口不计入判定。

### 转换现状：P12-011 发现的缺口

最初用当时的代码转换三份输入的结果：

| 输入 → 格式 | 保留 | 丢失或不对 | 有没有警告 |
| --- | --- | --- | --- |
| report → docx | 标题层级、段落、引用、列表、表格文字、链接（外链、邮件、电话）、代码块；脚本和 `javascript:` 链接被去掉 | **图片和图注整个丢了**（`<figure>` 里的内容没有输出）；**加粗、斜体、下划线、删除线、上下标都变成普通文字**；**跨行跨列表头错位**（`rowspan`/`colspan` 没有合并单元格，“收入”下的 Q2、Q3 跑到了“区域”下面）；**嵌套列表并进父项**，和源码里的换行、缩进一起成了一段；`<caption>` 和 `<details>` 的文字丢了；段落里保留了源码的换行和缩进 | 图片和格式丢失**没有警告**；caption、details 有警告；CSS 列为 unsupported_css |
| budget → xlsx | 四个工作表和表名、数字、负数、空单元格、前导零 | **公式写成文本**（有意为之，防止执行，有警告）；**跨行跨列表头错位**，没有合并单元格；千分位（`18,500`）、货币、百分比、日期、科学计数法都是文本，不能计算；`<br>` 两边的字粘在一起（“王小明”）；**嵌套表格的文字并进外层单元格**（“差旅嵌套”） | 公式、图片有警告；嵌套表格、错位**没有警告** |
| launch → pptx | 六页的标题和正文（含 h3 和行内文字） | **动画、切换效果全部丢失**；**表格**（第 3 页正文为空）和**图片**没转换；**演讲者备注丢失**；视频、SVG 丢失 | 表格、图片有警告；动画、切换、备注、视频**没有警告** |

### 补齐缺口（P12-013）

2026-10-18 你要求先把这些缺口补齐。现在的转换结果（`tests/test_html_complex.py` 对三份输入逐项检查；三份输出都用 LibreOffice 打开并导出 PDF 核对过版面）：

| 输入 → 格式 | 现在怎样 | 仍然不转换（都有警告） |
| --- | --- | --- |
| report → docx | `<figure>` 里的图片和图注（Caption 样式）；表格 `<caption>`（Caption 样式）；`<details>` 的摘要（加粗）和内容；加粗、斜体、下划线、删除线、上下标、代码字体、高亮，以及行内样式里的粗细、斜体、下划线、删除线和颜色；`rowspan`/`colspan` 合并为一个单元格，`<th>` 加粗；嵌套列表成为第二、三级列表段落；源码空白压缩成一个空格，`<pre>` 保留原有换行和缩进 | 脚本；`javascript:` 链接；CSS 版式（列在 `unsupported_css`） |
| budget → xlsx | `rowspan`/`colspan` 合并单元格，表头居中加粗；千分位、正负号、百分比、货币（¥ $ € £）、科学计数法写成数字并带对应的数字格式；`2021-03-15`、`2025/11/20` 写成日期；前导零仍是文本；`<br>` 成为单元格内换行；单元格里唯一的链接成为超链接；本地图片放在它前面那张表的下方 | 公式仍写成文本，不计算（防止 HTML 带入公式）；嵌套表格按行写进外层单元格 |
| launch → pptx | 幻灯片表格（合并单元格、表头加粗）；本地图片和本地音视频；`<aside class="notes">` 成为演讲者备注；行内格式；嵌套列表层级；`@keyframes` 动画成为进入效果：平移是“飞入”（按方向），缩放是“缩放”，其他是“淡入”，都随幻灯片开始、按 `animation-delay` 延迟，列表项逐段出现；`data-transition`（fade、push、wipe、cover、split、dissolve、zoom、cut）或 section 上的 CSS `transition` 成为切换效果 | SVG；脚本；`:hover`/`:focus` 效果；找不到的视频（`teaser.mp4`）；段落里一部分文字的动画用到整段；未知的切换名 |

LibreOffice 把动画读成 `ooo-entrance-fly-in`、`ooo-entrance-fade-in`、`ooo-entrance-fade-in-and-zoom`，切换读成 fade、push、wipe，延迟 0.2/0.4/0.6 秒都对。WPS 里的效果要在 P12-012 上机时确认：任务会让 WPS 打开转换结果并导出 PDF；动画本身需要你在 WPS 演示里放映 `launch.pptx` 看一眼。

## P12-012 结果（第一轮）

`scripts/windows_check/results/20261018T010801Z-1fdbcfb-eval/`：`main@1fdbcfb`，三个任务各 3 次，用时 8 分钟，Claude API 约 5.4 美元。

| 任务 | 结果 | 说明 |
| --- | --- | --- |
| `html-complex-report-to-docx` | 3/3 | WPS 打开转换出的 docx 并导出 PDF |
| `html-complex-launch-to-pptx` | 3/3 | WPS 打开带动画、切换、表格、图片和备注的 pptx 并导出 PDF |
| `html-complex-budget-to-xlsx` | **0/3** | 三个原因，见下 |

预算表没通过的原因：

1. **WPS 保存时改了工作表名。** 第四张表名里的全角冒号“：”在 WPS 保存后变成了“_”（第 3 次运行写公式之前用原名能读到，之后就是 `SHEET_NOT_FOUND`），`xlsx_sheets` 检查失败。Excel 只禁止半角的 `[ ] : * ? / \`，WPS 还会替换它们的全角形式。修复：转换时把全角形式也换成空格。
2. **`spreadsheet-read` 读日期单元格失败。** 读“入职日期”列时返回 `MCP_TOOL_EXECUTION_FAILED`（`TypeError: Object of type datetime is not JSON serializable`）。这是早就存在的缺陷，以前的评测表格里没有日期；P12-013 把日期写成了真正的日期后才暴露。修复：命令结果和 MCP 回复里的日期、时间一律写成 ISO 8601 文本。
3. **Agent 自作主张把 `=SUM(...)` 文本改成了公式**（`spreadsheet_formula_write`），又因为读日期失败反复检查，三次都用满了 15 轮，其中两次没来得及导出 PDF。修复：公式警告写明“保持文本，除非用户要求可计算的公式”；读日期不再失败，也就不需要反复检查。

报告和演示也有较多不必要的核对调用（报告 15 次、演示 9 次，都在写入之前，比如 `inspect_env`、`register_document`、`snapshot_document`），不影响判定。

`launch.pptx` 在 WPS 演示里放映的动画和切换效果还没有记录，要你看一眼。

第二轮只重跑预算表：

```powershell
python scripts/windows_check/run_windows_check.py eval --only html-complex-budget-to-xlsx --repeat 3 --min-passes 2
```

## P12-012 结果（第二轮）

`scripts/windows_check/results/20261018T045319Z-d126c8c-eval/`：`main@d126c8c`（#116 合并后），只重跑预算表，各 3 次。

- `html-complex-budget-to-xlsx` **3/3**，工具错误 0，`wrong_tool_calls` 0。
- 读日期列不再失败；工作表名在 WPS 保存后不变；Agent 没有再把 `=SUM(...)` 文本改写成公式。
- 多余的核对调用从第一轮的 39 次降到 7 次（`inspect_env`、`register_document`、`spreadsheet_sheets`、`spreadsheet_read`），轮数平均 10.7。

三个复杂 HTML 任务都已通过：报告、演示在 `1fdbcfb` 上 3/3，预算表在 `d126c8c` 上 3/3。

放映确认（2026-10-18，你在 WPS 演示 12.8.2.18913 里放映 `launch.pptx`）：**完全正确**。第 1 页标题飞入、日期淡入，第 2 页三个列表项逐条飞入，各页切换效果都按 HTML 里的设定出现。**P12-012 完成。**

## P12-002 结果

`scripts/windows_check/results/20261017T172608Z-29175b1-eval/`：`main@29175b1`，34 个任务各 3 次，一条命令跑完，约 5 小时 20 分钟。

- **33/34 通过**，这 33 个任务都是 3/3。`wrong_tool_calls` 0，`unverified_writes` 0。
- 18 个按文件的任务里 17 个通过。这是 Phase 5 之后第一次在 Windows 上重跑它们，只有备份恢复这一处有问题。
- **`restore-latest-backup` 1/3，没通过。** 三次运行的第一次 `restore_backup` 都同时传了 `backup_name` 和 `backup_path`，都是 `list_backups` 里同一条备份的两个字段。CLI 里这两个参数是互斥组，argparse 拒绝，返回 `MCP_CLI_ARGUMENTS_REJECTED`。Agent 去掉 `backup_path` 重试后成功，文件都恢复正确，但多用了一次调用，有两次运行因此超过 6 次调用的上限。`restore-dry-run` 三次也都撞上同样的拒绝，只是它没有调用次数检查，所以通过了。
- 修复（P12-003）：两个参数可以一起给，指向同一个文件时照常恢复，指向不同文件时返回 `INVALID_ARGUMENT`，两个都不给时也返回 `INVALID_ARGUMENT`。MCP 工具说明同步修改。对外接口清单不变：两个参数本来就都是可选的。
- 写入后的额外调用 7 次：`spreadsheet_read` 6 次，`snapshot_document` 1 次，和 Phase 11 的水平相当。

P12-003 的重跑：

```powershell
python scripts/windows_check/run_windows_check.py eval --only restore-latest-backup --only restore-dry-run --repeat 3 --min-passes 2
```

## P12-003 结果

`scripts/windows_check/results/20261017T233437Z-a21b050-eval/`：`main@a21b050`，只重跑两个任务，各 3 次。

- `restore-latest-backup` **2/3**，`restore-dry-run` **3/3**。`wrong_tool_calls` 0，`unverified_writes` 0。
- 同时传 `backup_name` 和 `backup_path` 的调用在 6 次运行里出现 4 次（其中 2 次运行各调了两次），全部成功，`MCP_CLI_ARGUMENTS_REJECTED` 不再出现。
- `restore-latest-backup` 第 3 次没通过，原因和修复无关：Agent 先做了 dry run，再正式恢复，又查了两次 `operation`（第一次在恢复前，返回 `OPERATION_NOT_FOUND`）、`snapshot_document` 和 `spreadsheet_read`，共 8 次调用，超过上限 6。文件恢复正确。

| 标准 | 结果 | 证据 |
| --- | --- | --- |
| M1 | 达成 | P12-002：33/34，`wrong_tool_calls` 0，`unverified_writes` 0；没通过的 `restore-latest-backup` 查清原因并修复（#114）后，P12-003 重跑 2/3 |

## 主要风险

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| 34 个任务各 3 次耗时长，跑到一半会话或 API 额度用完 | P12-002 要分几次跑 | `eval --resume` 已经支持接着跑；结果目录和设置不变 |
| 按文件的任务在 Phase 5 之后有回退 | M1 需要修复，阶段变长 | 这正是本阶段要发现的；修复按任务分开提交，只重跑没通过的 |
| 新账户上 WPS 首次启动有欢迎页、登录框或会话恢复对话框 | 自动化被对话框挡住 | 在新账户上先手动打开一次 WPS 关掉首次启动的界面，并记进步骤；runner 已能记录准备失败的原因 |
| 接口清单太细，每个阶段都要改 | 清单形同虚设 | 清单只列对外的东西（命令、参数、工具、错误码），不列内部结构；`data` 里新增字段按规则不算破坏 |
