# 铁令 + Mecha-Lit Slice 6a（采集策略页 · 按分类策略 · GLM 亲手执行）

⚠️ **铁令**：你＝执行的手，亲手写代码。**禁止 dispatch / 委派任何子 agent——你就是 GLM 执行体。** cockpit「派 GLM」规则本轮不适用于你。产出＝新文件 + 亲手验证。**再委派即判失败。**

⚠️ 本片**纯加法**：只新增文件 + 改 `main_window.py` 导航两处。**绝不碰** `harvest_page.py` / `engine.py` / `overrides.py` / `journals.py` / `ledger.py` / `zotero.py`（可 import，不可改）、**绝不碰** Mecha-Core 引擎、**绝不改** `journal-overrides.json` 内容。**绝不调用 DeepSeek API、绝不 -Execute、绝不写 Zotero。**

## 背景（先读，别推倒）
`D:\mecha-lit` 是已验收的 PySide6 采集台。**先读**：`ui\main_window.py`（导航单一真相源 `_PAGES` + `pages`）、`ui\pages\harvest_page.py`（widget 工厂 `_muted`/`_card`、`_loading` 写回抑制、期刊树写法可借鉴）、`lit\overrides.py`（例外表读写 + `load_all`）、`lit\journals.py`（`CATEGORIES` 五分类 + `category_of` + `load`）、`lit\config.py`（`MECHA_CORE` 绝对路径）、`ui\style.py`（配色常量，只准用这里的）。

**本片要造什么**：一个**采集策略**页（v3 左右分栏：左选分类、右改策略），把「按分类的采集策略」持久化到新文件 `strategy.json`。这是文献爆炸的过滤总控——按 5 大分类分别配 pubtype / PubMed 主题过滤 / DeepSeek 语义筛判据。**本片只做配置持久化 + resolve 合并契约，DeepSeek 只存判据字符串不执行**（执行属下一片 6b）。

## 要造的 4 样

### 1. `D:\BaiduSyncdisk\Mecha-Core\.mecha\strategy.json`（预种子，你亲手写这个文件）
分类键**必须**与 `journals.CATEGORIES` 逐字一致（胸部肿瘤与胸外科 / 流行病学与公共卫生 / 临床医学综合 / 医学AI与数字医学 / 基础与转化医学）。内容如下（这是主驾已用真实 PubMed + DeepSeek 验证过的默认，逐字落盘）：

```json
{
  "version": 1,
  "categories": {
    "胸部肿瘤与胸外科": {
      "editorial": false,
      "letter": false,
      "topicFilter": { "enabled": false, "terms": "" },
      "deepseek": { "enabled": true, "criteria": "研究主体是胸部（肺癌/食管/纵隔/胸膜间皮瘤/胸腺），剔除纯心脏外科（冠脉/瓣膜/先心/心律失常）内容" }
    },
    "流行病学与公共卫生": {
      "editorial": false,
      "letter": false,
      "topicFilter": { "enabled": false, "terms": "" },
      "deepseek": { "enabled": false, "criteria": "" }
    },
    "临床医学综合": {
      "editorial": false,
      "letter": false,
      "topicFilter": { "enabled": true, "terms": "lung[tiab] OR pulmonary[tiab] OR thoracic[tiab] OR NSCLC[tiab] OR SCLC[tiab] OR esophag*[tiab] OR mediastin*[tiab] OR pleura*[tiab] OR mesotheliom*[tiab] OR \"lung neoplasms\"[mh] OR \"thoracic neoplasms\"[mh]" },
      "deepseek": { "enabled": true, "criteria": "研究主体真正聚焦肺癌或胸部肿瘤（肺/食管/纵隔/胸膜/胸腺），而非泛癌或其它系统疾病顺带提及 lung/thoracic" }
    },
    "医学AI与数字医学": {
      "editorial": false,
      "letter": false,
      "topicFilter": { "enabled": false, "terms": "" },
      "deepseek": { "enabled": false, "criteria": "" }
    },
    "基础与转化医学": {
      "editorial": false,
      "letter": false,
      "topicFilter": { "enabled": true, "terms": "lung[tiab] OR pulmonary[tiab] OR thoracic[tiab] OR NSCLC[tiab] OR SCLC[tiab] OR esophag*[tiab] OR mediastin*[tiab] OR pleura*[tiab] OR mesotheliom*[tiab] OR \"lung neoplasms\"[mh] OR \"thoracic neoplasms\"[mh]" },
      "deepseek": { "enabled": true, "criteria": "研究主体真正聚焦肺癌或胸部肿瘤，而非泛癌机制研究顺带用到 lung 细胞系或提及 thoracic" }
    }
  }
}
```

