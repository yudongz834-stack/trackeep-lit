# Mecha-Lit 施工规格（PySide6 原生桌面 · 严格对齐 mecha-quant）

架构/审核/指挥＝主驾（Claude），执行＝GLM 5.2。PI 已授权主驾自主推进到底。

## 0. 一句话
一个 **PySide6 原生桌面 App**（技术栈与观感严格对齐 `D:\mecha-quant`），在现有 `zotero-import.ps1` 引擎之上做 GUI：分类期刊树 + 检索配置 + 采集最新/回填历史 + 检索预览审计页 + 真实导入 Zotero。真写、16 护栏内建。**不是 webview、不是浏览器——是原生 Qt 应用。**

## 1. 栈 & 落位（严格对齐 mecha-quant）
- 位置：`D:\mecha-lit`（与 `D:\mecha-quant` 同级）
- 栈：**PySide6 + PyInstaller + venv + VBS 启动器**；结构 / QSS / 线程模式**镜像 `D:\mecha-quant`**
- 已放好基座：`ui/style.py`、`ui/workers.py`（从 mecha-quant 复制）、`prototype-reference.html`（设计/流程参照）
- **动手前必读参照物**（照它写、别自创）：`D:\mecha-quant\gui.py`、`ui\main_window.py`、`ui\workers.py`、`ui\style.py`、`ui\state.py`、`ui\pages\data_center.py`（后台任务+进度条的范例页）
- 后端：spawn `powershell -NoProfile -ExecutionPolicy Bypass -File "D:\BaiduSyncdisk\Mecha-Core\scripts\zotero-import.ps1" -Journal <j> <窗口参数> -EmitJson`，从 stdout 取 `MECHA_JSON ` 前缀行、去前缀 `json.loads`。**不重写引擎、不改 Mecha-Core / mecha-quant 任何文件。**

## 2. 结构
- `gui.py`（抄 mecha-quant/gui.py：QApplication + setStyleSheet(style.QSS) + AppUserModelID + app icon + MainWindow）
- `ui/style.py`（已放；按需追加 lit 专用 QSS 规则，配色沿用其常量）
- `ui/workers.py`（已放，**必须改**：删顶部 `from quant import datahub, scan` 和 mecha-quant 专用的 `UpdateWorker`，只留通用 `FuncWorker` + `run_async`）
- `ui/main_window.py`（左 QListWidget 导航 + 右 QStackedWidget；导航项：采集台 / 设置 / 使用说明）
- `ui/pages/harvest_page.py`（采集台＝核心页）、`settings_page.py`、`help_page.py`
- `lit/engine.py`（后端桥：`run_search()` / `run_import()` 调引擎、parse MECHA_JSON、窗口计算、配置读写）
- `lit/config.py`（APP_NAME="机甲文献"、VERSION、ROOT、ENGINE_PATH、MECHA_CORE 等）
- `requirements.txt`（PySide6>=6.7 起步）

## 3. 引擎（主驾已改好并实测，勿动）
`-EmitJson` 末行输出 `MECHA_JSON <一行 compressed JSON>`；dry-run 与 `-Execute` 都吐。窗口参数三选一：`-Month YYYY-MM` / `-Year YYYY` / `-ReldateDays N`；pubtype 开关 `-IncludeEditorial` `-IncludeLetter`；`-TopicFilter "…"`；`-Execute` 才真写。例外配置 `Mecha-Core/.mecha/journal-overrides.json`（引擎自读，App 也读写它）。

## 4. JSON 契约（schema `mecha-lit/import-result@1`）
```
{journal, mode, query, executed,
 found, counts:{new,dup,suspect,imported,failed},
 collection:{key,exists}, broadCount, taMismatch,
 items:[{pmid,doi,title,type,hasAbstract,status,dedupBy,dupSrc}], batchId}
```
非 ASCII 转义为 `\uXXXX`，`json.loads` 后即中文。

## 5. 采集台交互（照 prototype-reference.html 的流程翻成 Qt）
- 左：分类期刊树（Slice-1 用胸外 10 本静态；后续从 `Mecha-Core` 的期刊来源表载全 74）
- 中上：检索配置 chips（Article/Review/Editorial/Letter · 有摘要 · 综合刊主题过滤）＝例外表，改动写回 `journal-overrides.json`
- 中：采集最新（窗口＝台账锚点 −30~45 天缓冲 → 今；首次 60 天）/ 回填历史（日期范围）二选一
- 「检索」→ `run_search`（dry-run）→ 检索预览审计页（时间戳、最终 query、found/new/dup/suspect、按 status 分组清单）
- 「导入」→ `run_import`（-Execute）→ 回执（成功/失败/重复，可只重试失败项）

## 6. 护栏 16 条（后续 slice；此处备查）
①采集最新⇄回填互斥 ②运行中禁用按钮+进度、锁切刊/切模式/改配置 ③pubtype 至少勾一个否则禁检索 ④有摘要仅对 Article/Review ⑤预览结果带时间戳+TTL，超期导入前重检索去重 ⑥导入前再查 Zotero 全库 ⑦DOI/PMID 同=判重、仅标题similar=疑似只标记 ⑧命中0 区分无新文/刊名错配 ⑨部分成功可只重试失败项 ⑩异常关闭不默认成功、重启按 Zotero 实况恢复 ⑪锚点只在 POST 成功后前移 ⑫retmax=1000 自动分窗 ⑬网络/Token 失败优雅报错、锚点不动 ⑭回填输入校验 ⑮单飞锁 ⑯collection 不存在→受控自动创建（停下、显示拟建名/父级/[TA]、确认后才建、禁静默）。

## 7. 分片（主驾按此逐片指挥+审）
- **Slice 1（现在建）**：项目起得来（venv 里 `python gui.py` 起窗）+ 采集台页 + 左导航 + `run_search` 桥（真 spawn 引擎、真 parse JSON）+ 采集最新「检索」→审计页渲染**真实结果**。dry-run only、无 -Execute、无写回；护栏仅基础（运行中禁按钮 + pubtype 至少一个 + 检索走线程不卡 UI）。左树静态胸外 10。
- Slice 2：全 74 刊载入 + 配置写回 journal-overrides.json + 窗口从台账算 + 回填历史 + 护栏④⑤⑧⑬⑭
- Slice 3：真实导入路径 + 受控建 collection⑯ + 回执/部分成功/重试⑨/崩溃恢复⑩/单飞锁⑮/锚点⑪/分窗⑫
- Slice 4：PyInstaller 打包 + VBS 启动器 + README + 图标

## 8. 严禁
- 不改 `D:\mecha-quant`、不改 `D:\BaiduSyncdisk\Mecha-Core`（只读参照 / 只读调用引擎）
- 不重写引擎为 Python（一律 spawn PS）
- Slice 1 禁 `-Execute` / 任何真实 Zotero 写入
- 不引 CDN；App 除引擎负责的 PubMed/Zotero 外不自行联网

## 9. 失败处理 & 每片产出
- 预期外即停、如实报卡点原文 + 你的定位；不擅自扩范围、不碰引擎/mecha-quant/Mecha-Core
- 每片交付：能起窗运行的项目 + `BUILD-NOTES.md`（起动步骤 + 各功能实现位置 + 桩点清单）
- **建完必须自己在 venv 里真跑起来验证**（不是只写代码）：起窗成功 + 点检索真拿到 JSON 真渲染
