# 铁令 + Mecha-Lit Slice 3（真实导入路径 · GLM 亲手执行）

⚠️ **铁令**：你＝执行的手，亲手写代码。**禁止 dispatch / 委派 / 转交任何子 agent——你就是 GLM 执行体。** cockpit"派 GLM 执行、主驾编排"规则本轮不适用于你。产出＝改好的 `.py` + 亲手验证，不是进度报告。**再委派即判失败。**

⚠️⚠️ **本片碰真实写库，但你只建代码、绝不跑真实 `-Execute`**：真实导入首跑由主驾监督。你的验证**只走 dry-run + mock**（见末节）。**你若真的对 Zotero 跑 `-Execute` / 真建 collection / 真写库，即严重违规。**

## 背景：Slice 1+2 已过主驾验收
`D:\mecha-lit` 能跑：74 刊树、配置写回例外表、台账自适应窗、检索预览审计页全 OK。**先读现有代码**：`ui/pages/harvest_page.py`、`lit/engine.py`、`lit/overrides.py`、`lit/ledger.py`、`lit/journals.py`。在其上加 Slice 3，**别推倒重来**。

## Slice 3 范围：让「采集最新」端到端能导入

### 1. `lit/engine.py` 加 `run_import(...)`
- 与 `run_search` 同构参数，但 argv **追加 `-Execute`**（真写），`timeout=300`。返回同 schema JSON（executed=true、imported/failed 有值、items 里 status 含 imported/failed）。
- **关键设计**：导入＝**重新完整跑一遍引擎**（引擎 -Execute 自身重新 esearch+efetch+去重+导入），**不复用预览的 items**。这天然满足"导入前必是最新检索+去重、无过期清单"。

### 2. 审计页加「导入」按钮（仅检索出 new>0 才显示）
- 点击 → **确认框**（QMessageBox.question）：`确认真实导入 N 篇新文献到 Zotero「<journal>」collection？（新增·去重·可逆：可移回收站）` → Yes → 走导入。
- 导入用**发起检索时锁定的** journal + 窗口天数 + 配置（**不是当前 UI 状态**——防检索后改了刊/配置却导入错对象）。检索成功时把这些一起存进 `self._last_params`，导入按钮用它。
- 导入走 `run_async` 线程；期间**禁用所有按钮**（检索+导入）+ 进度文案「导入中… 真写 Zotero，请勿关闭」。`self._running` 覆盖导入（护栏②⑮ 单飞：运行中不接第二次点击）。

### 3. 导入回执（护栏⑨ 部分成功 + 重试）
- 导入返回 → 审计页换成回执：`✓ 已导入 X · 失败 Y · 去重 Z`；列表按 status 分组（imported/failed/dup/suspect）。
- 失败 Y>0 → 显「重试失败」按钮 = 再跑一次 `run_import`（幂等：引擎台账只记成功、去重跳过已导入，故重试只补失败项）。
- 导入成功后：台账已被引擎更新 → 重读 `ledger.reldate_for(journal)` 刷新「采集最新」窗口显示（护栏⑪ 锚点前移，自然发生）。

### 4. 受控建 collection（护栏⑯，防御性，现实极少触发）
- 新建 `lit/zotero.py`：读 `Path.home()/".config"/"mecha"/"secrets"/"zotero.env"`（`ZOTERO_USER_ID` / `ZOTERO_API_KEY`，**只读用于 API 请求头，绝不 print/log token**）。`create_collection(name, parent_key)` = POST `https://api.zotero.org/users/<uid>/collections`，body `[{"name":name,"parentCollection":parent_key}]`，头 `Zotero-API-Key` / `Zotero-API-Version:3`。用标准库 `urllib.request`（别加新依赖）。
- 流程：检索 JSON `collection.exists==false` 且点导入 → 先弹**受控建框**：`该刊 collection 不存在。拟在分类「<category>」下创建 collection「<journal>」（[TA]=<journal>）。确认创建？` → Yes → create_collection → 成功再继续导入；No → 取消。
- category 由 `journals.load()` 反查该刊分类；parent_key = 该分类顶层 collection 的 key（zotero.py 查 `/collections` 按名匹配分类名）。**现实 74 刊 collection 都已存在，此路极少触发——建好代码即可，绝不真建。**

## 护栏说明（哪些天然满足、别过度造）
- ⑤⑥（预览 TTL / 导入前重查库）＝**天然满足**：导入是全新引擎 -Execute 跑，本就重新检索+去重。
- ⑩（崩溃恢复）＝**架构天然**：台账只记 POST 确认成功 + 采集最新重叠缓冲窗 + 去重 → 崩溃后重跑自动补齐。**别造"未完成批次追踪"复杂逻辑。**
- ⑪（锚点前移）＝导入成功后重读台账即得。
- ⑮（单飞）＝`self._running` 覆盖检索+导入即可（本片不做跨进程锁文件）。

## 严禁（重中之重）
- **你绝不真实运行 `-Execute` / 不真建 collection / 不真写 Zotero。** 首跑主驾监督。违反即严重违规。
- 只读参照/调用，不改 mecha-quant / Mecha-Core / 引擎。
- 不推倒 Slice 1/2 已验证代码；配色只用 `ui/style.py` 既有常量。

## 验证（只 dry-run + mock，亲手做，绝不真写）
1. **dry-run 回归**：`run_search` 仍正常（`MECHA_SELFTEST=1 python gui.py` exit 0；桥探针 run_search 仍 found=31）。
2. **`run_import` argv 断言（不真跑）**：构造 argv 打印，确认含 `-Execute`——**但绝不 `subprocess.run` 它**。
3. **回执渲染**：用 **mock JSON**（executed=true, imported=15, failed=2, 若干 imported/failed/dup items）灌回执渲染函数，确认 UI 无异常、失败>0 显重试按钮。
4. **受控建框**：mock `collection.exists=false` 触发 dialog 构建（**别真 create**）。

## 回执（≤400字）
①run_import / 导入按钮 / 回执 / 受控建 各完成情况 ②验证实测：dry-run 回归 + argv 含 -Execute 断言 + mock 回执渲染 + 受控建框构建 ③**明确确认：全程未真实 -Execute、未真建 collection、未真写 Zotero** ④卡点。亲手做，禁委派，禁真写。