### 2. `lit\strategy.py`（策略读写 + resolve 合并契约）
仿 `overrides.py` 的风格（utf-8-sig 读兼容 BOM、原子写 mkstemp+os.replace、保留其它键）。API：

- `STRATEGY_PATH = config.MECHA_CORE / ".mecha" / "strategy.json"`
- `CATEGORY_DEFAULT = {"editorial": False, "letter": False, "topicFilter": {"enabled": False, "terms": ""}, "deepseek": {"enabled": False, "criteria": ""}}`
- `load() -> dict`：读 strategy.json（utf-8-sig）。读不到/解析失败 → 返回 `{"version": 1, "categories": {}}`。对缺失的分类键，调用方用 `get_category` 兜 `CATEGORY_DEFAULT`。
- `get_category(cat: str) -> dict`：返回该分类策略（深拷 `CATEGORY_DEFAULT` 再覆盖已存字段；`topicFilter`/`deepseek` 子字典也要逐字段兜默认，防半缺）。
- `save_category(cat: str, policy: dict) -> None`：原子写。读现有 → 更新该分类 → 保留 `version` 与其它分类 → 写回。`policy` 结构同 `CATEGORY_DEFAULT`。
- `resolve(journal: str) -> dict`：**6b 用的合并契约**——分类默认 ⊕ 单刊例外（单刊显式字段优先）。实现（严格照此，别自由发挥）：
  ```
  cat = journals.category_of(journal)
  base = get_category(cat) if cat else copy of CATEGORY_DEFAULT
  raw = overrides.load_all().get(journal) or {}        # 只含该刊“显式”字段
  editorial = raw["includeEditorial"] if "includeEditorial" in raw else base["editorial"]
  letter    = raw["includeLetter"]    if "includeLetter"    in raw else base["letter"]
  # topic：单刊显式 topicFilter（非空）优先，否则用分类的（仅当 enabled）
  if raw.get("topicFilter"):
      topic = raw["topicFilter"]
  elif base["topicFilter"]["enabled"] and base["topicFilter"]["terms"].strip():
      topic = base["topicFilter"]["terms"].strip()
  else:
      topic = None
  return {"editorial": bool(editorial), "letter": bool(letter), "topic": topic,
          "deepseek_enabled": bool(base["deepseek"]["enabled"]),
          "deepseek_criteria": base["deepseek"]["criteria"] or ""}
  ```
  （`import` 用 `from lit import journals, overrides`。）

### 3. `ui\pages\strategy_page.py`（v3 左右分栏 UI）
**左**：`QListWidget`（objectName 随意，不必是 "nav"），固定宽 ~248，列出 `journals.CATEGORIES` 五分类，每行文字 `f"{cat}（{n}）"`（n=该分类刊数，用 `journals.load()` 取）。默认选中第 0 行。
**右**：`QScrollArea` + 表单，随左选分类切换载入该分类策略。表单含（用 style.py 配色、`_card` 卡片包裹、`_muted` 说明）：
1. 分类标题（`pageTitle` 或 `sectionTitle`）+ 一句 `_muted` 说明这页干嘛（选分类→配采集策略→自动存 strategy.json；单刊例外仍在采集台配）。
2. **文献类型**行：`Article`、`Review` 两个 checkbox 设 `setChecked(True); setEnabled(False)`（引擎恒含的基底，展示用不可改）；`Editorial`、`Letter` 两个可勾 checkbox（对应 `editorial`/`letter`）。
3. **PubMed 主题过滤**行：checkbox「启用主题过滤（PubMed 检索式层）」（对应 `topicFilter.enabled`）+ `QLineEdit`（对应 `topicFilter.terms`，placeholder 给 `lung[tiab] OR esophag*[tiab] …`）。checkbox 关时 QLineEdit `setEnabled(False)`。
4. **DeepSeek 语义筛**行：checkbox「启用 DeepSeek V4 Flash 语义复筛（按标题+摘要逐篇判留/滤）」（对应 `deepseek.enabled`）+ 多行 `QPlainTextEdit`（对应 `deepseek.criteria`，2–3 行高，placeholder 举例「研究主体真正聚焦肺癌/胸部肿瘤，而非泛癌顺带提及」）。checkbox 关时禁用文本框。
5. 一行 `_muted` 小结当前分类是「全收 / 主题过滤 / +AI 复筛」（可选，简单拼即可）。

