# Trackeep Literature 当前接手状态

## 当前：双入口候选，第二篇原生附加待复验（2026-10-03）

PI已授权把现有采集台与Agent Skill／MCP接成完整流程。验收契约为 [.project/unified-workflow-task.md](.project/unified-workflow-task.md)。此页描述候选代码当前态；真实 GUI／MCP 从输入到本机全文、重跑、限定测试清理和独立终验尚在进行，不能写成已全部通过。

**当前阻点**：第二篇 PMID35357919 已完成真实MCP检索、题录导入与复核；官方Science作者稿已保存、30页、身份及哈希通过，但原生文件框识别失败，尚无本机附件。原因是 Zotero9 公共文件框位于主窗的 UIA 子树，由另一 Zotero 子进程承载。代码已按窗口owner、程序路径及控件唯一性修复，独立12项测试与实际归属函数反例通过；真实重跑待关闭前次遗留的空“选择文件”窗口。桌面工具未将此子进程框暴露为可操作窗口，点击被拒绝；当前不可宣称无需人工介入的第二篇端到端验收通过。

来源接口曾返回429，已停止重复身份转换请求。后续按成功回执中已核官方地址新下载，证据 `日志/unified-live-validation/science-official-file.json` 明确标记新下载；后续只用 `工作区/缓存全文复验.py` 复验该文件并经真实stdio MCP重跑，不重新下载。原文件 `全文/原生补充/35357919-b2d13d10041d4873.pdf`，SHA256 `b2d13d10041d4873479388f69e577b266bf2b31c1daf807bef5dfde6937046ff`，MD5与PMC一致。两个测试父项C6WXAFZ4／5ATM3SFJ目前保留，清理脚本已独审但未执行；不可写成已清理。

正式工程 `D:\trackeep-lit`，原引擎 `D:\dev\trackeep-scripts\zotero-import.ps1`。GUI入口为 `Trackeep Lit.pyw` 或既有venv执行 `gui.py`；现役页面是 `WorkflowPage`，不再从主窗进入旧无新护栏的 `HarvestPage`。

## 已接入的能力与边界

GUI与MCP同调 `Workflow.dispatch`：计划、检索、核重、确认题录写入、复核、仅保留项全文、状态及批次恢复。按刊支持分类来源表、额外刊名核验、年月或最近60天；中文主题经现有DeepSeek生成明确计划，未配置或失败则报错；PMID和期刊计划无模型依赖。

身份、日期、计数与检索解释由PubMed模块统一校验；同PMID跨月比较历史快照，身份冲突待核。模型无结论与缺摘要保持pending。全文先核现有本机PDF，原生查找后才考虑官方PMC／Nature补充并原生附加；回执区分已有、核验完成、缺全文、待核和失败。原生桥实际可靠性仍须本轮真机结果支撑，不能拿离线替身代替。

项目Skill指针、MCP stdio服务、插件声明与启动包装已在项目内。本机插件列表以临时配置实测发现 `trackeep-literature@trackeep-local` 1.0.0，状态为未安装、未启用。**未安装到受保护客户端，未修改账号或全局配置**。未验证的宿主不能声称开箱即用；远程ChatGPT不自动具有本机访问能力。唯一技能正文在插件目录，项目`.agents`仅指针。入口与使用见 [README](README.md)。

## 证据和剩余验收

GUI施工证据：`日志/workflow-gui-validation/`。独立复核亲跑初轮130项针对性测试、smoke88、历史GUI29、对抗70、压力6（含现役页面真实QThread连点／失败恢复50轮）、属性5均通过。后续增量原生UI10、原生全文19、现役GUI23共52项通过；共享PDF校验9项及独立引用章节反例通过。各轮有重叠，不能简单相加当作独立测试总数。离屏1040×760、40长题录截图只证明布局可读。

CI已接共享流程、现役GUI、原生UI及原生全文测试并保存日志；远端未运行。架构机器块以 `tools/check_map.py --write/--check`生成。第一篇GUI实测 PMID34265844 已经计划、检索、集合确认、题录导入、保留复核、原生查找并验证12页本机PDF；父项C6WXAFZ4、附件SGRCQN5E。实际stdio MCP重复导入新增0，重新复核后全文复验仍为同一附件，新增0。证据位于 `日志/unified-live-validation/`；第二篇及清理终验结果在下文补记。

原引擎只作显式集合编号兼容修复，未另造导入引擎：`D:\dev\trackeep-scripts` 本机提交 `7926c73`，看板收尾 `51e4f85`；独立6种匹配反例、真实dry-run及两篇隔离导入通过，未推送。补丁及哈希记录在 `工作区/引擎集合修复/`，完整原文件备份只留本地不入库。

