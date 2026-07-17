# 铁令 + Mecha-Lit Slice 2（GLM 亲手执行）

⚠️ **铁令**：你＝执行的手，亲手写代码。**禁止 dispatch / 委派 / 转交任何子 agent——你就是 GLM 执行体。** cockpit 里"派 GLM 执行、主驾编排"的规则本轮不适用于你（你是执行者）。产出＝改好的 `.py` 文件 + 亲手跑起来验证，不是进度报告。**若再委派即判失败。**

## 背景：Slice 1 已完成并通过主驾验收
`D:\mecha-lit` 是能跑的 PySide6 采集台（`venv\Scripts\python.exe gui.py` 起窗）。引擎桥 `lit/engine.py` 已验证真跑通（run_search → found=31/new=19/dup=12）。**先读现有代码再动手**：`ui/pages/harvest_page.py`、`lit/engine.py`、`lit/config.py`、`ui/main_window.py`。在其上加 Slice 2，**别推倒重来**。

## Slice 2 范围（四件事）

### 1. 载全 74 刊（替换静态胸外 10）
- 新建 `lit/journals.py`，解析 `D:\BaiduSyncdisk\Mecha-Core\Mecha-Memex\00-系统\期刊来源表.md`（**只读**）。表格式：`| 来源分类 | 期刊全名 | PubMed缩写 | 推荐目录名 | 备注 |`；`line.split('|')` 后 cells[1]=分类、cells[4]=推荐目录名（=检索用刊名）。跳过：列数<5、cells[1] 含"来源分类"（表头）、cells[1] 是 `^-+$`（分隔行）。
- 左树按 5 分类分组（基础与转化医学 / 临床医学综合 / 医学AI与数字医学 / 胸部肿瘤与胸外科 / 流行病学与公共卫生）→ 各刊叶子（用 cells[4] 刊名）。保持 Slice 1 的树交互（叶子可选、分类节点不可选、默认选 J Thorac Oncol）。
- 表读不到 / 解析空 → **优雅回退**到现有静态 10（别崩）。

### 2. 检索配置写回例外表 `journal-overrides.json`
- 新建 `lit/overrides.py` 管 `D:\BaiduSyncdisk\Mecha-Core\.mecha\journal-overrides.json`（这是给 App 写的配置，可写；引擎也读它）。
- 选中刊 → 读该刊条目，把 `includeEditorial`/`includeLetter`/`topicFilter` 反映到 chips + 主题过滤输入框。**默认**（无该刊条目）＝ Article+Review+有摘要、无 editorial/letter、无 topicFilter。
- chips / 主题过滤改动 → 写回该刊配置：**与默认相同则删除该刊条目（不落行），与默认不同才落**。**原子写**（写 temp 再 rename）、**保留其它刊已有条目**（现有 `{"J Thorac Oncol":{"includeEditorial":true}}` 不能丢）。
- 与默认不同的刊：配置区显示「例外」小标（用 style.ACCENT）。
- 主题过滤：加 QLineEdit（占位提示 `lung[tiab] OR esophag*[tiab] …`），写入 topicFilter；空=删除该字段。

### 3. 采集最新：窗口从台账算（真自适应窗，替换硬编码 60）
- 新建 `lit/ledger.py`：读 `D:\BaiduSyncdisk\Mecha-Core\.mecha\zotero-import-ledger.json` 的 `batches[]`，取该刊（`batch.journal==刊名`）最大 `time`（ISO 如 `2026-06-18T..`）。`reldate_for(journal)`：有 → `(今天-那天).days + 30`（夹在 [7,400]）；无（首次）→ 60。同时返回 `last_date`（或 None）给 UI 显示。
- 采集台配置区显示：有历史「采集最新：上次 <date> · +30天缓冲 · 近 <N> 天」；首次「首次采集 · 近 60 天」。检索时用算出的 N 传 `reldate_days`。

### 4. UI 护栏两条
- **④** 「仅要有摘要」只对 Article/Review 有意义：当 Article 与 Review **都没勾**时，把「仅要有摘要」勾选框 disable（灰掉）。
- **⑧** 命中 0：`run_search` 返回 `found==0` 时，审计页读 JSON 的 `taMismatch`——true → 红字（style.DANGER_TEXT 口径）「⚠ 刊名可能与 PubMed [TA] 错配，核对缩写」；false → 「本期无新文献（该刊 [TA] 宽检索共 <broadCount> 篇存在）」。

## 严禁
- 只读：期刊表、台账（`zotero-import-ledger.json`）。可写：仅 `journal-overrides.json`（App 的配置）。**不改 mecha-quant / Mecha-Core 其它任何文件 / 引擎。**
- Slice 2 仍**禁 `-Execute` / 任何真实 Zotero 写入**（真导入是 Slice 3）。
- 不推倒 Slice 1 已验证代码；配色只用 `ui/style.py` 既有常量。

## 建完亲手自验（不是只写）
1. `venv\Scripts\python.exe gui.py` 起窗：左树 74 刊分 5 类；选不同刊 chips 随其配置变；采集最新显示算出的窗口天数。
2. 配置写回探针：`from lit import overrides` 选个刊关掉 Editorial → 确认 json 落条目；改回默认 → 确认条目删除；确认 `J Thorac Oncol` 原有条目没被误删。
3. 窗口探针：`from lit import ledger; print(ledger.reldate_for('J Thorac Oncol'))` 返回合理天数（非崩）。
4. `grep -rn Execute lit ui` 确认无真实写入调用。

## 回执（≤400字）
①四件事各完成情况 ②起窗实况（左树 74 刊分类？配置随刊变？窗口天数显示？）③配置写回 / 窗口计算 / 命中0 三处探针实测值 ④卡点（贴报错原文）。**亲手做，禁委派，产出＝代码文件。**
