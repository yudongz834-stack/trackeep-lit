# Trackeep Lit — 项目纪律（CLAUDE.md）

与 [AGENTS.md](./AGENTS.md) 分工：**AGENTS.md = 生产规范流程入口（母法/合同/红线内联/门禁）；
本文件 = 项目纪律与已踩坑固化决策**。开工先读 AGENTS.md + [PROJECT-CONTRACT.md](./PROJECT-CONTRACT.md) + 本文件；
当前状态看 [阶段日志.md](./阶段日志.md) 顶部。

## 定位一句话

PI 的医学文献桌面进料端：选刊 → PubMed 检索 → Zotero 去重预览 → 一键导入。
界面与编排归本仓；检索/导入引擎归 Mecha-Core `zotero-import.ps1`（spawn 只读调用，绝不改）。

## 红线

见 AGENTS.md §1（母法内联）+ §2（本项目五条：不改 Mecha-Core / dry-run 绝不 -Execute /
凭证不外泄 / JSON 契约不动 / PI 不写代码）。

## 修改纪律

- **每改动跑两件套**：`venv\Scripts\python.exe tests\smoke_test.py` + `tests\gui_test.py`，全绿才 commit
- **commit 中文人话**，改完顺手 push（单执行体纪律，EX-01 补偿措施之一）
- 版本语义：`lit/config.py::VERSION`（主.次.修订；v0.1=Slice 1–6b 施工期收口，v0.2=品牌重构+规范落地）
- 改动收尾同步 [阶段日志.md](./阶段日志.md)（刷新「当前活跃状态」+ 追加调整记录）
- 测试内**绝不真跑引擎写路径**：engine spawn 一律 mock；真实 `-Execute` 只归 PI 在界面上点

## 不走回头路（已踩坑固化，别再犯）

1. **PowerShell 写的 JSON 一律 `utf-8-sig` 读**——台账 BOM 曾致 json 解析静默失败、采集窗口永远按首采算（Slice 2 事故，VS-01）。
2. **spawn 引擎必须 `CREATE_NO_WINDOW`**——pythonw 下点「检索」会弹 PowerShell 黑窗（2026-07-13 运行加固，VS-04）。
3. **回填命中 ≥1000 必须告警**——PubMed esearch retmax 静默截断（护栏⑫，VS-03）；自动分月循环属新功能，不顺手加。
4. **Qt 嵌套布局清理走递归 `_clear_layout`**——`_clear_receipt` 曾控件泄漏留残影（6b-1 附修，VS-07）。
5. **导入用检索时锁定的 `_last_params`**，不读当前 UI 态——防切刊/改配置后导入错对象（Slice 3 设计，VS-06）。
6. **导入 = 引擎重新完整跑**（不复用预览 items）——天然满足「导入前必是最新检索+去重」+ 崩溃后重跑自动补齐（护栏⑤⑥⑩）。
7. **`tool="mecha-lit"`（NCBI 标识）与 schema `mecha-lit/import-result@1` 是 wire 契约**——品牌改名不迁移它们（2026-07-18 拍板）。

## 外部依赖（都不在本仓，指针）

| 资源 | 用途 | 归属 |
|---|---|---|
| `Mecha-Core/scripts/zotero-import.ps1` | 检索/导入引擎 | 只读 spawn |
| `Mecha-Core/.mecha/journal-overrides.json` | 单刊例外表 | 本仓可写（原子写） |
| `Mecha-Core/.mecha/strategy.json` | 分类采集策略 | 本仓可写（原子写） |
| `Mecha-Core/.mecha/zotero-import-ledger.json` | 采集台账 | **只读**（引擎写） |
| `Mecha-Memex/00-系统/期刊来源表.md` | 74 刊来源（5 分类） | 只读解析 |
| `~/.config/mecha/secrets/zotero.env` | Zotero 凭证 | 只进请求头 |
| `DEEPSEEK_TOKEN`（Windows 用户环境变量） | 复筛凭证 | 只进请求头 |
