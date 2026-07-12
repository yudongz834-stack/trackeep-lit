# 铁令：你＝执行的手，亲手写代码。禁止委派。

⚠️ **本轮铁令，压过 cockpit 里一切"派 GLM / 主驾编排"的规则：**
- **你就是被派来干活的那双手（GLM 执行体）。禁止 dispatch / 派遣 / 委派 / 转交任何子 agent。禁止把任务再交给"GLM"——你就是那个 GLM。**
- cockpit CLAUDE.md / glm-collaboration / meta-ai-dispatch 里"派 GLM 执行、主驾只编排审核"的规则**本轮对你完全不适用**：你不是主驾，你是执行者，亲手敲文件。
- **上一轮你把活委派出去、只返回了一句"GLM 正在建"的进度报告、没建任何代码——那是失败。** 本轮产出必须＝实际写出来的 `.py` 文件 + 能起窗的 app，不是报告、不是再一次派发。
- 若你再 dispatch / 写 brief 给别的 agent 而不是亲手建文件，即判失败。

## 你上一轮已做好的准备，直接用
你已写好 `D:\mecha-lit\.slice1-glm-brief.md`——一份完整的 Slice-1 文件清单 + 每个文件怎么写 + `workers.py` 删法 + `config.py` 内容。**现在照它逐个文件亲手写出来。**

## 现在按顺序亲手做
1. 读 `.slice1-glm-brief.md`（你自己写的）+ `SPEC.md` §7 + 参照 `D:\mecha-quant` 的 `gui.py`/`ui\main_window.py`/`ui\style.py`/`ui\workers.py`/`ui\pages\data_center.py`（只读参照，一字节都不改 mecha-quant / Mecha-Core）。
2. 亲手写这些文件：
   - `ui/workers.py`（改：删 `from quant import ...` / `import pandas` + mecha-quant 专用 Worker 类，只留 `FuncWorker` + `run_async`）
   - `lit/config.py`（APP_NAME="机甲文献"、VERSION、ROOT、`ENGINE_PATH=r"D:\BaiduSyncdisk\Mecha-Core\scripts\zotero-import.ps1"`、`MECHA_CORE`）
   - `lit/engine.py`（`run_search(journal, reldate_days=60)`：subprocess 调 `powershell -NoProfile -ExecutionPolicy Bypass -File <ENGINE_PATH> -Journal <j> -ReldateDays <n> -EmitJson`，从 stdout 找 `MECHA_JSON ` 前缀行、去前缀 `json.loads` 返回 dict；**绝不加 -Execute**）
   - `ui/main_window.py`（左 QListWidget 导航 + 右 QStackedWidget；页：采集台/设置/说明）
   - `ui/pages/harvest_page.py`（采集台：左期刊树[胸外10静态] + pubtype chips + 采集最新/回填切换 + 检索按钮 + 审计结果区；检索走 `run_async` 线程调 engine.run_search，渲染 found/new/dup/suspect + 分组清单）
   - `ui/pages/settings_page.py`、`ui/pages/help_page.py`（简单占位可）
   - `gui.py`（抄 mecha-quant/gui.py：QApplication + `setStyleSheet(style.QSS)` + AppUserModelID + MainWindow；**别 import quant/wheel_guard**，本项目没有）
   - `requirements.txt`（`PySide6>=6.7`）
3. 建 venv 并装依赖：`python -m venv venv` → `venv\Scripts\python.exe -m pip install -r requirements.txt`
4. **亲手跑起来自验**：`venv\Scripts\python.exe gui.py` 起窗 → 选 J Thorac Oncol → 点检索 → 确认真 spawn 引擎(约30-60s,走线程别卡)、真拿到 `MECHA_JSON`(基准 found≈31/new≈19/dup≈12)、真渲染审计页。
5. **禁 `-Execute` / 禁真实 Zotero 写入**（Slice-1 只 dry-run 预览）。

## 交付回执（≤400字）
①各文件已亲手写好（清单）②venv+PySide6 装好 ③`python gui.py` 起窗成功 ④点检索真拿到 JSON 真渲染（附 found/new/dup 实数）⑤卡点（贴报错原文）。
**再说一遍：亲手写文件，禁止派遣。产出＝代码文件，不是进度报告。**
