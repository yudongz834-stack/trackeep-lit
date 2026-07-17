# 机甲文献 — Slice 1 构建说明

PySide6 原生桌面 App，结构 / QSS / 线程模式对齐 `D:\mecha-quant`，在
`zotero-import.ps1` 引擎之上做 GUI（dry-run 采集预览）。**Slice 1 不写 Zotero、不动台账。**

## 启动

```bash
# 1) 建虚拟环境 + 装依赖（已执行，PySide6 6.11.1）
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt

# 2) 起窗
venv\Scripts\python.exe gui.py

# 3) 起窗自检（3 秒自动退出，退出码 0 = 整窗能拉起）
MECHA_SELFTEST=1 venv\Scripts\python.exe gui.py
```

## 自验结果（真跑，非仅写代码）

| 项 | 结果 |
|---|---|
| venv + PySide6 | ✅ PySide6 6.11.1 |
| 起窗自检（exit 0） | ✅ |
| 桥探针 `run_search('J Thorac Oncol', reldate_days=60)` | ✅ **found=31 new=19 dup=12 suspect=0 executed=False** |
| 审计页渲染（真实 31 条） | ✅ `_render_receipt` 在真实数据上不崩，items_rendered=31 |

found 落在 brief 基准 25–40 区间，与 ground truth（found=31/new=19/dup=12）一致 → 桥真通。

## 各功能实现位置

| 功能 | 文件 |
|---|---|
| 入口（QApplication + QSS + AppUserModelID + 自检） | `gui.py` |
| 配置常量（APP_NAME/VERSION/ROOT/ENGINE_PATH/MECHA_CORE） | `lit/config.py` |
| 后端桥（spawn 引擎 / parse MECHA_JSON / 三选一窗口 / -EmitJson） | `lit/engine.py` |
| 全局 QSS + 配色常量（沿用 mecha-quant，未改） | `ui/style.py` |
| 后台线程（FuncWorker + run_async，已裁掉 quant 专用 worker） | `ui/workers.py` |
| 主窗（左 nav QListWidget + 右 QStackedWidget + closeEvent wait） | `ui/main_window.py` |
| 采集台（树+配置+检索+审计） | `ui/pages/harvest_page.py` |
| 设置页（占位） | `ui/pages/settings_page.py` |
| 使用说明（占位） | `ui/pages/help_page.py` |

## 采集台交互（Slice 1 实装）

- **左**：分类期刊树（QTreeWidget），分类节点「胸部肿瘤与胸外科（10）」不可选，10 本叶子可单选，默认 J Thorac Oncol。
- **检索配置**：Article/Review/Editorial/Letter 四个 chip（默认 Article+Review+Editorial 勾、Letter 不勾）+「仅要有摘要」。Article/Review/hasabstract 是引擎基底（Slice 1 仅 UI 态）；**Editorial/Letter 才真透传引擎** `-IncludeEditorial` / `-IncludeLetter`。
- **模式**：采集最新（-ReldateDays 60，PubMed edat）已实装；回填历史禁用占位。
- **检索按钮**：pubtype 至少勾一个 + 选中叶子刊才启用；点击 → 禁用按钮 + 状态行「⏳ 检索中…（约 30–60 秒）」→ `run_async` 后台跑 `engine.run_search` → done 渲染审计页 / failed 显示错误原文。
- **审计页**：时间戳徽章 + found/new/dup/suspect 四块统计 + 最终 query + 按 status 分组清单（新增/去重/疑似，每条 title + pill + tooltip 明细）+ collection/journal/mode 页脚。

## 护栏（SPEC §7 基础三条，已内建）

1. 检索走 `run_async` workers 线程，**绝不卡 UI**（引擎 30–60s）。
2. 运行中禁用「检索」按钮 + 显示进度文案。
3. pubtype 至少勾一个才启用检索。

**Slice 1 绝不 `-Execute` / 任何真实 Zotero 写入**（`lit/engine.py` 末尾固定 `-EmitJson`，无 -Execute 分支）。

## 桩点（后续 slice）

- **Slice 2**：全 74 刊从 Mecha-Core 期刊来源表载入；配置写回 `journal-overrides.json`；窗口从台账锚点算；回填历史；护栏④⑤⑧⑬⑭。
- **Slice 3**：真实导入（-Execute）+ 受控建 collection（护栏⑯）+ 回执/部分成功重试（⑨）+ 崩溃恢复（⑩）+ 单飞锁（⑮）+ 锚点（⑪）+ 分窗（⑫）。
- **Slice 4**：PyInstaller 打包 + VBS 启动器 + README + 图标。

## 严禁（已遵守）

不改 `D:\mecha-quant`、不改 `D:\BaiduSyncdisk\Mecha-Core`（只读参照 + 只读 spawn 引擎）；不重写引擎为 Python；Slice 1 禁 -Execute；不引 CDN、App 不自行联网。
