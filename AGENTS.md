# Trackeep Lit — Agent 运行入口（AGENTS.md）

本文件是 Agent 在本仓的**规范流程入口**（母法附录 C.2 形制）。与 [CLAUDE.md](./CLAUDE.md) 分工：
**AGENTS.md = 生产规范流程入口；CLAUDE.md = 项目纪律与已踩坑固化决策**。二者互指不重复。
任何 Agent（Claude / GLM / Codex / 其他）开工先读本文件 + [PROJECT-CONTRACT.md](./PROJECT-CONTRACT.md) + CLAUDE.md。

## 0. 母法与合同位置

- **母法**：《AI-Agent 软件生产规范》**v1.1.2**
  `D:\dev\trackeep-design\AI-Agent软件生产规范-v1.1-定稿.md`（核心规范单一权威版本）
- **项目合同**：[PROJECT-CONTRACT.md](./PROJECT-CONTRACT.md)（分级 S1/**R2**/C1 / 预算 / 预授权 / 测试缺省值；R1→R2 PI 2026-07-18 拍板）
- **机器清单**：`.project/manifest.yaml`（实然，门禁状态仅由 CI 回填）
- **义务/不变量/脆弱场景/例外**：`.project/policy.yaml` / `invariants.yaml` / `vulnerable-scenarios.yaml` / `exceptions.yaml`

## 1. 红线（内联副本，来源母法 v1.1.2 §3.4 / §3.5；与母法出入一律以母法为准）

> 以下红线全文内联自母法 v1.1.2，因违反成本灾难性、每个任务都适用，不容"未加载相关文件"这种失败模式（母法 C.1 唯一允许的内联例外）。

**§3.4 必须停止并取得批准的操作：**
* 删除、覆盖或不可逆修改真实用户数据、原始数据或历史记录
* 在隔离环境之外执行无法可靠回滚的操作
* 修改操作系统、驱动、注册表、全局环境或项目边界外的重要资源
* 使用生产、支付、个人高权限或未经批准的凭证
* 超出预授权预算或新增付费服务
* 上传或外发患者数据、隐私数据、商业机密等敏感信息
* 修改生产数据库或生产环境
* 合并受保护的稳定分支
* 正式向外发布
* 收费、签署合同或作出商业承诺
* 作出需要人类承担医疗、金融或法律责任的最终决定
* 目标存在根本冲突且无法合理裁决

**§3.5 不适用例外的事项（不得通过例外机制绕过）：**
* 真实数据和敏感数据红线
* 隔离环境之外的不可逆操作红线
* 生产环境与正式发布授权
* 未关闭的 B0 缺陷
* 法律或监管明确禁止的行为

## 2. 本项目红线（浓缩自 CLAUDE.md「红线」节；细节以 CLAUDE.md 为准）

1. **不改 Mecha-Core**：引擎 `zotero-import.ps1` 只读 spawn 调用，绝不重写为 Python；台账 `zotero-import-ledger.json` 只读（锚点只归引擎前移）。`journal-overrides.json` / `strategy.json` 是本 App 的可写配置（原子写）。
2. **dry-run 绝不 `-Execute`**：真实写 Zotero 只能由用户点「导入」+ 确认框触发（INV-01/02）；受控建 collection 必须确认、禁静默。
3. **凭证不外泄**：`zotero.env` / `DEEPSEEK_TOKEN` 只进请求头——不 print、不落日志、不进异常文本、不进 git（INV-08）。
4. **JSON 契约是接线真相**：`TRACKEEP_JSON` 前缀行 + schema `trackeep-lit/import-result@1`（2026-07-18 PI 拍板 wire 层随品牌全迁——引擎与 App 两端原子切换，无兼容包袱）。
5. **PI 不写代码**：注释 / 文档 / 界面文案全中文人话。

## 3. 本项目自主清单 / 必停清单（裁剪自母法 §3.2 / §3.4）

**可自主（隔离环境内 / 项目边界内）：** 读/分析项目；改项目内代码；跑命令/测试/构建；
mock 引擎与合成回执数据（测试内一律 mock spawn，不触真实 PubMed/Zotero 写路径）；
装/升项目级依赖（venv 内）；提测试强度、加护栏、登记脆弱场景（加严不请示）；
git 开发提交与 push（单执行体纪律，见 EX-01）；应急预授权内动作（回滚上一稳定 commit /
误导入批次移回收站——执行后 24h 内补报 PI）。

**必停请示（§3.4 + 本项目红线）：** 任何真实 `-Execute` 导入 / 真建 collection（属真实用户数据写，
测试与施工中一律禁；日常使用由 PI 在界面上自行触发）；改 Mecha-Core 任何文件；改引擎 JSON 契约
（=改结论口径，须与引擎侧同步、PI 拍板）；force-push main（禁）；外发含凭证/完整文献库数据的材料。

## 4. CI 与证据位置

- **机器门禁**：`.github/workflows/quality-gates.yml`（governance / tests / secret-scan / evidence 四 job；任一红=发布阻断）
- **证据**：GitHub Actions run artifacts `evidence-<sha>`（evidence.json：commit sha、时间、Python 版本、测试统计、TRACKEEP_CI 跳过计数、产物哈希、lock_hash）。仓库内不存副本
- **测试**：`tests/smoke_test.py`（离线，逻辑全链路，引擎 mock）+ `tests/gui_test.py`（离屏，界面交互）；CI 下 `TRACKEEP_CI=1` 跳过联网并计数
- **脏数据**：tests 内合成（BOM / 半截 JSON / 空文件 / 畸形回执样本），门禁内必过

## 5. 质量复核方式（母法 §8.5）

独立复核 = 全新会话/隔离上下文、不继承施工结论、仅依据合同+仓库+证据、不参与被审版本设计施工、条件允许用异构模型。
**R2 项目**：写审分离必守（施工方自报不作数，主驾新眼睛独立跑验证）；**每候选版本一轮独立复核 +
一轮对抗性测试**（7.5，adversarial_test 常驻 CI + 每候选版本追加新变体）；变异测试每发布周期一轮
（BL-08）。分支保护为例外 EX-01（2026-07-18 实测双路 403 付费墙），由「CI 每推必跑 + 红灯阻断 +
单执行体不 force-push main」补偿。
