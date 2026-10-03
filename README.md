# Trackeep Literature

现有文献采集台与 Agent 共用一条流程：明确计划 → PubMed 检索核验 → 导入前核重 → Zotero 题录入库 → 相关性、重复与撤稿复核 → 保留项本机全文。

本机 GUI／stdio MCP 已分别走通检索、题录、复核和本机全文，并完成重复执行不新增的实测；独立席直接读取实际PDF核验。项目插件已验证可发现，尚未安装或启用。授权与限制见 [.project/unified-workflow-task.md](.project/unified-workflow-task.md)，验收及清理证据见 [HANDOFF.md](HANDOFF.md)。当前为本机候选交付，未推送或正式发布。

## 打开采集台

双击项目内 `Trackeep Lit.pyw`；也可在本项目执行：

```powershell
& .\venv\Scripts\python.exe .\gui.py
```

存量 `Trackeep Lit.vbs` 暂保留兼容，不再作为新建启动器方案。正式工程为 `D:\trackeep-lit`。

采集台支持既有分类期刊表、额外刊名核验、最近60天、按年月回填、中文主题和明确 PMID。先看生成的计划，再核验检索；读取并选择已有集合，核重后确认存入 Zotero。双击题录可读摘要，逐篇填写保留、排除、待核及理由，也可用已配置的 DeepSeek 复核。保存复核后获取全文；错误和待核保留在批次中，可恢复后重试。

新主窗只调用 `lit.workflow.Workflow.dispatch`。旧 `HarvestPage` 保留历史回归，不是当前导航中的生产导入入口。旧分类策略和筛选前排除规则不自动套入新流程；查询计划与入库后复核要求在当前批次中明确。

## Agent、Skill 和 MCP

项目发现入口为 [.agents/skills/trackeep-literature/SKILL.md](.agents/skills/trackeep-literature/SKILL.md)，唯一技能正文位于 [插件包](plugins/trackeep-literature/skills/trackeep-literature/SKILL.md)。本机插件列表已实测发现 `trackeep-literature@trackeep-local` 1.0.0；状态为未安装、未启用，不代表当前客户端已经加载该技能。

支持本机 stdio MCP 的客户端可连接项目内 `plugins/trackeep-literature/mcp.json` 所描述的服务；可安装包位于 `plugins/trackeep-literature/`。未修改受保护客户端配置、账号或全局安装。不同宿主需各自适配，远程 ChatGPT 不能仅凭本包访问本机。

Agent 优先用 `literature_dispatch(action,payload)`；未接 MCP 时可调用同核心命令：

```powershell
& E:\Python\python.exe -m lit.workflow --help
& E:\Python\python.exe -m lit.workflow list_runs
& E:\Python\python.exe .\plugins\trackeep-literature\server.py
```

最后一条启动 MCP stdio 服务，由客户端管理。Agent 负责形成参数，用户不需要手写 JSON。动作和顺序以技能正文及[唯一检索规范](规则/PubMed检索规范_v1.0_20261003.md)为准。

## 运行边界

- 题录写入复用 `D:\dev\trackeep-scripts\zotero-import.ps1`，不是第二套导入引擎。GUI确认后才写；Agent 写入须在用户已授权范围内，并显式 `apply:true`。
- 同 PMID 跨月记录已见或字段变化；身份冲突待核，不按标题自动合并。缺摘要、缺模型结论不自动排除。
- 全文先只读核已有本机文件，再调用 Zotero 原生查找；官方补充目前覆盖 PMC 主文及 Nature 路径，失败明确记录，不承诺所有出版社可取。原生添加本身不去重，护栏在共享服务。
- 本机 Zotero 9.0.6／WebDAV 用只读本地 API 验收和 Windows 原生界面写入；不直接写数据库或内部存储。Zotero Storage 云上传不作为本机完成条件，WebDAV远端和其他设备另列未验证。
- 排除项保留来源和理由；可恢复清理仅限明确授权对象，不永久删除，不覆盖已有附件、笔记、标签或集合。

## 依赖、记录与验证

GUI 复用已批准 `venv` 中的 PySide6；原生桥与 PDF 解析复用公共棚 `E:\Python`。Zotero 必须运行且本地 API 可用。中文主题计划及 AI 相关性复核使用现有 `DEEPSEEK_TOKEN`；按刊／PMID不需要模型。凭证由现有模块读取，只进请求头。

期刊来源表为 `D:\dev\trackeep-memex\00-系统\期刊来源表.md`，展示不代表身份已通过；正式身份仍由 PubMed／NLM核验。批次与失败回执保存到 `日志/workflow-runs/`，官方补充文件到 `全文/原生补充/`，均属运行数据。

```powershell
& .\venv\Scripts\python.exe tests\workflow_test.py
& .\venv\Scripts\python.exe tests\workflow_gui_test.py
& .\venv\Scripts\python.exe tests\native_fulltext_test.py
& .\venv\Scripts\python.exe tests\smoke_test.py
& .\venv\Scripts\python.exe tests\gui_test.py
& .\venv\Scripts\python.exe tools\check_map.py --check
```

这些离线／离屏测试不替代真实 Zotero 验收。CI 接线见 `.github/workflows/quality-gates.yml`；本地通过不等于远端 CI 已运行。施工定位见[架构图](规则/架构.md)，历史证据见[阶段日志](阶段日志.md)，规则入口见 [AGENTS.md](AGENTS.md)。
