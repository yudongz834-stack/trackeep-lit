---
name: trackeep-literature
description: 使用现有 Trackeep 文献管道按期刊、年份、主题或文章检索 PubMed，核重导入 Zotero、复核并获取本机原生全文；与桌面采集台共用核心。
---

使用本机 `D:/trackeep-lit`，先读 `AGENTS.md` 与其中指向的唯一检索规范。不得另外实现检索、去重或下载器。桌面操作台和本技能均使用 `lit.workflow.Workflow.dispatch`。

优先调用 MCP 工具 `literature_dispatch(action,payload)`。未安装 MCP 时在本机使用 `E:/Python/python.exe -m lit.workflow` 的命令行入口（先看 `--help`）；工作目录为 `D:/trackeep-lit`。用户不需要手工写 JSON，由 Agent 形成参数。

1. `plan_natural` 接收 `{"text":"用户原话"}`；或 `plan` 接收明确计划。将检索日期口径、范围和查询呈现给用户；原话有歧义时先缩小歧义，不替用户猜全面历史导入。
2. `search` 接收 `run_id`，核验完整计数与题录身份；存在异常、身份冲突时留待核。
3. 用户已授权范围内，`import` 使用同一 `run_id`，先 `apply:false` 核重再 `apply:true`。由核心绑定检索快照和目标集合，不能另行构造 Zotero 写请求。
4. `review` 为本批每个 PMID 给出 `keep/exclude/pending` 与理由；不确定或缺摘要留 pending。`review_ai` 可使用现有配置的复筛能力，失败不改成排除。`apply_cleanup` 仅在用户授权可恢复清理时使用。
5. `fulltext` 使用 `run_id` 和 `apply:true`，仅处理保留项。核心先检查本机真实文件，再触发 Zotero 原生查找，必要时使用已核官方文件原生附加。重复附件导入本身不会核重，绝不绕过核心护栏。
6. `status` 读回相同批次，报告取得、已存在、排除、待核、缺全文和失败的真实数量；云端附件记录不代表本机全文成功。

本机依赖：Zotero 运行且本地 API 可读、Windows 原生界面可自动化；公共工具棚由项目复用。不得编辑 Zotero 数据库/存储目录、调用内部 JS 假冒外部 API，或改账号/WebDAV/客户端全局配置。控件不能唯一识别时保留失败证据，不盲点坐标。此包提供本机 stdio MCP；远程 ChatGPT 不能据此访问本机，须使用支持本机执行的客户端。
