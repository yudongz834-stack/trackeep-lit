# Trackeep Literature 当前接手状态

## 最新验证：Zotero 两条原生全文路径（2026-10-03）

用户要求“验一下，它的自带功能很重要”。现用 Zotero9.0.6、原有WebDAV设置，Agent亲自完成原生UI操作；没有升级、装插件、改同步设置或直接写storage/数据库。唯一可复用流程写回《PubMed检索规范》§5.1，优先原生，保留写前核重及本机读回。

| 路径 | 输入与父项 | 实测结果 |
|---|---|---|
| 查找全文 | PMID42420446临时副本QMZ3QGFM，起始0附件 | 原生下载Nature PDF，YAW2DYA9，imported_url，37页；标题/DOI/哈希通过 |
| 存储副本 | PMID42816625临时副本K8ZWW5TD；全文\\42816625.pdf | 原生附加文件生成UICJITSE，imported_file，37页；身份/哈希通过 |
| 原生重复附加 | 同父项、同文件再次执行 | 新增WH83RRD9，附件1→2、同哈希；原生不去重 |
| Agent写前护栏 | 两父项实际文件再次只读验证 | 有合格PDF则跳过；新增0。不是原生幂等 |

查找完成后右键入口消失，没有实际执行第二次查找，不能宣称已测重复下载去重。当前9.0.6没有受支持的本地外部写API；本次是原生GUI成功+只读API验收，尚非通用自动命令。只证明两个样本；未核WebDAV远端或其他设备。

SHA256：42420446 = c0c10e691579ee9cdc47fb61dc0ff52bca58a96a91b797aa2b4fb0b3f4121266；42816625 = a346ec1af676aafcb59867d0e3673b8036bbeaee911206020babcab98ef88d9f。独立复核保护基线确认原父项WD9F8D8E/IU8CWQD2、原附件XT8K8X34/JBKB7SJZ及本地文件保持不变。

测试清理仅5个精确键：QMZ3QGFM、YAW2DYA9、K8ZWW5TD、UICJITSE、WH83RRD9，官方API PATCH deleted=1逐项读回；禁止永久删除。保留空测试目录75X3U7JU。临时准备与清理脚本仅作本次操作记录，带禁止盲重跑保护，不是常规入口。

证据目录：D:\trackeep-lit\日志\native-zotero-validation。native-actions.json记录GUI操作；独立首次、重复、清理证据与guarded-repeat.json分别证明不同结论。未将UI截图另存归档。基础回归88/88、GUI29/29通过；无远端CI、无push或发布。


## 最新交付：两篇本机全文已可用（2026-10-03）

桌面缺文件问题已通过 Zotero 自带“找不到文件→检索/定位文件”流程解决。Agent 逐一选择已校验官方PDF，由 Zotero 自己补回原附件存储：PMID42420446／XT8K8X34、PMID42816625／JBKB7SJZ。两份均在本机阅读器实际打开、显示37页；本地API给出的文件真实存在，SHA256与官方原件一致。没有新建附件、直接写storage/数据库、升级软件或改变现有WebDAV设置，用户无需手动搬文件。证据：日志/fulltext-validation/desktop-verification.json、desktop-relink-actions.json；独立本机验收见 independent-desktop-acceptance.json。

此前错误是只验了Zotero Storage云端而未核用户WebDAV桌面交付，失败记录保留。现已完成本批本机可读交付；WebDAV远端文件没有另行下载核验，不能将UI同步错误标志消失称为远端验收。旧GUI仍未接新Agent护栏，命令复用范围与需Agent编排的环节见下方历史核对中的入口说明；桌面定位操作也是本次Agent执行原生UI，尚非一个通用自动管道。

## 桌面交付核对历史（当时文件未到本机；已由上方定位修复关闭）

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
- D:\trackeep-lit\工作区\收口本机交付.py
- D:\trackeep-lit\工作区\独立复核\fulltext_desktop_acceptance.py
- D:\trackeep-lit\日志\fulltext-validation\desktop-before-relink.json
- D:\trackeep-lit\日志\fulltext-validation\desktop-relink-actions.json
- D:\trackeep-lit\日志\fulltext-validation\independent-desktop-acceptance.json

## 本轮原生验证文件清单（完整绝对路径）

独立终验：本地5项均deleted=1，原件未变；云端仅依据执行方逐项回执，独立审查未访问云端。一次性测试脚本不作为产品命令，不使用python -O运行。

- D:\trackeep-lit\.gitignore
- D:\trackeep-lit\工作区\独立复核\native_cleanup_scope.py
- D:\trackeep-lit\工作区\独立复核\native_final_acceptance.py
- D:\trackeep-lit\工作区\独立复核\native_find_verify.py
- D:\trackeep-lit\工作区\独立复核\native_stored_verify.py
- D:\trackeep-lit\工作区\独立复核\native_zotero_snapshot.py
- D:\trackeep-lit\工作区\原生全文测试收尾.py
- D:\trackeep-lit\工作区\原生全文测试准备.py
- D:\trackeep-lit\规则\PubMed检索规范_v1.0_20261003.md
- D:\trackeep-lit\阶段日志.md
- D:\trackeep-lit\日志\native-zotero-validation\cleanup.json
- D:\trackeep-lit\日志\native-zotero-validation\fixture.json
- D:\trackeep-lit\日志\native-zotero-validation\guarded-repeat.json
- D:\trackeep-lit\日志\native-zotero-validation\gui.txt
- D:\trackeep-lit\日志\native-zotero-validation\independent-after-cleanup.json
- D:\trackeep-lit\日志\native-zotero-validation\independent-cleanup-scope.json
- D:\trackeep-lit\日志\native-zotero-validation\independent-copies-before.json
- D:\trackeep-lit\日志\native-zotero-validation\independent-final-acceptance.json
- D:\trackeep-lit\日志\native-zotero-validation\independent-find-first-verification.json
- D:\trackeep-lit\日志\native-zotero-validation\independent-find-first.json
- D:\trackeep-lit\日志\native-zotero-validation\independent-plan.json
- D:\trackeep-lit\日志\native-zotero-validation\independent-protected-baseline.json
- D:\trackeep-lit\日志\native-zotero-validation\independent-stored-first-verification.json
- D:\trackeep-lit\日志\native-zotero-validation\independent-stored-first.json
- D:\trackeep-lit\日志\native-zotero-validation\independent-stored-repeat.json
- D:\trackeep-lit\日志\native-zotero-validation\native-actions.json
- D:\trackeep-lit\日志\native-zotero-validation\smoke.txt
- D:\trackeep-lit\HANDOFF.md
- D:\trackeep-lit\README.md
