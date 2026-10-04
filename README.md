# Trackeep Literature — 文献线工具之家

Agent 直驱的文献流水线之家。2026-10-04 PI 裁：GUI／MCP 入口退役归档，**Agent 为唯一现役门**；引擎心肝 `lit\` 不动。流程正本＝`E:\Trackeep-Obsidian\00-系统\文献处理SOP.md`；检索规则唯一正文＝[规则\PubMed检索规范_v1.0_20261003.md](规则/PubMed检索规范_v1.0_20261003.md)。

## 现役组成

| 目录 | 是什么 |
|---|---|
| `zotero\` | 流水线脚本＋名册（`zotero\README.md`）：import／harvest-all／shelve／audit／trash／coverage／status／pdf／wipe／journals＋journal-registry.py |
| `lit\` | 共享引擎包：workflow 核心、全文挂接 attach、原生界面桥 native_ui、批次复核——Agent 工具的底座 |
| `tools\` | Agent 侧执行体：fulltext_sweep_inbox（扫箱归档）、oa_harvest（开放版扫描）（pilot 试点件已随清洗归档） |
| `规则\` | 检索规范唯一正文＋架构图 |
| `tests\` | 引擎测试（workflow／fulltext／metadata／pubmed／native 桥） |
| `archives\` | 史料；含 `gui-mcp-20261004`＝退役的 GUI＋MCP 全家（含其测试），要用从 git 请回 |

## 怎么跑（Agent 门）

- **补货／审计／上架**：照 SOP 走 `zotero\` 脚本（`zotero` 口令＝规则库条目 skill-flow-trackeep-zotero）
- **全文六步**：SOP 第 4 步；扫箱归档＝`E:\Python\python.exe tools\fulltext_sweep_inbox.py`
- **登记表**（各刊更新到几月＋落后报警）：`E:\Python\python.exe zotero\journal-registry.py`
- **引擎直调**：`E:\Python\python.exe -m lit.workflow --help`（批数据落 `日志\workflow-runs\`）

## 运行边界（现行）

- 题录写入只走 `zotero\import.ps1`；台账＋现库双锚查重；写入须显式执行（`-Execute`／`apply:true`）
- 全文挂接只走 `lit.fulltext.attach`：验身份、查重防副本、官方协议上传、读回核哈希；单份制（原件验后即删、逐名留删除清单）
- Zotero 9 本地 API 只读核验；不写数据库、不动内部存储；WebDAV 远端另列未验证面
- 凭证只进请求头不回显；`.trackeep\` 为运行状态（台账在忽略名单，journal-overrides.json 在册）

依赖：公共棚 `E:\Python`（PyMuPDF 等）；venv 已随 GUI 退役清洗移除（2026-10-04，全套引擎测试 E:\Python 全绿实证）。Zotero 桌面须运行（本地 API 23119）。
