# GLM 任务：Mecha-Lit Slice 1（PySide6 采集台核心）

你在当前目录 `D:\mecha-lit` 建一个 **PySide6 原生桌面应用**。**先完整读 `SPEC.md`**（本目录），按其 §7 Slice-1 范围建。本 brief 只强调关键点。

## 第一步（别跳过）：通读参照物
照 `D:\mecha-quant` 的写法建（结构 / QSS / 线程 / 左导航+右分页），先读：
`D:\mecha-quant\gui.py`、`ui\main_window.py`、`ui\workers.py`、`ui\style.py`、`ui\state.py`、`ui\pages\data_center.py`。
本项目要"像 mecha-quant"——它是 PySide6 原生 Qt 桌面软件，**不是网页、不是 webview**。

## 血的教训（别踩）
1. 后端**spawn** `zotero-import.ps1 … -EmitJson` 再 `json.loads` 那行 `MECHA_JSON ` —— **不重写引擎、不改 Mecha-Core / mecha-quant 一个字节**（只读参照、只读调用）。
2. 已放好 `ui/style.py`、`ui/workers.py`。**`ui/workers.py` 必须改**：删顶部 `from quant import datahub, scan` 与 mecha-quant 专用的 `UpdateWorker`，只留通用 `FuncWorker` + `run_async`（否则 import 就崩）。
3. Slice 1 **禁 `-Execute` / 任何真实 Zotero 写入**——只做 dry-run 检索预览。
4. 引擎一次 run_search（如 `-Journal "J Thorac Oncol" -ReldateDays 60 -EmitJson`）要 30–60s（拉 PubMed + 遍历 Zotero 库去重），**放 workers 线程别卡 UI**，给足超时。
5. **建完自己在 venv 里真跑起来验证**：`python -m venv venv` → `venv\Scripts\python.exe -m pip install -r requirements.txt` → `venv\Scripts\python.exe gui.py` 起窗 → 选 J Thorac Oncol → 点检索 → 确认真渲染出审计页。别只写不跑。

## 交付回执（≤400 字，你的最终消息）
①`python gui.py` 是否起窗成功 ②点检索是否真 spawn 引擎、真拿到 `MECHA_JSON`、真渲染审计页（**附一次真实 found/new/dup 数**）③venv + requirements 是否装好 ④卡点（若有，贴报错原文）⑤文件清单 + 起动步骤。
你的返回文本＝交付回执，主驾据此审。别客套。
