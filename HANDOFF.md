# Trackeep Literature 当前接手状态

## 桌面交付核对追加（2026-10-03，覆盖前文“未确认同步”）

本机 Zotero9.0.6 API 已读到两篇正确父项与两份附件，PMID/DOI/标题/关联一致；但 API 返回的两个 storage 文件路径均不存在。现有桌面附件同步配置为 WebDAV，本批上传后端为 Zotero Storage，不能把云端附件成功等同于桌面文件可用。尝试系统 open-pdf URI 因未注册失败；改用已有 Zotero 可执行文件 -url 打开指定两份附件后复查仍无文件。没有修改账户/凭证/全局同步配置或注册表，也没有向 storage 目录自行塞文件或改库。尚缺“本机全文文件可用”这一环，具体桌面下载错误未取得，不能声称完全诊断。证据：日志/fulltext-validation/desktop-verification.json、desktop-sync-boundary.json。最初标题句末点差异导致的严格字符串误报亦保留为 desktop-verification-before-normalization.json，改用既有规范化比较并核PMID后确认题录无误。

后续需要确定如何沿用户既有 WebDAV 路径完成这两份文件的交付，或明确授权其他受支持的本地附件写入方式；本次仅核对，不开新功能。用户无需自行执行下面命令，它们用于后续 Agent 接手。

现成 Agent 命令从 D:\trackeep-lit 运行：`E:\Python\python.exe -m lit.pubmed --plan <计划JSON>`；`-m lit.metadata_batch --preview <检索回执> --pmids <明确PMID列表>`（只预演，具名授权后才加 --apply）；`-m lit.batch_review --batch <题录回执> --decisions <决定JSON>`；`-m lit.fulltext_batch --review <复核回执> --downloads <官方下载凭据>`（只预演，具名授权后才加 --apply）。检索计划编写、相关性判断/决定JSON、官方来源定位和下载仍由 Agent 编排。全文入口依赖已有PDF、下载证据及当前既有PyMuPDF；此次下载脚本含已关闭tab，不是通用下载器。工作区/核对本机全文.py 仅只读核对本批两篇。

旧GUI仍走原有桌面流程，未接这些新校验与入库后复核；本批没有做插件或一个自然语言命令包办全部的产品。当前交付是可复用的分段命令和两篇云端实测，桌面文件闭环仍未完成。

2026-10-03：本批两篇已完成核验检索、题录导入、入库后复核及官方全文挂接。检索2 → 题录新增2 → 保留2／排除0／待核0 → 官方PDF2 → 附件新增2；题录和附件分别真实重跑，均新增0。

PMID42420446：父项WD9F8D8E，附件XT8K8X34；PMID42816625：父项IU8CWQD2，附件JBKB7SJZ。两份均37页，云端文件读回SHA256等于原件，父项内容/标签/目录保持不变。官方下载路径：第一篇PMC现行云主文、第二篇Nature官网。原件在全文目录。

正式路径 D:\trackeep-lit，分支 codex/pubmed-rules；原题录引擎唯一正身 D:\dev\trackeep-scripts\zotero-import.ps1，本全文阶段未改动。唯一筛选规范为 规则/PubMed检索规范_v1.0_20261003.md；具名授权为 .project/metadata-trial.md 与 .project/fulltext-task.md。旧GUI未接新护栏，通用自动下载、存量更新、增量追踪及插件未完成。

全文创建：日志/fulltext-batches/20261003-151747-7ee932e7/report.json；重跑：20261003-152244-de96ea4a/report.json。独立40探针及实际验收见 日志/fulltext-validation/independent-review.json、independent-live-acceptance.json。本地6＋15＋38＋88＋29＋70项和地图检查通过，见 final-verification.json；未运行远端CI、未发布。完整前序证据与失败史见阶段日志。

本批无真实排除项及原有附件笔记，相关拦截/旧资料保护仅合成验证。独立实际复核依执行回执核云端读回并独立解析本地PDF，没有确认桌面同步。初次静态下载HTML被拒，旧oa.fcgi未调用。既往PMID4误建仍在回收站，本轮未处理；题录阶段首次只读预演失败根因仍未知。旧隔离全管道原型仍保留，不是交付入口。下载脚本引用已关闭的临时tab，仅作此次运行记录。

## 本轮及前序产出清单

