# Trackeep Literature 当前接手状态

2026-10-03：本轮只交付 PubMed 检索规则及只读预览。正式项目根 `D:\trackeep-lit`，分支 `codex/pubmed-rules`。七刊身份有官方来源；按刊与主题入口可用，筛选默认策略尚未定案。使用入口与规则唯一指针见 [AGENTS.md](AGENTS.md)，过程、实测范围和反证见[阶段日志](阶段日志.md)。

本轮验收：检索解释、数量、身份、异常留证；online first跨月用显式历史报告区分已见/新增/元数据变化。不能把“取齐”当“相关性已验证”或“全刊收齐”。下一阶段仍需 PI 按顺序推进题录字段映射、全文路径、筛选分工。

此前整体管道施工保留在 `codex/literature-pipeline` 与外部引擎隔离分支；未迁入本轮正式入口。其真实单篇误建已撤回到回收站，未永久删除；原全管道还有全文身份校验阻断，不得把本阶段独立通过当成全管道发布。旧 GUI 未接入新预览护栏。

正式根已登记系统仓 wb-ed6181e6；登记 backup=true 不等于已验证离盘备份执行。本轮未改 Zotero 文件、凭证、Claude 登录或设置。登记表/登记日志保留在系统既有正本位置，不为“搬入项目”复制第二份真相源。

本阶段独立复核及追加跨月复核均通过，最终本地验证见 `日志/pubmed-validation/20261003-141829-verification.json`；独立原始证据见同目录 `independent-review.json`。无远端 CI/发布宣称。

## 本轮产出清单

- D:\AI-Projects\_收件箱\journal\workbench-install.jsonl
- D:\AI-Projects\_收件箱\journal\workbenches.count
- D:\AI-Projects\_收件箱\workbenches.json
- D:\trackeep-lit\.github\workflows\quality-gates.yml
- D:\trackeep-lit\.gitignore
- D:\trackeep-lit\.project\pubmed-journals.json
- D:\trackeep-lit\.trackeep-workbench
- D:\trackeep-lit\AGENTS.md
- D:\trackeep-lit\CLAUDE.md
- D:\trackeep-lit\HANDOFF.md
- D:\trackeep-lit\README.md
- D:\trackeep-lit\lit\pubmed.py
- D:\trackeep-lit\tests\pubmed_test.py
- D:\trackeep-lit\tools\check_map.py
- D:\trackeep-lit\工作区\online-first-july.json
- D:\trackeep-lit\工作区\online-first-september.json
- D:\trackeep-lit\工作区\pubmed-corrected-filter.json
- D:\trackeep-lit\工作区\pubmed-legacy-filter.json
- D:\trackeep-lit\工作区\独立复核\close_cross_month.py
- D:\trackeep-lit\工作区\独立复核\cross_month.py
- D:\trackeep-lit\工作区\独立复核\live.py
- D:\trackeep-lit\工作区\独立复核\retest.py
- D:\trackeep-lit\工作区\独立复核\review.py
- D:\trackeep-lit\日志\pubmed-preview\20261003-140119-fd3c12b8.json
- D:\trackeep-lit\日志\pubmed-preview\20261003-140142-bc2905c9.json
- D:\trackeep-lit\日志\pubmed-preview\20261003-140614-79201c36.json
- D:\trackeep-lit\日志\pubmed-preview\20261003-140817-cc309ae6.json
- D:\trackeep-lit\日志\pubmed-preview\20261003-141319-e595ab19.json
- D:\trackeep-lit\日志\pubmed-preview\20261003-141439-fbf29861.json
- D:\trackeep-lit\日志\pubmed-validation\20261003-141829-adversarial_test.log
- D:\trackeep-lit\日志\pubmed-validation\20261003-141829-check_map.log
- D:\trackeep-lit\日志\pubmed-validation\20261003-141829-gui_test.log
- D:\trackeep-lit\日志\pubmed-validation\20261003-141829-pubmed_test.log
- D:\trackeep-lit\日志\pubmed-validation\20261003-141829-smoke_test.log
- D:\trackeep-lit\日志\pubmed-validation\20261003-141829-verification.json
- D:\trackeep-lit\日志\pubmed-validation\adversarial.log
- D:\trackeep-lit\日志\pubmed-validation\gui.log
- D:\trackeep-lit\日志\pubmed-validation\independent-review.json
- D:\trackeep-lit\日志\pubmed-validation\pubmed-tests-final-verified.log
- D:\trackeep-lit\日志\pubmed-validation\pubmed-tests-final.log
- D:\trackeep-lit\日志\pubmed-validation\pubmed-tests.log
- D:\trackeep-lit\日志\pubmed-validation\smoke.log
- D:\trackeep-lit\日志\pubmed-validation\web-search-details.json
- D:\trackeep-lit\规则\PubMed检索规范_v1.0_20261003.md
- D:\trackeep-lit\规则\架构.md
- D:\trackeep-lit\规则\示例\nature-month.json
- D:\trackeep-lit\规则\示例\stem-cell-topic.json
- D:\trackeep-lit\阶段日志.md
