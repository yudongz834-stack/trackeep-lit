---
name: trackeep-literature
description: 使用现有 Trackeep 文献管道按期刊、年份、主题或文章检索 PubMed，核重导入 Zotero、复核并获取本机原生全文；与桌面采集台共用核心。
---

使用本机 `D:/trackeep-lit`，先读 `AGENTS.md` 与其中指向的唯一检索规范。不得另外实现检索、去重或下载器。桌面操作台和本技能均使用 `lit.workflow.Workflow.dispatch`。

优先调用 MCP 工具 `literature_dispatch(action,payload)`。未安装 MCP 时在本机使用 `E:/Python/python.exe -m lit.workflow` 的命令行入口（先看 `--help`）；工作目录为 `D:/trackeep-lit`。用户不需要手工写 JSON，由 Agent 形成参数。

1. `plan_natural` 接收 `{"text":"用户原话"}`；或 `plan` 接收明确计划。将检索日期口径、范围和查询呈现给用户；原话有歧义时先缩小歧义，不替用户猜全面历史导入。
2. `search` 接收 `run_id`，核验完整计数与题录身份；存在异常、身份冲突时留待核。
3. 用 `collections` 读取已有集合，按用户范围选择 `collection_key`；先 `import` 携带同一 `run_id`、集合和 `apply:false` 核重。用户确认或已明确授权后，默认调用 `continue`、`apply:true`，一次接续题录写入、AI复核与保留项全文；不要求用户手写参数或逐步触发。首次计划可带 `criteria`；空标准按已确认检索范围生成，按刊未限定主题则保留刊期内全部文章。确认后标准、目标集合和检索批次锁定，不能另行构造 Zotero 写请求或静默建集合。
4. 读 `pending_queue` 集中报告原因；不确定、缺摘要、模型不可用或无可信判决、身份冲突均留 pending。人工核实后 `review` 给出 `keep/exclude/pending` 与理由；已授权连续流程会自动继续保留项全文。旧 `review_ai` 也须遵守锁定标准且只处理未决项，不改写人工决定。排除保留题录和理由，`apply_cleanup` 仅在另有用户授权可恢复清理时使用。
5. 失败或中断后继续同一 `run_id` 的 `continue`、`apply:true`；不重复导入已确认题录或重判已确认决定。`fulltext` 仍可单独调用，仅处理保留项。核心先检查本机真实文件，再触发 Zotero 原生查找，必要时使用已核官方文件原生附加。重复附件导入本身不会核重，绝不绕过核心护栏。`continue` 的 `apply:false` 仅预览，不调用模型或真实写入。
6. `status` 读回相同批次，报告取得、已存在、排除、待核、缺全文和失败的真实数量；云端附件记录不代表本机全文成功。

本机依赖：Zotero 运行且本地 API 可读、Windows 原生界面可自动化；公共工具棚由项目复用。不得编辑 Zotero 数据库/存储目录、调用内部 JS 假冒外部 API，或改账号/WebDAV/客户端全局配置。控件不能唯一识别时保留失败证据，不盲点坐标。此包提供本机 stdio MCP；远程 ChatGPT 不能据此访问本机，须使用支持本机执行的客户端。
