# 机甲文献（Mecha-Lit）

医学文献素材库的**桌面进料端**：选刊 → PubMed 检索 → Zotero 全库去重预览 → 一键导入。
是 Mecha 机甲工作区的文献采集 GUI，调用 Mecha-Core 的 `zotero-import.ps1` 引擎干活，自身只管界面与编排。

## 怎么跑

开发调试：

```
venv\Scripts\python.exe gui.py
```

日常使用：双击 `机甲文献.vbs`（静默启动，无黑窗；用 `venv\Scripts\pythonw.exe`）。

## 功能

- **采集最新**：按刊从 PubMed edat 拉近期文献，Zotero 全库去重，审计页预览（新增/去重/疑似分组清单）。采集窗口从台账自动算（上次采集 +30 天缓冲）。
- **回填历史**：按年/月回填某刊历史文献（选「全年」或具体月）；命中达 1000 上限时提示改按月（避免截断）。
- **配置例外表**：Editorial/Letter/主题过滤偏好按刊写回 `journal-overrides.json`；与默认不同的刊显示「例外」小标。
- **真实导入**：审计页点「导入」→ 确认 → 写 Zotero + 台账；可逆（Zotero 回收站）；失败可幂等重试。

## 依赖（外部资源，不在本仓库）

| 资源 | 用途 |
|---|---|
| `Mecha-Core/scripts/zotero-import.ps1` | 检索/导入引擎（spawn 调用，本仓库不改它） |
| `Mecha-Core/.mecha/journal-overrides.json` | 例外表（本仓库可写） |
| `Mecha-Core/.mecha/zotero-import-ledger.json` | 采集台账（引擎写、本仓库只读算窗口） |
| `~/.config/mecha/secrets/zotero.env` | Zotero API 凭证（`ZOTERO_USER_ID` / `ZOTERO_API_KEY`，受控建 collection 用） |
| `Mecha-Memex/00-系统/期刊来源表.md` | 74 刊来源（5 分类，只读解析） |

运行时：Python 3.11+ · PySide6（见 `requirements.txt`）。PubMed 走 E-utilities（免 key）；Zotero 走官方 API。

## 分片进度

- **Slice 1** ✅ PySide6 采集台核心（期刊树 + dry-run 审计页 + 引擎桥）
- **Slice 2** ✅ 全 74 刊载入 + 配置写回例外表 + 台账自适应窗口 + 护栏
- **Slice 3** ✅ 真实导入（-Execute）+ 受控建 collection + 幂等重试（首次真实导入 JTO 6 篇端到端验证）
- **Slice 4** ✅ 回填历史（年/月）+ VBS 启动器 + 设置/说明页 + README

## 结构

```
gui.py              入口（QApplication + 主窗 + 自检钩子 MECHA_SELFTEST）
lit/                引擎桥（engine）/ 期刊表（journals）/ 台账（ledger）/
                    例外表（overrides）/ Zotero API（zotero）/ 配置常量（config）
ui/                 主窗（main_window）/ 样式（style）/ 后台线程（workers）
ui/pages/           采集台（harvest）/ 设置（settings）/ 说明（help）
机甲文献.vbs        双击启动器（pythonw，无黑窗）
```

检索/导入都在后台线程跑（不卡 UI）；dry-run 预览绝不写 Zotero，真实导入仅点「导入」/「重试」触发。
