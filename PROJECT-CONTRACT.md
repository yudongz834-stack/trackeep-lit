# Trackeep Lit — 项目合同（PROJECT-CONTRACT）

> 母法：《AI-Agent 软件生产规范》v1.1.2（`D:\dev\trackeep-design\AI-Agent软件生产规范-v1.1-定稿.md`）。
> 本文件是附录 A 在本项目的实例化（应然层）。机器版义务清单见 `.project/policy.yaml`；
> 实然状态见 `.project/manifest.yaml`；不变量/脆弱场景/例外见 `.project/` 同名文件。
> 与母法出入一律以母法为准。本合同不改母法条款，只填入本项目实际值。

## 0. 项目定位（指针，不复制）

Trackeep Lit（原 mecha-lit/机甲文献，2026-07-18 品牌重构）是 PI 的医学文献素材库桌面进料端：
选刊 → PubMed 检索 → Zotero 全库去重预览 → 一键导入。自身只管界面与编排，检索/导入引擎
spawn 调用 Mecha-Core 的 `zotero-import.ps1`（只读调用，绝不改引擎）。详见：

- [README.md](./README.md) — 软件骨架、功能、依赖、目录结构
- [CLAUDE.md](./CLAUDE.md) — 项目纪律、红线、不走回头路（已踩坑固化决策）
- [阶段日志.md](./阶段日志.md) — 当前活跃状态、阶段路线图、调整记录

## 1. 分级（PI 2026-07-18 拍板：S1 / R1 / C1）

| 轴 | 等级 | 判级三问与依据 |
|---|---|---|
| 规模 S | **S1** | 个人长期使用的单机桌面工具（PI 自用采集 GUI） |
| 风险 R | **R1** | 判级三问：①不可逆动作？导入可逆（Zotero 回收站）、台账/配置为本地 JSON 可恢复，无资金、无 PHI（文献元数据是公开出版物）②真实数据与密钥？有——Zotero API 写凭证 + PI 核心文献库 ③对外？否。失败后果=错误结果/有限数据损失（错误导入可撤、漏采可回填）→ R1。**R2 论点已暴露**（文献库批量污染清理成本 + 持写凭证），PI 裁定 R1；若数据面/凭证面扩大按母法 4.6 重评 |
| 商业 C | **C1** | 项目所有者自己长期使用，不对外交付/收费 |

## 2. 验收标准（每改动照做；CI 四门禁：governance / tests / secret-scan / evidence）

- 本地两件套全绿：`venv\Scripts\python.exe tests\smoke_test.py` 与 `tests\gui_test.py`
- CI 门禁绿：`.github/workflows/quality-gates.yml` 全 job 绿
- **B0 缺陷清零**（母法 8.1/8.6）
- 阶段日志已更新（刷新「当前活跃状态」+ 追加调整记录）
- 适用不变量未被破坏（`.project/invariants.yaml`）

## 3. 变更类型 → 门禁子集（引用母法 4.7，不复制正文）

本次（v0.2.0）变更类型 = **新功能（品牌重构 + 生产规范落地 + 测试两件套 + CI）**；
启用门禁 = 新功能全套：两件套全量 + CI 首跑绿。此后各变更类型（缺陷修复/新功能/
配置依赖/架构/紧急修复）的门禁子集一律引用母法 4.7 原文。本项目无数据迁移面（无自有 Schema）。

## 4. 预算与熔断（母法 10.2 / 附录 A.3）

- 单任务重试上限：**3 次**
- 连续失败转根因分析阈值：**3 次**（同一处修 3 次不绿即停步报告，不盲目试错）
- 模型额度：各家订阅内（GLM 走订阅、Claude/GPT 走订阅、DeepSeek 复筛按量 Flash 计费）；超出须 PI 批准
- 派遣量：不超过主驾能独立审核的量（主驾保持全局理解，不做盖章机）
- 超限处理：运行环境强制停止、保留现场、按母法 10.2 上报

## 5. 应急预授权（母法 3.3，执行后 24 小时内补报 PI）

以下具名动作视为 PI 事前批准，仅在约定触发条件/对象/范围/有效期内生效，超出任一边界回归母法 3.4 停止确认：

