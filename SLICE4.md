# 铁令 + Mecha-Lit Slice 4（回填历史 + 启动器 + 文档 · GLM 亲手执行）

⚠️ **铁令**：你＝执行的手，亲手写代码。**禁止 dispatch / 委派任何子 agent——你就是 GLM 执行体。** cockpit"派 GLM"规则本轮不适用于你。产出＝改好的文件 + 亲手验证。**再委派即判失败。**

⚠️ **本片碰真写库（回填导入也是 -Execute），但你只建代码、验证只走 dry-run + mock，绝不真跑 -Execute。** 真实回填导入由主驾监督。

## 背景：Slice 1–3 已过主驾验收（含首次真实导入 JTO 6 篇端到端验证）
`D:\mecha-lit` 采集最新已端到端能用：检索→审计页→导入→入库→幂等→锚点前移，全绿。**先读现有**：`ui/pages/harvest_page.py`、`lit/engine.py`、`lit/journals.py`。在其上加 Slice 4，别推倒。

## Slice 4 范围（四件事）

### 1. 回填历史（复用现有检索/导入流程，只换窗口参数）
- 启用 `rb_back`（现在 disabled）。选「回填历史」时，配置区显示**年/月选择**：年 QComboBox（近 ~8 年，如 2019–2026）+ 月 QComboBox（`全年` / `01`…`12`）。
- 检索/导入构 params 时按模式分流：**采集最新** → `reldate_days=self._window_days`；**回填** → 选「全年」用 `year=<年>`、选具体月用 `month="<年>-<月>"`。引擎桥 `run_search`/`run_import` 已支持 month/year 参数，直接传。
- `_last_params` 要带上窗口类型（存 `mode`/`year`/`month` 或直接存传给引擎的 kwargs），导入用它。检索文案/确认框相应显示回填的窗口（不是"近 N 天"）。
- **护栏⑭ 输入校验**：回填年份不超今年、月份非未来（今年只能选到当前月）；违反 → 禁检索 + 提示。
- **护栏⑫ retmax**：检索返回 `found>=1000` → 审计页显警示（style.WARN_TEXT 口径）：「命中达上限 1000，可能截断，建议改按月回填」。（本片不做自动分月循环，只告警——按月回填即可规避。）

### 2. VBS 启动器（像 mecha-quant 双击即开、无黑窗）
- 建 `机甲文献.vbs`：参照 `D:\mecha-quant\机甲量化.vbs` 的写法，用 `venv\Scripts\pythonw.exe gui.py`（pythonw 无控制台窗）静默启动。路径用相对/脚本自身目录定位，别写死绝对路径。

### 3. README.md
- 一句话定义（素材库进料端的桌面 GUI）＋ 是什么/怎么跑（venv + `python gui.py` 或双击 vbs）＋ 功能（采集最新/回填/配置例外表）＋ 依赖说明（调 `Mecha-Core/scripts/zotero-import.ps1` 引擎、`journal-overrides.json` 配置、`zotero.env` 凭证）＋ 分片进度。给人读、简洁。

### 4. 设置页 + 说明页（填实内容，替占位）
- `settings_page.py`：只读展示关键路径与状态——引擎路径（存在?）、journal-overrides.json 路径、台账路径、zotero.env（存在?，**不显示 key 值**）、当前 74 刊载入数。不做可编辑设置（本版）。
- `help_page.py`：采集台使用说明（选刊→配置→采集最新/回填→检索预览→导入）、护栏说明、"真实导入可逆(回收站)"提示。

## 严禁
- 只读/调用引擎，不改 mecha-quant / Mecha-Core。可写：仅 `journal-overrides.json`。
- **你绝不真跑 -Execute / 真写 Zotero**（回填导入首跑主驾监督）。
- 不推倒 Slice 1–3 已验证代码；配色只用 style.py 既有常量。

## 验证（亲手做，只 dry-run + mock）
1. `MECHA_SELFTEST=1 venv\Scripts\python.exe gui.py` exit 0。
2. 回填 dry-run 探针（**不 -Execute**）：`engine.run_search('J Thorac Oncol', year=2025)` 或 `month='2025-10'` 返回合理 found（打印数即可）。
3. 采集最新回归：`run_search('J Thorac Oncol', reldate_days=30)` 仍 new=19 一带（BOM/流程没被回填改动破坏）。
4. VBS：确认 `机甲文献.vbs` 内容正确（pythonw + gui.py），**不必真双击**。
5. `grep -rn "run_import\|-Execute" lit ui` 复核：真写仅在导入按钮/重试触发，无自动真跑。

## 回执（≤400字）
①回填/VBS/README/设置说明 各完成情况 ②验证实测：selftest exit + 回填 dry-run found 数 + 采集最新回归数 ③确认全程未真跑 -Execute ④卡点。亲手做，禁委派，禁真写。
