# Trackeep Literature 当前接手状态

## 当前：双入口本机实测完成，未发布（2026-10-03）

PI已授权把现有采集台与Agent Skill／MCP接成完整流程。验收契约为 [.project/unified-workflow-task.md](.project/unified-workflow-task.md)。GUI和真实stdio MCP各自完成检索、题录、复核到本机全文；同批次在采集台与Agent显示一致，重复执行新增0。独立席直接读取PDF、正文身份、父子关系与哈希确认通过。项目插件可发现但未安装／启用；不同客户端、WebDAV远端、其他设备不在本轮实测结论内。

**第二篇实机结果**：PMID35357919经原生“添加附件→附加文件”存储副本路线交付，父5ATM3SFJ、唯一子X33B248I，30页。`20261003-172501-916134-fulltext.json` 记录自动挂接及本机验证，`172515-860525-fulltext.json` 重跑返回已有全文、同键同哈希、0新增。独立席另起stdio status核对完成。采集台刷新同批次也显示指定PMID和全文已核验，见 `gui-shared-complete.png`。

修复历史保留：Zotero9文件框由另一子进程承载，现按原生owner、程序路径和唯一控件识别；UIA设置焦点不足以激活主窗，现显式请求置前、最多1秒等严格同HWND，拒绝时零点击。最新独立原生UI14项及系统拒绝激活反例通过。旧版失败遗留的空框曾由PI点取消一次；之后最终成功运行由程序完成挂接，PI没有手动选择PDF或添加附件。不得抹掉这次调试人工介入，也不得把它误写成最终挂接需要手工完成。

来源接口曾返回429，已停止重复身份转换请求。后续按成功回执中已核官方地址新下载，证据 `日志/unified-live-validation/science-official-file.json` 明确标记新下载；最终挂接使用已保存文件的缓存复验，没有重新下载。原文件 `全文/原生补充/35357919-b2d13d10041d4873.pdf`，SHA256 `b2d13d10041d4873479388f69e577b266bf2b31c1daf807bef5dfde6937046ff`，MD5与PMC一致。

**测试收尾**：经独立核对范围后，SGRCQN5E、C6WXAFZ4、X33B248I、5ATM3SFJ四键已用版本条件PATCH可恢复入回收站，逐项云端读回deleted=1，证据 `cleanup.json`；保留测试集合75X3U7JU。`local-delivery.json`和批次完成状态是清理前验收快照，不能当成清理后的现存测试文件承诺。两篇原交付文献保持保护。

独立终验 `independent-final-acceptance.json` 判决PASS、无未关闭发现：四键本机／云端均已删除标记，测试集合两端有效条目均0，无同步待决；原WD9F8D8E／IU8CWQD2的父项、子项数据及实际PDF哈希与保护基线一致。独立席只读、未参与真实写入。

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