**交互**：切分类 → `_load(cat)` 把策略反映到控件（用 `self._loading = True/False` 抑制期间写回，仿 harvest_page）。任一控件变更（`toggled`/`editingFinished`/`textChanged` 去抖）→ `_save(cat)` 组 policy dict 调 `strategy.save_category`。写失败 try/except 显提示不崩。**本页只写 strategy.json，绝不碰 journal-overrides.json。**

### 4. `ui\main_window.py` 导航接入（只改这里）
`_PAGES` 在「采集台」与「设置」之间插 `("采集策略", "🎛️  采集策略")`；`self.pages` 列表同位置插 `StrategyPage()`（顺序与 `_PAGES` 严格对齐）。`import` 加 `from ui.pages.strategy_page import StrategyPage`。别的不动。

## 严禁
- 不改上列 6 个既有 lit/ui 文件（除 main_window 导航两处）、不改 Mecha-Core、不改 journal-overrides.json。
- 不调 DeepSeek / 不 -Execute / 不写 Zotero / 不联网。
- 配色只用 `ui/style.py` 常量，不新造硬编码色。
- 不装新依赖（只用 PySide6 + 标准库）。

## 验证（亲手做，全离线）
1. `set MECHA_SELFTEST=1 && venv\Scripts\python.exe gui.py` → **exit 0**（新页随窗构建不崩；gui.py 3 秒自退）。
2. strategy.json 往返：Python 里 `from lit import strategy`；`strategy.save_category("临床医学综合", {...改 deepseek.enabled=False...})` → 重新 `strategy.load()` 确认①该分类改动落盘②其它 4 分类原值在③`version` 仍在。**验完把这条改动改回原值**（别污染种子）。
3. `resolve()` 正确性：对 `journals.load()` 里**胸部**分类取一本真实刊 + **临床医学综合**取一本真实刊，分别打印 `strategy.resolve(刊名)`。预期：胸部刊 `deepseek_enabled=True`、`topic=None`；`J Thorac Oncol` 额外 `editorial=True`（来自 journal-overrides.json）；综合刊 `deepseek_enabled=True`、`topic` 为胸部词串。
4. 回归：`from lit import overrides; print(overrides.get("J Thorac Oncol"))` 仍 `includeEditorial=True`（journal-overrides.json 没被动）。
5. `git -C D:\mecha-lit status` 确认改动面 = 仅新增 strategy.json（在 Mecha-Core，不提交进 mecha-lit 仓）/ 新增 strategy.py / 新增 strategy_page.py / 改 main_window.py。**注意**：strategy.json 在 `D:\BaiduSyncdisk\Mecha-Core\.mecha\`，不属 mecha-lit 仓，别 add 它。

## 提交
`git -C D:\mecha-lit add lit/strategy.py ui/pages/strategy_page.py ui/main_window.py SLICE6a.md` → commit，信息 `Slice 6a: 采集策略页（按分类 pubtype/主题过滤/DeepSeek 判据）+ strategy.json + resolve 契约`。

## 回执（≤400字）
①4 样各完成情况 ②验证实测：selftest exit 码 + strategy.json 往返结果 + 两本刊的 `resolve()` 打印 + 回归 overrides.get ③确认全程未调 DeepSeek/未 -Execute/未改既有 6 文件与 journal-overrides.json ④commit hash ⑤卡点（贴报错原文）。亲手做，禁委派。
