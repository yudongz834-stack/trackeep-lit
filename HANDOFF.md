# Trackeep Literature 当前接手状态

## 当前：确认一次后自动衔接（2026-10-04，本机候选）

现役 `Trackeep Lit.pyw → WorkflowPage → Workflow.dispatch` 与 Agent/MCP 共用 `continue`：确认本批范围、集合与收集标准后，接续题录导入、AI复核、保留项原生优先全文。空标准依已确认范围生成；按刊未指定主题保留刊期内全部文章。待核与全文失败集中展示原因，人工保存保留决定后自动继续，恢复沿用原批次与授权。

标准和集合在首次确认时保存（包括导入前核验失败），旧批次读取既有复核标准，已确认题录不重导，已有人工保留/排除不重判。旧 import、review_ai、search 入口遵守相同锁定，不能通过旧按钮覆盖决定或检索快照。缺摘要（包括复筛重新抓取时缺失）、模型不可用/无可信明确结论、身份冲突保持待核。排除保留题录和理由；默认不清库。

本轮四项独立 high/B1 反例已复测关闭：旧AI更改标准/人工决定、旧核重清复核、重新抓取缺摘要仍排除、导入前失败恢复丢目标。独立终验及源码哈希在 [final-verification.json](日志/continuation-validation/independent/final-verification.json)。连续18、共享流程33、现役GUI26（检索和continue各50轮真实QThread）、原生全文19、smoke88通过；独立对抗70通过。历史GUI首次28/29、单跑29/29；随后独立诊断发现固定夹具目录medium/B2，改为每进程独有目录后主驾29/29、独立双进程各29/29，B2关闭。原首次失败没有竞争进程时间线，原因仍未证明；原日志保留，不抹去初次红灯。远端CI未运行。

增量连续编排采用隔离引擎、模型及全文响应；实际stdio仅合成只读预览。独立席自行选取旧真实失败回执复算恢复，无重导/重判、父键保留，全文执行明确为替身。前序GUI/MCP真实题录及本机PDF证据复用下文，本轮没有新增真实Zotero写入。布局为1040×760、40条合成题录，中文字体/QSS与集中待核14条检查见 [pending-console.png](日志/continuation-validation/pending-console.png)。本地明细与初次失败记录在 `日志/continuation-validation/`。

CI已加入continuation测试、数量检查及日志；INV-12与VS-13/14/15登记连续保护、新增反例和测试夹具隔离。架构机器块重新生成并检查通过，含此前漏列工具与工作树中新工具事实；这不表示本轮施工或验收这些工具。当前原引擎位置由 `lit/config.py` 指向 `D:/trackeep-lit/zotero/import.ps1`，只读调用。临床小样仍为候选；插件未安装或启用，未推送或发布。本轮产出及SHA256清单见 [delivery.json](日志/continuation-validation/delivery.json)。

## 前序：临床设计拆解候选小样（2026-10-04）

本轮交付入口为[研究设计拆解小样](工作区/研究设计拆解小样/README.md)：候选模板v0.1、两张主卡、第三篇模式差异、单独模式记录、两席AI审阅及来源/字段依赖记录。官方全文与两篇补充原件已本地保存；事实与方法审阅分开，迁移限度保留，未发布为通用规范或Agent默认规范。未开发软件、未写Zotero、未装插件、未创建或迁移Obsidian库。

资料小样完成时，“确认题录后自动AI复核并衔接全文”尚未施工验收；后续恢复与增量结论见上方当前段。资料小样本身不构成客户端验收，此前双入口具名实测结果保留在下文。

本轮按入口要求运行架构检查，发现既有机器块漏列tools/fulltext_pilot_jto.py和tools/oa_harvest_jto.py。两文件及地图不是本轮修改，未为资料小样扩展施工；不宣称地图检查通过。

## 前序：双入口本机实测完成，未发布（2026-10-03）

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

## 本轮产出清单

- D:\trackeep-lit\HANDOFF.md
- D:\trackeep-lit\阶段日志.md
- D:\trackeep-lit\工作区\研究设计拆解小样\README.md
- D:\trackeep-lit\工作区\研究设计拆解小样\候选模板v0.1.md
- D:\trackeep-lit\工作区\研究设计拆解小样\可复用模式.md
- D:\trackeep-lit\工作区\研究设计拆解小样\字段依赖.json
- D:\trackeep-lit\工作区\研究设计拆解小样\审阅记录.md
- D:\trackeep-lit\工作区\研究设计拆解小样\来源\BarOn2022全文.pdf
- D:\trackeep-lit\工作区\研究设计拆解小样\来源\Magen2022全文.pdf
- D:\trackeep-lit\工作区\研究设计拆解小样\来源\Magen2022补充.pdf
- D:\trackeep-lit\工作区\研究设计拆解小样\来源\Moreira2022全文.xml
- D:\trackeep-lit\工作区\研究设计拆解小样\来源\Moreira2022补充.pdf
- D:\trackeep-lit\工作区\研究设计拆解小样\来源\Moreira分析人群核对.png
- D:\trackeep-lit\工作区\研究设计拆解小样\来源与复核.md
- D:\trackeep-lit\工作区\研究设计拆解小样\来源回执.json
- D:\trackeep-lit\工作区\研究设计拆解小样\核取来源.py
- D:\trackeep-lit\工作区\研究设计拆解小样\检查回执.json
- D:\trackeep-lit\工作区\研究设计拆解小样\模式差异.md
- D:\trackeep-lit\工作区\研究设计拆解小样\观察队列卡.md
- D:\trackeep-lit\工作区\研究设计拆解小样\随机试验卡.md