1. **回滚至上一稳定 commit**（触发：改动致 main 红 / 起窗即崩）
2. **误导入批次移入 Zotero 回收站**（触发：确认某批次导入错对象/错窗口；限该 batch 条目、可逆、回收站保留）

## 6. 隔离环境认定（母法 3.1）

已认定模板（按本合同登记模板创建即视为已认定，Agent 可自主创建/销毁）：

- **GitHub Actions runner**（ubuntu-latest）：CI 测试/证据环境，无 Zotero 凭证、无真实文献库、可完整重建
- **本地离屏测试环境**：`QT_QPA_PLATFORM=offscreen` + `TRACKEEP_SELFTEST=1`（+ CI 时 `TRACKEEP_CI=1` 跳过联网并计数）——不弹模态框、不触真实引擎写路径（测试内引擎 spawn 一律 mock）
- **git worktree 镜像**：隔离工作区做并行写改动，主驾合并

新型环境须先经质量责任方认定，登记于本节。

## 7. 测试缺省值调整（低于稳定优先档处，逐条记理由）

> 稳定优先档见母法附录 A.2。以下照搬 Trackeep Quant 同款方子（PI 2026-07-18 随分级决策批准）。
> 判定「不适用」（非降低）按母法 2.4 由质量责任方判定、一句话记理由。机器版见 policy.yaml `test_defaults`。

| 项 | 稳定优先档 | 本项目 | 理由 |
|---|---|---|---|
| 并发类重复 | 门禁内 ≥50 次 | **≥50 次**（2026-07-18 升档回母法档，`tests/stress_test.py`；原 ≥10 调整注销） | 加严不需批准（母法 3.2） |
| 全量回归节律 | 每夜 | **CI 每推 + 每改动本地两件套** | 个人项目、笔记本非常开机（EX-03） |
| 每夜并发≥500 / 每周 soak≥8h | 适用 | **不适用** | 无服务端常驻、用完即关 |
| 备份恢复演练 | 每月或每发布周期 | **不适用** | App 零自有数据存储：文献库在 Zotero 云端、台账/配置在 Mecha-Core 同步盘（policy R1-01） |
| 变异测试 | R2 以上周期性 | **不适用** | R1 非母法 7.7 强制面 |

**列入 manifest 待办、不虚标为已达成**：UI 随机事件风暴（BL-02，目标 v0.3；连点/竞态已由
stress_test 覆盖，真随机序列风暴未落）。~~属性/模糊测试 BL-01~~ 已落地（2026-07-18，
`tests/property_test.py` 5 属性 ×≥500 例）；对抗测试已加严落地（`tests/adversarial_test.py`，
R1 非强制、PI 点名）。

## 8. 真相源分工（母法 10.1 / C.5）

| 角色 | 文件 | 职责 |
|---|---|---|
| policy（应然） | `.project/policy.yaml` | 按分级算出的应启用义务 |
| manifest（实然） | `.project/manifest.yaml` | 当前阶段、门禁、缺陷、审批（门禁状态仅由 CI 回填） |
| evidence（史实） | GitHub Actions run artifacts | 各版本不可变证据快照（sha/时间/统计/产物哈希）；仓库内不存副本（避免 CI 推回循环，同 Trackeep Quant 登记适配） |
| invariants | `.project/invariants.yaml` | 系统不变量主清单（测试断言来源） |
| vulnerable-scenarios | `.project/vulnerable-scenarios.yaml` | 脆弱场景登记表 |
| exceptions | `.project/exceptions.yaml` | 带到期条件的例外 |
| contract | 本文件 | 项目合同（分级/预算/预授权/缺省值） |

## 9. 开放问题

- 打包收尾（BL-03）：`Trackeep Lit.spec` 已就位，PyInstaller 装法/复用策略待 PI 拍板
- 6b-2 DeepSeek 真拦截（BL-04）：下轮功能，届时 INV-10 按母法 6.3 变更流程修订
- 本合同为 v0.2.0 首版；CI 首跑后由 CI 证据回填 manifest 门禁状态