- D:\dev\trackeep-scripts\zotero-import.ps1
- D:\trackeep-lit\.github\workflows\quality-gates.yml
- D:\trackeep-lit\.gitignore
- D:\trackeep-lit\.project\fulltext-task.md
- D:\trackeep-lit\.project\metadata-trial.md
- D:\trackeep-lit\.trackeep\zotero-import-ledger.json
- D:\trackeep-lit\AGENTS.md
- D:\trackeep-lit\CLAUDE.md
- D:\trackeep-lit\HANDOFF.md
- D:\trackeep-lit\README.md
- D:\trackeep-lit\lit\batch_review.py
- D:\trackeep-lit\lit\fulltext.py
- D:\trackeep-lit\lit\fulltext_batch.py
- D:\trackeep-lit\lit\library.py
- D:\trackeep-lit\lit\metadata_batch.py
- D:\trackeep-lit\lit\pubmed.py
- D:\trackeep-lit\lit\zotero.py
- D:\trackeep-lit\tests\fulltext_test.py
- D:\trackeep-lit\tests\metadata_test.py
- D:\trackeep-lit\tests\pubmed_test.py
- D:\trackeep-lit\全文\42420446.pdf
- D:\trackeep-lit\全文\42816625.pdf
- D:\trackeep-lit\工作区\下载本批官方全文.py
- D:\trackeep-lit\工作区\全文来源探测.py
- D:\trackeep-lit\工作区\升级精确导入.py
- D:\trackeep-lit\工作区\收口全文验证.py
- D:\trackeep-lit\工作区\收口题录验证.py
- D:\trackeep-lit\工作区\更新全文交接.py
- D:\trackeep-lit\工作区\更新题录交接.py
- D:\trackeep-lit\工作区\独立复核\fulltext_batch_probe.py
- D:\trackeep-lit\工作区\独立复核\fulltext_boundaries.py
- D:\trackeep-lit\工作区\独立复核\fulltext_candidate.py
- D:\trackeep-lit\工作区\独立复核\fulltext_close.py
- D:\trackeep-lit\工作区\独立复核\fulltext_live_acceptance.py
- D:\trackeep-lit\工作区\独立复核\fulltext_prereview.py
- D:\trackeep-lit\工作区\独立复核\metadata_bridge.py
- D:\trackeep-lit\工作区\独立复核\metadata_close.py
- D:\trackeep-lit\工作区\独立复核\metadata_engine.ps1
- D:\trackeep-lit\工作区\独立复核\metadata_live_acceptance.py
- D:\trackeep-lit\工作区\独立复核\metadata_live_failure.py
- D:\trackeep-lit\工作区\独立复核\metadata_postreview.py
- D:\trackeep-lit\工作区\独立复核\metadata_prereview.py
- D:\trackeep-lit\工作区\落实筛选顺序.py
- D:\trackeep-lit\工作区\诊断题录预演.py
- D:\trackeep-lit\工作区\题录试运行复核决定.json
- D:\trackeep-lit\日志\fulltext-batches\20261003-151203-00e3f8d6\report.json
- D:\trackeep-lit\日志\fulltext-batches\20261003-151747-7ee932e7\report.json
- D:\trackeep-lit\日志\fulltext-batches\20261003-152244-de96ea4a\report.json
- D:\trackeep-lit\日志\fulltext-batches\attachment.lock
- D:\trackeep-lit\日志\fulltext-validation\42420446-first.png
- D:\trackeep-lit\日志\fulltext-validation\42816625-first.png
- D:\trackeep-lit\日志\fulltext-validation\final-adversarial.log
- D:\trackeep-lit\日志\fulltext-validation\final-fulltext.log
- D:\trackeep-lit\日志\fulltext-validation\final-gui.log
- D:\trackeep-lit\日志\fulltext-validation\final-map.log
- D:\trackeep-lit\日志\fulltext-validation\final-metadata.log
- D:\trackeep-lit\日志\fulltext-validation\final-pubmed.log
- D:\trackeep-lit\日志\fulltext-validation\final-smoke.log
- D:\trackeep-lit\日志\fulltext-validation\final-verification.json
- D:\trackeep-lit\日志\fulltext-validation\independent-batch-results.json
- D:\trackeep-lit\日志\fulltext-validation\independent-boundary-results.json
- D:\trackeep-lit\日志\fulltext-validation\independent-candidate-before-fix.json
- D:\trackeep-lit\日志\fulltext-validation\independent-candidate-results.json
- D:\trackeep-lit\日志\fulltext-validation\independent-live-acceptance.json
- D:\trackeep-lit\日志\fulltext-validation\independent-review.json
- D:\trackeep-lit\日志\fulltext-validation\independent-test-plan.json
- D:\trackeep-lit\日志\fulltext-validation\official-downloads.json
- D:\trackeep-lit\日志\fulltext-validation\pmc-metadata.json
- D:\trackeep-lit\日志\fulltext-validation\source-probe.json
- D:\trackeep-lit\日志\fulltext-validation\zotero-status.json
- D:\trackeep-lit\日志\metadata-batches\20261003-144428-615da5bc\expected.json
- D:\trackeep-lit\日志\metadata-batches\20261003-144428-615da5bc\report.json
- D:\trackeep-lit\日志\metadata-batches\20261003-145208-a76b30d3\expected.json
- D:\trackeep-lit\日志\metadata-batches\20261003-145208-a76b30d3\report.json
- D:\trackeep-lit\日志\metadata-batches\20261003-145307-7128c01c\expected.json
- D:\trackeep-lit\日志\metadata-batches\20261003-145307-7128c01c\report.json
- D:\trackeep-lit\日志\metadata-batches\20261003-145432-2b6d0965\expected.json
- D:\trackeep-lit\日志\metadata-batches\20261003-145432-2b6d0965\report.json
- D:\trackeep-lit\日志\metadata-batches\20261003-145542-09f4f670\report.json
- D:\trackeep-lit\日志\metadata-reviews\review-1141862b.json
- D:\trackeep-lit\日志\metadata-validation\adversarial.log
- D:\trackeep-lit\日志\metadata-validation\final-adversarial.log
- D:\trackeep-lit\日志\metadata-validation\final-gui.log
- D:\trackeep-lit\日志\metadata-validation\final-map.log
- D:\trackeep-lit\日志\metadata-validation\final-metadata.log
- D:\trackeep-lit\日志\metadata-validation\final-pubmed.log
- D:\trackeep-lit\日志\metadata-validation\final-smoke.log
- D:\trackeep-lit\日志\metadata-validation\final-verification.json
- D:\trackeep-lit\日志\metadata-validation\gui.log
- D:\trackeep-lit\日志\metadata-validation\independent-bridge-results-before-fix.json
- D:\trackeep-lit\日志\metadata-validation\independent-bridge-results.json
- D:\trackeep-lit\日志\metadata-validation\independent-engine-results-before-fix.json
- D:\trackeep-lit\日志\metadata-validation\independent-engine-results.json
- D:\trackeep-lit\日志\metadata-validation\independent-live-acceptance.json
- D:\trackeep-lit\日志\metadata-validation\independent-live-failure-review.json
- D:\trackeep-lit\日志\metadata-validation\independent-postreview-results-before-fix.json
- D:\trackeep-lit\日志\metadata-validation\independent-postreview-results.json
- D:\trackeep-lit\日志\metadata-validation\independent-prereview.json
- D:\trackeep-lit\日志\metadata-validation\independent-review.json
- D:\trackeep-lit\日志\metadata-validation\live-dryrun-diagnosis.json
- D:\trackeep-lit\日志\metadata-validation\metadata.log
- D:\trackeep-lit\日志\metadata-validation\pubmed.log
- D:\trackeep-lit\日志\metadata-validation\smoke.log
- D:\trackeep-lit\日志\pubmed-preview\20261003-144356-a9213f2b.json
- D:\trackeep-lit\规则\PubMed检索规范_v1.0_20261003.md
- D:\trackeep-lit\规则\架构.md
- D:\trackeep-lit\规则\示例\nature-month.json
- D:\trackeep-lit\规则\示例\stem-cell-topic.json
- D:\trackeep-lit\阶段日志.md
- D:\trackeep-lit\工作区\核对本机全文.py
- D:\trackeep-lit\工作区\补充桌面核对交接.py
- D:\trackeep-lit\日志\fulltext-validation\desktop-before-open.json
- D:\trackeep-lit\日志\fulltext-validation\desktop-sync-boundary.json
- D:\trackeep-lit\日志\fulltext-validation\desktop-verification-before-normalization.json
- D:\trackeep-lit\日志\fulltext-validation\desktop-verification.json
