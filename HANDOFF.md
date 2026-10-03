# Trackeep Literature 当前接手状态

2026-10-03：本轮少量题录导入与入库后复核完成。通过原 PowerShell 引擎真实新建2篇，读回核对 PMID/DOI/标题/NLM/目录；同批重跑已有2、新增0。复核保留2、排除0、待核0，本次无需清理。全文未启动，获取数0；不做插件封装或全刊批量。

最终路径为 D:\trackeep-lit，分支 codex/pubmed-rules。原引擎唯一正身 D:\dev\trackeep-scripts\zotero-import.ps1，分支 codex/metadata-import，原版本由 Git 保存；没有另造 Python 题录导入器。当前写台账由原引擎维护在本项目 .trackeep 下，不改旧台账。旧 GUI 尚未接新护栏。旧隔离全管道原型仍保留，包含未解决的全文身份问题，不是本轮交付入口。

本轮授权与样本边界见 .project/metadata-trial.md；筛选顺序和日期口径只有 规则/PubMed检索规范_v1.0_20261003.md 一份正文。过程与失败史见 阶段日志.md。首次 apply 在只读预演失败，未进入 Execute；失败保留，根因未复现仍未知，后续经只读重查才重试。既往 PMID4 误建仍在回收站，本轮未处理。

证据：日志/metadata-batches/20261003-145432-2b6d0965/report.json（创建），20261003-145542-09f4f670/report.json（同批重跑）；日志/metadata-reviews/review-1141862b.json（复核）。独立离线49例及实际验收分别见 日志/metadata-validation/independent-review.json、independent-live-acceptance.json。最终本地15＋38＋88＋29＋70项及地图检查通过，见 final-verification.json；未运行远端CI、未发布。

真实样本没有旧附件或笔记，因此不能声称已实库验证含附件旧条目保护；这一面目前仅有合成测试。存量元数据更新、持续增量、全文及插件仍是后续阶段。

## 本轮产出清单

- D:\dev\trackeep-scripts\zotero-import.ps1
- D:\trackeep-lit\.github\workflows\quality-gates.yml
- D:\trackeep-lit\.gitignore
- D:\trackeep-lit\.project\metadata-trial.md
- D:\trackeep-lit\.trackeep\zotero-import-ledger.json
- D:\trackeep-lit\AGENTS.md
- D:\trackeep-lit\CLAUDE.md
- D:\trackeep-lit\HANDOFF.md
- D:\trackeep-lit\README.md
- D:\trackeep-lit\lit\batch_review.py
- D:\trackeep-lit\lit\library.py
- D:\trackeep-lit\lit\metadata_batch.py
- D:\trackeep-lit\lit\pubmed.py
- D:\trackeep-lit\lit\zotero.py
- D:\trackeep-lit\tests\metadata_test.py
- D:\trackeep-lit\tests\pubmed_test.py
- D:\trackeep-lit\工作区\升级精确导入.py
- D:\trackeep-lit\工作区\收口题录验证.py
- D:\trackeep-lit\工作区\更新题录交接.py
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
