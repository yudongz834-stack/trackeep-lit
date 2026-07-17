# Trackeep Lit

医学文献素材库的**桌面进料端**（原名 mecha-lit/机甲文献，2026-07-18 品牌重构）：
选刊 → PubMed 检索 → Zotero 全库去重预览 → 一键导入。
调用 Mecha-Core 的 `zotero-import.ps1` 引擎干活，自身只管界面与编排。

治理入口：[AGENTS.md](./AGENTS.md)（规范流程 + 红线）· [PROJECT-CONTRACT.md](./PROJECT-CONTRACT.md)（合同，S1/R2/C1）·
[CLAUDE.md](./CLAUDE.md)（项目纪律）· [阶段日志.md](./阶段日志.md)（当前状态）。

## 怎么跑

开发调试：

```
venv\Scripts\python.exe gui.py
```

日常使用：双击 `Trackeep Lit.vbs`（静默启动，无黑窗；用 `venv\Scripts\pythonw.exe`）。

起窗自检（3 秒自动退出，退出码 0 = 整窗能拉起）：`TRACKEEP_SELFTEST=1` 环境变量下跑 gui.py。

测试两件套（每改动必跑）：

```
venv\Scripts\python.exe tests\smoke_test.py
venv\Scripts\python.exe tests\gui_test.py
```

## 功能

- **左树单脊柱**：点分类节点 → 该分类采集策略表单（pubtype / PubMed 主题过滤 / DeepSeek 判据，
  写 `strategy.json`）；点期刊叶子 → 操作面板 + 审计页（生效策略摘要 = 分类默认 ⊕ 单刊例外 resolve）。
- **采集最新**：按刊从 PubMed edat 拉近期文献，Zotero 全库去重，审计页预览（新增/去重/疑似分组清单）。
  采集窗口从台账自动算（上次采集 +30 天缓冲，首次 60 天）。
- **回填历史**：按年/月回填某刊历史文献；命中达 1000 上限时橙字告警建议改按月（防静默截断）。
- **AI 复筛（advisory）**：检索后可调 DeepSeek Flash 按分类判据逐篇判「主体是否相关」，
  判决+理由标注在审计页——本版**只显示不拦截**，导入不受影响（6b-2 才门控）。
- **真实导入**：审计页点「导入」→ 确认框 → 写 Zotero + 台账；可逆（Zotero 回收站）；失败可幂等重试；
  collection 不存在时受控建（确认才建，禁静默）。
- **单刊例外**：Editorial/Letter/主题过滤按刊写回 `journal-overrides.json`，与默认不同的刊显示「例外」小标。

检索/导入都在后台线程跑（不卡 UI）；dry-run 预览绝不写 Zotero，真实导入仅点「导入」/「重试」触发。
16 条护栏内建，正式清单见 `.project/invariants.yaml`（11 条系统不变量）。

## 依赖（外部资源，不在本仓库）

| 资源 | 用途 |
|---|---|
| `Mecha-Core/scripts/zotero-import.ps1` | 检索/导入引擎（spawn 调用，本仓库不改它） |
| `Mecha-Core/.mecha/journal-overrides.json` | 单刊例外表（本仓库可写，原子写） |
| `Mecha-Core/.mecha/strategy.json` | 分类采集策略（本仓库可写，原子写） |
| `Mecha-Core/.mecha/zotero-import-ledger.json` | 采集台账（引擎写、本仓库只读算窗口） |
| `~/.config/mecha/secrets/zotero.env` | Zotero API 凭证（受控建 collection 用） |
| `DEEPSEEK_TOKEN`（Windows 用户环境变量） | DeepSeek 复筛凭证 |
| `Mecha-Memex/00-系统/期刊来源表.md` | 74 刊来源（5 分类，只读解析） |

运行时：Python 3.13 + PySide6（版本锁定见 `requirements-lock.txt`）。
PubMed 走 E-utilities（免 key）；Zotero 走官方 API。

## 结构

```
gui.py              入口（QApplication + 主窗 + 自检钩子 TRACKEEP_SELFTEST）
lit/                数据层：引擎桥（engine）/ 期刊表（journals）/ 台账（ledger）/
                    例外表（overrides）/ 策略（strategy）/ Zotero API（zotero）/
                    DeepSeek 复筛（deepseek）/ 配置常量（config）
ui/                 主窗（main_window）/ 样式（style）/ 后台线程（workers）
ui/pages/           采集台（harvest_page）/ 分类策略表单件（category_form）/
                    设置（settings_page）/ 说明（help_page）
tests/              smoke_test（离线逻辑链路）+ gui_test（离屏界面回归）
.project/           规范五件套（policy/manifest/invariants/vulnerable-scenarios/exceptions）
.github/workflows/  CI 四门禁（governance/tests/secret-scan/evidence）
archives/           Slice 施工期历史文档（SPEC/SLICE*/brief 等，只读追溯）
Trackeep Lit.vbs    双击启动器（pythonw，无黑窗）
Trackeep Lit.spec   PyInstaller 打包规格（打包收尾待排，BL-03）
```
