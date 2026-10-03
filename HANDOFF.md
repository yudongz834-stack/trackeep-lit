# Trackeep Literature 当前接手状态

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