收到协调会话将模型更正为 **GPT-6.1 Sol High** 的通知后，继续完成失败批次GUI恢复、中文计数、官方来源分阶段诊断与有限重试、PDF身份误判修复及本轮实机收尾；没有重新开始已完成工作。此处记录通知后的工作边界，不声称自行验证了运行时模型身份。

## 前序样例是历史证据

两篇原交付 PMID42420446／42816625的父项WD9F8D8E／IU8CWQD2、附件XT8K8X34／JBKB7SJZ保持保护。本轮不得清理它们。先前云Storage与本机WebDAV错配，已用原生定位修复；原件与失败史见阶段日志及 `日志/fulltext-validation/`。

前序原生试验在临时父项QMZ3QGFM／K8ZWW5TD完成查找、存储副本及重复附加验证；原生重复附件确实增加1，护栏读回跳过新增0。两父项及YAW2DYA9／UICJITSE／WH83RRD9已进入回收站，空测试集合75X3U7JU保留。证据 `日志/native-zotero-validation/independent-final-acceptance.json`。本轮真实测试将使用明确隔离对象，处置以新回执为准。WebDAV远端和其他设备始终未单独验收。

## 本轮产出清单（候选；每行一个绝对路径）

```text
D:\trackeep-lit\.project\unified-workflow-task.md
D:\trackeep-lit\README.md
D:\trackeep-lit\HANDOFF.md
D:\trackeep-lit\阶段日志.md
D:\trackeep-lit\规则\架构.md
D:\trackeep-lit\规则\PubMed检索规范_v1.0_20261003.md
D:\trackeep-lit\.github\workflows\quality-gates.yml
D:\trackeep-lit\.gitignore
D:\trackeep-lit\Trackeep Lit.pyw
D:\trackeep-lit\lit\config.py
D:\trackeep-lit\lit\journals.py
D:\trackeep-lit\lit\workflow.py
D:\trackeep-lit\lit\pubmed.py
D:\trackeep-lit\lit\metadata_batch.py
D:\trackeep-lit\lit\batch_review.py
D:\trackeep-lit\lit\library.py
D:\trackeep-lit\lit\deepseek.py
D:\trackeep-lit\lit\native_fulltext.py
D:\trackeep-lit\lit\native_ui.py
D:\trackeep-lit\lit\native_pdf.py
D:\trackeep-lit\lit\mcp_server.py
D:\trackeep-lit\ui\main_window.py
D:\trackeep-lit\ui\pages\workflow_page.py
D:\trackeep-lit\ui\pages\settings_page.py
D:\trackeep-lit\ui\pages\help_page.py
D:\trackeep-lit\tests\workflow_test.py
D:\trackeep-lit\tests\workflow_gui_test.py
D:\trackeep-lit\tests\native_fulltext_test.py
D:\trackeep-lit\tests\native_ui_test.py
D:\trackeep-lit\tests\fulltext_test.py
D:\trackeep-lit\tests\gui_test.py
D:\trackeep-lit\tests\stress_test.py
D:\trackeep-lit\.agents\skills\trackeep-literature\SKILL.md
D:\trackeep-lit\plugins\trackeep-literature\.mcp.json
D:\trackeep-lit\plugins\trackeep-literature\mcp.json
D:\trackeep-lit\plugins\trackeep-literature\plugin.json
D:\trackeep-lit\plugins\trackeep-literature\server.py
D:\trackeep-lit\plugins\trackeep-literature\.claude-plugin\plugin.json
D:\trackeep-lit\plugins\trackeep-literature\.codex-plugin\plugin.json
D:\trackeep-lit\plugins\trackeep-literature\skills\trackeep-literature\SKILL.md
D:\trackeep-lit\日志\workflow-gui-validation\gui_test.py.log
D:\trackeep-lit\日志\workflow-gui-validation\narrow-40-rows.png
D:\trackeep-lit\日志\workflow-gui-validation\smoke_test.py.log
D:\trackeep-lit\日志\workflow-gui-validation\workflow_gui_test.py.log
D:\trackeep-lit\AGENTS.md
D:\trackeep-lit\PROJECT-CONTRACT.md
D:\trackeep-lit\CLAUDE.md
D:\trackeep-lit\lit\fulltext.py
D:\trackeep-lit\.agents\plugins\marketplace.json
D:\trackeep-lit\工作区\验证统一MCP.py
D:\trackeep-lit\工作区\核验双入口本机交付.py
D:\trackeep-lit\工作区\补充已核官方全文.py
D:\trackeep-lit\工作区\缓存全文复验.py
D:\trackeep-lit\工作区\双入口测试收尾.py
D:\trackeep-lit\工作区\引擎集合修复\source.json
D:\trackeep-lit\工作区\引擎集合修复\explicit-collection.patch
D:\trackeep-lit\工作区\引擎集合修复\verify-collection.ps1
```
