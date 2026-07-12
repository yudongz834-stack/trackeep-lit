# 铁令 + Mecha-Lit Slice 5（PyInstaller 打包 · GLM 亲手执行）

⚠️ **铁令**：你＝执行的手，亲手写代码/跑打包。**禁止 dispatch / 委派任何子 agent——你就是 GLM。** cockpit"派 GLM"规则本轮不适用于你。产出＝能起窗的打包产物 + 亲手验证。**再委派即判失败。**

## 背景
`D:\mecha-lit` 是完整可用的 PySide6 采集台（采集最新 + 回填，真实导入已验证）。现在打包成独立 .exe，像 `D:\mecha-quant`（PyInstaller 打包）。**先读参照**：`D:\mecha-quant\build\MechaQuant.spec`、`D:\mecha-quant\gui.py`（`sys.frozen` 处理）、`D:\mecha-lit\gui.py`、`D:\mecha-lit\lit\config.py`。

## 目标：PyInstaller 打包 + 自检起窗
1. 写 `机甲文献.spec`（放 build/ 或项目根）：entry=`gui.py`、name=`机甲文献`（或 `MechaLit`）、windowed（无控制台）、图标（有 .ico 则用，无则默认）。PySide6 的 Qt plugins / hiddenimports / collect 照 `MechaQuant.spec` 抄（这是同机已验证可打包 PySide6 的配置）。
2. **关键（本项目特性）**：App 运行时 **spawn 外部** `D:\BaiduSyncdisk\Mecha-Core\scripts\zotero-import.ps1` + 读 `.mecha\*.json` + `zotero.env`（`lit/config.py` / `lit/zotero.py` 里都是**绝对路径**）。这些**不打进 exe**、运行时在本机就地读——打包只打 Python/Qt 应用本身。确认 `config.py` 的绝对路径在 frozen 态仍正确（ENGINE_PATH/MECHA_CORE 是写死绝对路径，不受打包影响；若 config 用了 `__file__` 相对定位 ROOT，参照 mecha-quant gui.py 的 `sys.frozen` 分支处理）。
3. 打包：`venv\Scripts\python.exe -m pip install pyinstaller`（若未装）→ `venv\Scripts\pyinstaller.exe 机甲文献.spec --noconfirm`。
4. **自检起窗**（像 mecha-quant）：`set MECHA_SELFTEST=1 && "dist\机甲文献\机甲文献.exe"` → exit 0 = 打包产物能拉起整个界面（gui.py 已有 MECHA_SELFTEST 3 秒自退，确认打包后仍生效）。

## 严禁
- 不改 mecha-quant / Mecha-Core。**不真跑 -Execute / 不真写 Zotero**（打包 + 起窗自检不碰导入按钮）。
- 打包产物放本项目 build/dist，别外溢。加 `dist/`、`build/`、`*.spec` 之外的产物到 `.gitignore`（dist/build 别提交，太大）。

## 卡点预案（PyInstaller 常见，别硬耗）
- 缺 Qt platform plugin → spec 里 `collect_all("PySide6")` 或加 hiddenimports/datas（照 MechaQuant.spec）。
- exe 启动即崩 → 贴 MECHA_SELFTEST 运行的报错原文 + 你的定位；本项目内能修则修，修不动（环境级）则停下如实报——打包偶尔需手调，报清楚即可。

## 回执（≤400字）
①`机甲文献.spec` 写好 ②pyinstaller 打包成功？（dist 产物路径 + 大小）③`MECHA_SELFTEST` 起窗自检 exit 码 ④卡点（贴报错原文）。亲手做，禁委派，禁真写。
