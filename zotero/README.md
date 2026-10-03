# zotero/ — 文献流水线脚本（2026-10-03 分家归位）

PubMed → Zotero 采集导入线的现役脚本，自仓根 `zotero-*.ps1` 迁入并去前缀。
仓根运行：`pwsh -NoProfile -File zotero\<脚本名>.ps1 …`；脚本间互调用 `$PSScriptRoot` 同夹解析。

## 现役名册

| 脚本 | 用途 | 默认安全档 | 现役引用方 |
|---|---|---|---|
| import.ps1 | PubMed 检索 → 去重（DOI 主/PMID 兜底）→ POST 导 Zotero + 写台账 | dry-run；`-Execute` 才真写 | harvest-all.ps1（循环调用）；人 |
| harvest-all.ps1 | 批量编排：选刊（-Journals/-Category/全部 73 刊）循环跑 import + shelve-by-date | dry-run；`-Apply` 才向子脚本传真写 | 人 |
| shelve-by-date.ps1 | 期刊 collection 内条目按 date 归入 年/月 子集 | dry-run；`-Apply` 才真写（只增不改） | harvest-all.ps1 |
| import-audit.ps1 | 导入后筛查：PubMed publication type 三类分流 + 跨全库查重 | 纯只读 | rulebook 条目 `skill-flow-trackeep-zotero`；人 |
| trash.ps1 | 指定 key 移入回收站（PATCH deleted=1，可逆；永不 DELETE） | 写，但仅显式点名的 key | rulebook 条目 `skill-flow-trackeep-zotero`；人 |
| journals.ps1 | 按期刊来源表建 5 类下的期刊子 collection（幂等） | 跑即写（POST 建 collection，无 dry-run） | 人 |
| coverage.ps1 | 73 刊「期刊表 ↔ Zotero collection ↔ PubMed [TA]」三方一致性自检 | 纯只读 | 人 |
| status.ps1 | 服务器端库计数（顶层/全部/回收站/collection） | 纯只读 | 人 |
| pdf.ps1 | 由 key/DOI/PMID/标题定位 PDF 本地 storage 绝对路径 | 纯只读 | 人 |
| wipe.ps1 | 全库彻底清空（GET→DELETE 循环） | **破坏性·不可逆**；dry-run 默认，`-Execute` 才真删，须 PI 显式指令 | 人（仅清库役） |
| journal-registry.py | 期刊×月份登记表：Zotero 现算各刊更新到几月＋PubMed 近45天对照，揪落后刊；输出 `D:\workbench\期刊登记表-<日期>.md` | 纯只读；`E:\Python\python.exe zotero\journal-registry.py`（本名册唯一 python 件，本地 API 优先/云端自切） | 人（2026-10-04 新增） |

## 归档与删除（`.pre-zotero-cleanup-20261003/`，原名保留，不复活）

- `zotero-init.ps1` — 清空后一次性建 5 类顶层骨架；骨架已立，使命完成。重建库时从归档取用。
- `zotero-pull.ps1` — 旧「Zotero→Memex 映射」v1 管线的拉取器；唯一消费者 analyze 已删，管线退役。
- `zotero-findpdf-sweep.js` — Zotero 桌面内（Actions&Tags 启动规则）批量找 OA PDF 的 JS，不属本仓 pwsh 流水线；需要时从归档取用。

删除：仓根 `zotero-analyze.ps1`（git 历史可寻）——死码四证：输入档 `.trackeep/zotero-pull.json` 不存在；collection key 属 25k 条旧库时代；仓内零消费者；可行性评估使命已完成（PI 2026-10-03 批删）。

## 钥匙与状态档

- **key**：`%USERPROFILE%\.config\trackeep\secrets\zotero.env`（`ZOTERO_API_KEY` / `ZOTERO_USER_ID`）——只进 HTTP 请求头，不回显、不入日志。
- **状态档**：import.ps1 默认落 `<仓上一级>\.trackeep\`（即 `D:\dev\.trackeep\`），可用环境变量 `TRACKEEP_STATE` 换根。台账 `zotero-import-ledger.json` **活在 `D:\trackeep-lit\.trackeep\`**（2026-10-03 深夜翻案：Lit 双入口经 `-StateDir` 落自家目录，双锚去重一直有效）；不带 `-StateDir` 直跑时默认目录无台账，import 打「去重已降级为现库单锚」警告并尾注 `ledger=missing(dedup=live-lib-only)`，属预期不是故障。
