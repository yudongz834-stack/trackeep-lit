# -*- coding: utf-8 -*-
"""冒烟测试：全离线，断言 lit/ 离线逻辑链路不变量。

断言来源：.project/invariants.yaml（INV-01~11）+ .project/vulnerable-scenarios.yaml。
绝不联网、绝不真 spawn 引擎、绝不读写 Mecha-Core 真实文件——所有 json/md/台账一律
patch 模块级 *_PATH 常量到 tests/_tmp_* 临时文件，脚本末尾自清理。

运行：venv\\Scripts\\python.exe tests\\smoke_test.py
"""
import json
import os
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

_TMPDIR = Path(__file__).resolve().parent / "_tmp_smoke"
_TMPDIR.mkdir(exist_ok=True)

from lit import config, deepseek, engine, journals, ledger, overrides, strategy, zotero  # noqa: E402

checks = []


def check(name: str, cond: bool, extra: str = "") -> None:
    checks.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {extra}")


def _tmp(name: str) -> Path:
    """tests/_tmp_smoke/<name>：测试自管的临时路径（gitignore 覆盖 tests/_tmp_*）。"""
    p = _TMPDIR / name
    p.unlink(missing_ok=True)
    return p


class _Patch:
    """简单的属性补丁上下文：进入记旧值、退出还原。"""

    def __init__(self, obj, name, val):
        self.obj, self.name, self.val = obj, name, val
        self.old = getattr(obj, name)

    def __enter__(self):
        setattr(self.obj, self.name, self.val)
        return self

    def __exit__(self, *_):
        setattr(self.obj, self.name, self.old)


# ============================ 引擎桥（mock subprocess.run） ============================

class _FakeSpawn:
    """假 subprocess.run：截获 argv/kwargs，返回合成 CompletedProcess（或抛异常）。

    run_search / run_import 不该真起进程——这里把 engine.subprocess.run 换成可控桩，
    既能验 argv 构造（dry-run 不带 -Execute / 导入带 -Execute / CREATE_NO_WINDOW），
    也能注入失败（非零退出 / 无 TRACKEEP_JSON / 超时 / 找不到 PowerShell）。
    """

    def __init__(self, stdout="", returncode=0, stderr="",
                 raise_exc=None, payload=None):
        self.calls = []                       # [(argv, kwargs)]
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr
        self.raise_exc = raise_exc
        # payload：直接合成 TRACKEEP_JSON 行（优先于 stdout）
        if payload is not None:
            self.stdout = "一些噪声行\nTRACKEEP_JSON %s\n收尾噪声" % json.dumps(payload, ensure_ascii=False)

    def __call__(self, argv, **kwargs):
        self.calls.append((list(argv), dict(kwargs)))
        if self.raise_exc is not None:
            raise self.raise_exc
        return subprocess.CompletedProcess(args=argv, returncode=self.returncode,
                                           stdout=self.stdout, stderr=self.stderr)


# 引擎路径预检在 argv 构造之前——argv/窗口校验类测试需要一个「存在」的引擎路径
_EXISTING_ENGINE = _tmp("fake_engine.ps1")
_EXISTING_ENGINE.write_text("# fake engine for argv tests\n", encoding="utf-8")


def _patch_engine(fake):
    """同时补 config.ENGINE_PATH（指向存在的假脚本）与 subprocess.run。"""
    return (_Patch(config, "ENGINE_PATH", _EXISTING_ENGINE),
            _Patch(engine.subprocess, "run", fake))


# --- INV-01：dry-run 不带 -Execute；导入带 -Execute ---
fake = _FakeSpawn(payload={"found": 3, "counts": {"new": 1, "dup": 1, "suspect": 1}})
with _Patch(config, "ENGINE_PATH", _EXISTING_ENGINE), \
        _Patch(engine.subprocess, "run", fake):
    engine.run_search("J Thorac Oncol", reldate_days=30)
    argv_search = fake.calls[-1][0]
    kwargs_search = fake.calls[-1][1]
    engine.run_import("J Thorac Oncol", reldate_days=30)
    argv_import = fake.calls[-1][0]

check("INV-01: run_search argv 含 -EmitJson",
      "-EmitJson" in argv_search)
check("INV-01: run_search argv 不含 -Execute（dry-run 零副作用）",
      "-Execute" not in argv_search, "(argv=%s)" % argv_search)
check("INV-01: run_import argv 含 -Execute（真写）",
      "-Execute" in argv_import)
check("INV-01: 两入口都带 -Journal 与刊名",
      "-Journal" in argv_search and "J Thorac Oncol" in argv_search
      and "J Thorac Oncol" in argv_import)
check("INV-01: 窗口参数 reldate→-ReldateDays",
      "-ReldateDays" in argv_search and "30" in argv_search)

# --- 6b-2：run_import 的 exclude_pmids → -ExcludePmids argv（向后兼容 + 门控）---
fake = _FakeSpawn(payload={"found": 0})
with _Patch(config, "ENGINE_PATH", _EXISTING_ENGINE), \
        _Patch(engine.subprocess, "run", fake):
    # 传 exclude_pmids → argv 含 -ExcludePmids "a,b"（仅 -Execute 路径有意义）
    engine.run_import("J Thorac Oncol", reldate_days=30, exclude_pmids=["a", "b"])
    argv_excl = fake.calls[-1][0]
    # 不传 / None → argv 不含 -ExcludePmids（向后兼容 6b-1）
    engine.run_import("J Thorac Oncol", reldate_days=30)
    argv_noexcl = fake.calls[-1][0]
    engine.run_import("J Thorac Oncol", reldate_days=30, exclude_pmids=None)
    argv_none = fake.calls[-1][0]
    engine.run_import("J Thorac Oncol", reldate_days=30, exclude_pmids=set())
    argv_empty = fake.calls[-1][0]
    # run_search 永不含 -ExcludePmids（dry-run 不导入、不门控）
    engine.run_search("J Thorac Oncol", reldate_days=30)
    argv_search_nx = fake.calls[-1][0]
check("6b-2: run_import(exclude_pmids) → argv 含 -ExcludePmids",
      "-ExcludePmids" in argv_excl, "(argv=%s)" % argv_excl)
check("6b-2: exclude 值为逗号拼接",
      "a,b" in argv_excl, "(值=%s)" % [a for i, a in enumerate(argv_excl) if i and argv_excl[i-1] == '-ExcludePmids'])
check("6b-2: run_import 不传 exclude → argv 不含 -ExcludePmids（向后兼容）",
      "-ExcludePmids" not in argv_noexcl)
check("6b-2: run_import(exclude=None) → argv 不含 -ExcludePmids",
      "-ExcludePmids" not in argv_none)
check("6b-2: run_import(exclude=set()) → argv 不含 -ExcludePmids（空集不门控）",
      "-ExcludePmids" not in argv_empty)
check("6b-2: run_search 永不含 -ExcludePmids（dry-run 无门控）",
      "-ExcludePmids" not in argv_search_nx)

# --- VS-04：spawn 含 CREATE_NO_WINDOW ---
check("VS-04: kwargs 含 creationflags",
      "creationflags" in kwargs_search)
_no_win = getattr(subprocess, "CREATE_NO_WINDOW", 0)
if sys.platform == "win32":
    check("VS-04: creationflags 含 CREATE_NO_WINDOW 位（灭 PowerShell 弹窗）",
          _no_win and (kwargs_search.get("creationflags", 0) & _no_win) == _no_win,
          "(flag=0x%x)" % kwargs_search.get("creationflags", 0))
else:
    # 非 Windows（CI ubuntu）无 CREATE_NO_WINDOW：产品用 getattr 兜底 0，是正确降级
    check("VS-04: 非 Windows 平台 creationflags 兜底 0（getattr 降级）",
          kwargs_search.get("creationflags", 0) == 0,
          "(flag=%r)" % kwargs_search.get("creationflags", 0))

# --- 窗口参数分流（年/月）---
fake = _FakeSpawn(payload={"found": 0})
with _Patch(config, "ENGINE_PATH", _EXISTING_ENGINE), \
        _Patch(engine.subprocess, "run", fake):
    engine.run_search("J Thorac Oncol", month="2026-03")
    assert "-Month" in fake.calls[-1][0]
    engine.run_search("J Thorac Oncol", year=2025)
    assert "-Year" in fake.calls[-1][0]
check("窗口分流: month→-Month / year→-Year 均进 argv", True)

# --- TRACKEEP_JSON 解析（BOM + 杂行干扰）---
fake = _FakeSpawn(stdout="﻿PowerShell 启动噪声\n进度 1/3\nTRACKEEP_JSON "
                         '{"found": 7, "counts": {"new": 2}}\n尾噪声')
with _Patch(config, "ENGINE_PATH", _EXISTING_ENGINE), \
        _Patch(engine.subprocess, "run", fake):
    r = engine.run_search("J Thorac Oncol", reldate_days=30)
check("TRACKEEP_JSON 解析: BOM 前缀 + 杂行干扰仍取到正确行",
      r.get("found") == 7 and r.get("counts", {}).get("new") == 2)

# --- INV-03：失败注入逐类（绝不渲染成成功）---
def _expect_runtime(fake, needle, label):
    with _Patch(config, "ENGINE_PATH", _EXISTING_ENGINE), \
            _Patch(engine.subprocess, "run", fake):
        try:
            engine.run_search("J Thorac Oncol", reldate_days=30)
        except RuntimeError as e:
            check("INV-03: %s → RuntimeError 含「%s」" % (label, needle),
                  needle in str(e), "(%s)" % str(e)[:60])
        except Exception as e:
            check("INV-03: %s → RuntimeError" % label, False,
                  "(抛了 %s 而非 RuntimeError)" % type(e).__name__)
        else:
            check("INV-03: %s → RuntimeError" % label, False, "(没抛异常！)")

_expect_runtime(_FakeSpawn(returncode=42), "42", "非零退出码")
_expect_runtime(_FakeSpawn(stdout="只有噪声，没有 JSON 行"), "TRACKEEP_JSON", "stdout 无 TRACKEEP_JSON")
_expect_runtime(_FakeSpawn(raise_exc=subprocess.TimeoutExpired(cmd=["powershell"], timeout=180)),
                "超时", "TimeoutExpired")
_expect_runtime(_FakeSpawn(raise_exc=FileNotFoundError(2, "找不到 powershell")),
                "PowerShell", "FileNotFoundError")

# 引擎脚本不存在 → 人话（spawn 前预检）
_missing_engine = _tmp("no_such_engine.ps1")   # 不创建即「不存在」
with _Patch(config, "ENGINE_PATH", _missing_engine):
    try:
        engine.run_search("J Thorac Oncol", reldate_days=30)
    except RuntimeError as e:
        check("INV-03: 引擎缺失 → RuntimeError 含「引擎脚本未找到」",
              "引擎脚本未找到" in str(e))
    else:
        check("INV-03: 引擎缺失 → RuntimeError", False)

# --- 窗口三选一校验：0 个或 ≥2 个模式参数 → ValueError ---
with _Patch(config, "ENGINE_PATH", _EXISTING_ENGINE), \
        _Patch(engine.subprocess, "run", _FakeSpawn(payload={"found": 0})):
    for label, kw in [("0 个模式", {}), ("2 个模式", dict(reldate_days=30, month="2026-01"))]:
        try:
            engine.run_search("J Thorac Oncol", **kw)
        except ValueError:
            check("窗口校验: %s → ValueError" % label, True)
        except Exception as e:
            check("窗口校验: %s → ValueError" % label, False,
                  "(抛了 %s)" % type(e).__name__)
        else:
            check("窗口校验: %s → ValueError" % label, False, "(没抛)")


# ============================ 配置层（patch *_PATH 到 temp） ============================

_ov_path = _tmp("overrides.json")
_st_path = _tmp("strategy.json")

# --- INV-07 overrides 往返：改一刊不伤其它刊；全默认删条目；文件合法 JSON ---
with _Patch(overrides, "OVERRIDES_PATH", _ov_path):
    overrides.save("J Thorac Oncol", {"includeEditorial": True, "includeLetter": False,
                                      "topicFilter": None})
    overrides.save("Lung Cancer", {"includeEditorial": False, "includeLetter": True,
                                   "topicFilter": None})
    d = overrides.load_all()
    check("INV-07 overrides: 两刊并存",
          len(d) == 2 and d["J Thorac Oncol"].get("includeEditorial") is True
          and d["Lung Cancer"].get("includeLetter") is True)
    check("INV-07 overrides: 只存与默认不同字段",
          "includeLetter" not in d["J Thorac Oncol"]   # False=默认，不落
          and "includeEditorial" not in d["Lung Cancer"])
    # 写回全默认 → 该刊条目删除，其它刊保留
    overrides.save("J Thorac Oncol", {"includeEditorial": False, "includeLetter": False,
                                      "topicFilter": None})
    d2 = overrides.load_all()
    check("INV-07 overrides: 写回默认删条目 + 其它刊保留",
          "J Thorac Oncol" not in d2 and "Lung Cancer" in d2)
    raw = _ov_path.read_text(encoding="utf-8-sig")
    json.loads(raw)   # 不抛即合法 JSON
    check("INV-07 overrides: 落盘文件是完整合法 JSON", True)

# --- INV-07 strategy 往返：改一分类不丢 version 与其它分类 ---
with _Patch(strategy, "STRATEGY_PATH", _st_path):
    strategy.save_category("胸部肿瘤与胸外科",
                           {"editorial": True, "letter": False,
                            "topicFilter": {"enabled": True, "terms": "lung[tiab]"},
                            "deepseek": {"enabled": False, "criteria": ""}})
    strategy.save_category("临床医学综合",
                           {"editorial": False, "letter": True,
                            "topicFilter": {"enabled": False, "terms": ""},
                            "deepseek": {"enabled": True, "criteria": "综合判据"}})
    sd = strategy.load()
    check("INV-07 strategy: 两分类并存 + version 保留",
          sd.get("version") == 1
          and "胸部肿瘤与胸外科" in sd["categories"]
          and "临床医学综合" in sd["categories"])
    # 再改一分类 → 另一分类与 version 仍保留
    strategy.save_category("胸部肿瘤与胸外科",
                           {"editorial": False, "letter": False,
                            "topicFilter": {"enabled": False, "terms": ""},
                            "deepseek": {"enabled": False, "criteria": ""}})
    sd2 = strategy.load()
    check("INV-07 strategy: 改一分类不丢另一分类 + version",
          sd2.get("version") == 1 and "临床医学综合" in sd2["categories"]
          and sd2["categories"]["临床医学综合"]["deepseek"]["criteria"] == "综合判据")

# --- VS-01 脏数据：BOM 可读 / 半截 JSON / 空文件全部优雅回退，不崩 ---
_ov_dirty = _tmp("overrides_dirty.json")
with _Patch(overrides, "OVERRIDES_PATH", _ov_dirty):
    # BOM 前缀 JSON：utf-8-sig 读得回
    _ov_dirty.write_bytes(b"\xef\xbb\xbf" + '{"J Thorac Oncol": {"includeEditorial": true}}'.encode("utf-8"))
    check("VS-01 overrides: BOM 前缀 JSON 可读",
          overrides.load_all().get("J Thorac Oncol", {}).get("includeEditorial") is True)
    _ov_dirty.write_text("{这不是合法的json", encoding="utf-8")
    check("VS-01 overrides: 半截 JSON → 空字典不崩", overrides.load_all() == {})
    _ov_dirty.write_text("", encoding="utf-8")
    check("VS-01 overrides: 空文件 → 空字典不崩", overrides.load_all() == {})

_st_dirty = _tmp("strategy_dirty.json")
with _Patch(strategy, "STRATEGY_PATH", _st_dirty):
    _st_dirty.write_text("{broken", encoding="utf-8")
    check("VS-01 strategy: 半截 JSON → 默认骨架不崩",
          strategy.load() == {"version": 1, "categories": {}})
    _st_dirty.write_text("", encoding="utf-8")
    check("VS-01 strategy: 空文件 → 默认骨架不崩",
          strategy.load() == {"version": 1, "categories": {}})

# --- resolve 合并契约（单刊显式 > 分类默认；topicFilter enabled 出 terms；deepseek 透传）---
# 合成期刊表：胸部肿瘤与胸外科 2 刊 + 临床医学综合 1 刊
_jt = _tmp("journal_table.md")
_jt.write_text(
    "| 来源分类 | 期刊全名 | PubMed缩写 | 推荐目录名 | 备注 |\n"
    "|---|---|---|---|---|\n"
    "| 胸部肿瘤与胸外科 | 胸科某刊 | J Thorac Oncol | J Thorac Oncol | 备注1 |\n"
    "| 胸部肿瘤与胸外科 | 另一本 | Ann Thorac Surg | Ann Thorac Surg | x |\n"
    "| 临床医学综合 | 综合一 | NEJM | N Engl J Med | y |\n"
    "| 杂表标题 | a | b |\n",           # <5 列杂表行（3 个 |）→ 自然被跳过
    encoding="utf-8")
_ov_res = _tmp("overrides_resolve.json")
_st_res = _tmp("strategy_resolve.json")
with _Patch(journals, "JOURNAL_TABLE", _jt), \
        _Patch(overrides, "OVERRIDES_PATH", _ov_res), \
        _Patch(strategy, "STRATEGY_PATH", _st_res):
    # 分类策略：editorial 关、topicFilter 开、deepseek 开
    strategy.save_category("胸部肿瘤与胸外科",
                           {"editorial": False, "letter": False,
                            "topicFilter": {"enabled": True, "terms": "lung[tiab]"},
                            "deepseek": {"enabled": True, "criteria": "主体聚焦肺癌"}})
    # 单刊显式例外：Ann Thorac Surg 开 editorial
    overrides.save("Ann Thorac Surg", {"includeEditorial": True, "includeLetter": False,
                                       "topicFilter": None})
    r1 = strategy.resolve("J Thorac Oncol")
    check("resolve: 分类默认 editorial=False 生效", r1["editorial"] is False)
    check("resolve: 分类 topicFilter enabled → resolve 出 terms",
          r1["topic"] == "lung[tiab]")
    check("resolve: deepseek_enabled 透传", r1["deepseek_enabled"] is True)
    check("resolve: deepseek_criteria 透传", r1["deepseek_criteria"] == "主体聚焦肺癌")
    r2 = strategy.resolve("Ann Thorac Surg")
    check("resolve: 单刊显式 editorial 优先于分类默认",
          r2["editorial"] is True, "(单刊覆盖分类 False)")
    # 单刊显式 topicFilter 覆盖分类
    overrides.save("Ann Thorac Surg", {"includeEditorial": True, "includeLetter": False,
                                       "topicFilter": "esophag*[tiab]"})
    r3 = strategy.resolve("Ann Thorac Surg")
    check("resolve: 单刊显式 topicFilter 优先", r3["topic"] == "esophag*[tiab]")

# --- per-journal deepseek override（三态 × 判据矩阵 + 默认全开 + 往返 + 畸形回落）---
# 复用上面的 _jt / _ov_res / _st_res（已 patch 到临时路径）。
with _Patch(journals, "JOURNAL_TABLE", _jt), \
        _Patch(overrides, "OVERRIDES_PATH", _ov_res), \
        _Patch(strategy, "STRATEGY_PATH", _st_res):
    # 默认全开：CATEGORY_DEFAULT deepseek enabled=True（未配分类也默认开）
    check("默认全开: CATEGORY_DEFAULT deepseek enabled=True",
          strategy.CATEGORY_DEFAULT["deepseek"]["enabled"] is True)
    check("默认全开: 未配分类 get_category deepseek enabled=True",
          strategy.get_category("流行病学与公共卫生")["deepseek"]["enabled"] is True)
    # 配胸外 enabled=False（模拟 PI 显式关某分类）+ 分类判据，供下面三态矩阵参照
    strategy.save_category("胸部肿瘤与胸外科",
                           {"editorial": False, "letter": False,
                            "topicFilter": {"enabled": False, "terms": ""},
                            "deepseek": {"enabled": False, "criteria": "分类判据"}})
    # 三态 × 判据矩阵：(override, expected_enabled, expected_criteria, label)
    matrix = [
        ({"enabled": None, "criteria": None}, False, "分类判据",
         "inherit：开/关随分类（关）+ 判据继承分类"),
        ({"enabled": True, "criteria": None}, True, "分类判据",
         "force-on：本刊强制开 + 判据继承分类"),
        ({"enabled": False, "criteria": None}, False, "分类判据",
         "force-off：本刊强制关 + 判据继承分类"),
        ({"enabled": None, "criteria": "本刊判据"}, False, "本刊判据",
         "inherit enabled + 自定义判据：开关随分类、判据用本刊"),
        ({"enabled": True, "criteria": "本刊判据"}, True, "本刊判据",
         "force-on + 自定义判据"),
    ]
    for ov, exp_en, exp_cr, label in matrix:
        overrides.save("J Thorac Oncol", {"includeEditorial": False, "includeLetter": False,
                        "topicFilter": None, "deepseek": ov})
        r = strategy.resolve("J Thorac Oncol")
        check("resolve deepseek 三态×判据: %s" % label,
              r["deepseek_enabled"] is exp_en and r["deepseek_criteria"] == exp_cr,
              "(got en=%r cr=%r)" % (r["deepseek_enabled"], r["deepseek_criteria"]))
    # override 往返：save → load_all → resolve（他刊不丢）
    overrides.save("Ann Thorac Surg", {"includeEditorial": False, "includeLetter": False,
                    "topicFilter": None, "deepseek": {"enabled": True, "criteria": "ATS判据"}})
    d = overrides.load_all()
    check("override 往返: deepseek 段落盘 + 他刊并存",
          isinstance(d.get("Ann Thorac Surg", {}).get("deepseek"), dict)
          and d["Ann Thorac Surg"]["deepseek"]["enabled"] is True
          and d["Ann Thorac Surg"]["deepseek"]["criteria"] == "ATS判据"
          and "J Thorac Oncol" in d)
    r = strategy.resolve("Ann Thorac Surg")
    check("override 往返: resolve 取本刊强制开 + 自定义判据",
          r["deepseek_enabled"] is True and r["deepseek_criteria"] == "ATS判据")
    # 全默认 override（inherit + 空判据）→ 条目删除
    overrides.save("Ann Thorac Surg", {"includeEditorial": False, "includeLetter": False,
                    "topicFilter": None, "deepseek": {"enabled": None, "criteria": None}})
    check("override: 全默认（inherit + 空判据）→ 该刊条目删除",
          "Ann Thorac Surg" not in overrides.load_all())
    # 畸形单刊 deepseek override（手编 JSON 绕过 save 归一）→ resolve 安全回落分类、不抛
    for label, raw_ov, exp_en, exp_cr in [
        ("deepseek 非 dict", {"deepseek": "notadict"}, False, "分类判据"),
        ("deepseek null", {"deepseek": None}, False, "分类判据"),
        ("enabled 非 bool（criteria 合法）",
         {"deepseek": {"enabled": "yes", "criteria": "x"}}, False, "x"),
        ("criteria 非 str（enabled 合法）",
         {"deepseek": {"enabled": True, "criteria": 123}}, True, "分类判据"),
    ]:
        _ov_res.write_text(json.dumps({"J Thorac Oncol": raw_ov}, ensure_ascii=False),
                           encoding="utf-8")
        try:
            rr = strategy.resolve("J Thorac Oncol")
            check("resolve deepseek 畸形回落: %s" % label,
                  rr["deepseek_enabled"] is exp_en and rr["deepseek_criteria"] == exp_cr,
                  "(got en=%r cr=%r)" % (rr["deepseek_enabled"], rr["deepseek_criteria"]))
        except Exception as e:
            check("resolve deepseek 畸形回落: %s" % label, False,
                  "(%s: %s)" % (type(e).__name__, str(e)[:80]))

# --- ledger：合成台账（带 BOM）→ last_date 取最大；reldate_for=gap+30 夹 [7,400] ---
_led = _tmp("ledger.json")
with _Patch(ledger, "LEDGER_PATH", _led):
    today = date.today()
    batches = [
        {"journal": "J Thorac Oncol", "time": (today - timedelta(days=100)).isoformat()},
        {"journal": "J Thorac Oncol", "time": (today - timedelta(days=70)).isoformat()},  # 最大
        {"journal": "Lung Cancer", "time": (today - timedelta(days=10)).isoformat()},
        {"journal": "J Thorac Oncol", "time": "not-a-date"},   # 坏 time 被跳过
        {"journal": "J Thorac Oncol"},                          # 缺 time 被跳过
    ]
    # 用 utf-8-sig 写：模拟 PowerShell 引擎写的 BOM 台账
    _led.write_text(json.dumps({"batches": batches}, ensure_ascii=False),
                    encoding="utf-8-sig")
    check("ledger: last_date 取该刊最大 time（跳坏/缺）",
          ledger.last_date("J Thorac Oncol") == today - timedelta(days=70))
    days, last = ledger.reldate_for("J Thorac Oncol")
    check("ledger: reldate_for = gap(70)+30 夹 [7,400]",
          days == 100 and last == today - timedelta(days=70), "(days=%d)" % days)
    # 夹下限：gap 很小 → 仍 ≥ 7
    batches_clamp = [{"journal": "X", "time": (today - timedelta(days=1)).isoformat()}]
    _led.write_text(json.dumps({"batches": batches_clamp}, ensure_ascii=False),
                    encoding="utf-8-sig")
    check("ledger: gap+30 夹下限 7", ledger.reldate_for("X")[0] == 31)  # 1+30=31
    # 夹上限：gap 很大 → ≤ 400
    batches_max = [{"journal": "Y", "time": (today - timedelta(days=500)).isoformat()}]
    _led.write_text(json.dumps({"batches": batches_max}, ensure_ascii=False),
                    encoding="utf-8-sig")
    check("ledger: gap+30 夹上限 400", ledger.reldate_for("Y")[0] == 400)

# --- VS-01 ledger 脏数据：缺文件 / 坏 JSON → (60, None) ---
_led_bad = _tmp("ledger_bad.json")
with _Patch(ledger, "LEDGER_PATH", _led_bad):
    _led_bad.write_text("{broken", encoding="utf-8")
    check("VS-01 ledger: 坏 JSON → (60, None)", ledger.reldate_for("Any") == (60, None))
    _led_bad.unlink(missing_ok=True)
    check("VS-01 ledger: 缺文件 → (60, None)", ledger.reldate_for("Any") == (60, None))

# --- INV-06：lit.ledger 模块公开 API 只读（无任何写函数） ---
_WRITE_VERBS = ("write", "save", "set", "update", "append", "create", "delete",
                "remove", "put", "insert", "push", "record", "mark")
_public_writers = [n for n in dir(ledger)
                   if not n.startswith("_")
                   and callable(getattr(ledger, n))
                   and any(v in n.lower() for v in _WRITE_VERBS)]
check("INV-06: ledger 公开 API 只读（无写函数）",
      _public_writers == [], "(发现疑似写 API: %s)" % _public_writers)
# 源码层再核一道：ledger 只有 read_text，不应出现 write_text（台账写路径归引擎，不归 App）
_ledger_src = (Path(ROOT / "lit" / "ledger.py").read_text(encoding="utf-8"))
check("INV-06: ledger 源码无 write_text（台账写路径归引擎）",
      "write_text" not in _ledger_src)

# --- journals：合成期刊表（表头/分隔/<5 列杂表）解析 + 缺文件回退静态 10 ---
with _Patch(journals, "JOURNAL_TABLE", _jt):
    data = journals.load()
    check("journals: 合成表解析正确（2 刊 + 1 刊）",
          data.get("胸部肿瘤与胸外科") == ["J Thorac Oncol", "Ann Thorac Surg"]
          and data.get("临床医学综合") == ["N Engl J Med"])
    check("journals: 杂表（<5 列）被跳过",
          "杂表标题" not in data and "a" not in journals.all_journals())
    check("journals: all_journals 按 CATEGORIES 顺序",
          journals.all_journals(data)[:2] == ["J Thorac Oncol", "Ann Thorac Surg"])
    check("journals: category_of 反查",
          journals.category_of("Ann Thorac Surg", data) == "胸部肿瘤与胸外科"
          and journals.category_of("不存在刊", data) is None)

with _Patch(journals, "JOURNAL_TABLE", _tmp("no_such_table.md")):   # 不创建即缺失
    fb = journals.load()
    check("journals: 文件缺失 → 回退静态胸外 10",
          fb.get("胸部肿瘤与胸外科") == journals._FALLBACK["胸部肿瘤与胸外科"]
          and len(fb["胸部肿瘤与胸外科"]) == 10)
    check("journals: 默认刊存在",
          journals.DEFAULT_JOURNAL == "J Thorac Oncol")

# --- INV-08：凭证不进异常文本 ---
# deepseek._deepseek_judge：无 DEEPSEEK_TOKEN → RuntimeError 人话，不含任何 token 值
_sentinel = "SECRET-TOKEN-XYZ-DO-NOT-LEAK"
os.environ["DEEPSEEK_TOKEN"] = _sentinel   # 先放一个哨兵 token
# 模拟「无 token」：patch os.environ 拿掉它（save/restore）
_environ_orig = dict(os.environ)
os.environ.pop("DEEPSEEK_TOKEN", None)
try:
    try:
        deepseek._deepseek_judge([{"pmid": 1, "title": "x"}], {"1": "abs"}, "判据", timeout=180)
    except RuntimeError as e:
        msg = str(e)
        check("INV-08: _deepseek_judge 无 token → RuntimeError 人话",
              "DEEPSEEK_TOKEN" in msg)
        check("INV-08: 异常文本不含任何 token 值",
              _sentinel not in msg and "sk-" not in msg, "(msg=%r)" % msg[:60])
    else:
        check("INV-08: _deepseek_judge 无 token 应抛 RuntimeError", False)
finally:
    os.environ.clear()
    os.environ.update(_environ_orig)

# zotero._load_env：凭证文件缺失 → FileNotFoundError（不触网）
with _Patch(zotero, "ENV_PATH", _tmp("no_such_zotero.env")):   # 不创建即缺失
    try:
        zotero._load_env()
    except FileNotFoundError:
        check("INV-08: zotero._load_env 缺凭证文件 → FileNotFoundError", True)
    else:
        check("INV-08: zotero._load_env 缺凭证文件 → FileNotFoundError", False)

# _fetch_abstracts 解析：mock urllib.request.urlopen 返回合成 PubMed XML（不联网）
import urllib.request as _urlreq  # noqa: E402

_FAKE_PUBMED_XML = (
    "<PubmedArticleSet>"
    "<PubmedArticle><MedlineCitation><PMID>111</PMID>"
    "<Article><Abstract><AbstractText>肺癌免疫治疗新进展</AbstractText>"
    "<AbstractText Label=\"CONCLUSIONS\">结论段</AbstractText></Abstract></Article>"
    "</MedlineCitation></PubmedArticle>"
    "<PubmedArticle><MedlineCitation><PMID>222</PMID>"
    "<Article><ArticleTitle>无摘要的</ArticleTitle></Article>"
    "</MedlineCitation></PubmedArticle>"
    "</PubmedArticleSet>").encode("utf-8")


class _FakeResp:
    def __init__(self, data):
        self._data = data

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


_orig_urlopen = _urlreq.urlopen
_urlreq.urlopen = lambda req, timeout=None: _FakeResp(_FAKE_PUBMED_XML)
try:
    abs_ = deepseek._fetch_abstracts(["111", "222"], timeout=10)
finally:
    _urlreq.urlopen = _orig_urlopen
check("INV-08 加严: _fetch_abstracts 解析合成 XML（拼接多 AbstractText，截断容缺）",
      "111" in abs_ and "222" in abs_
      and "肺癌免疫治疗新进展" in abs_["111"] and "结论段" in abs_["111"]
      and abs_["222"] == "")

# ============================ 收尾：清理临时目录 ============================
import shutil  # noqa: E402

shutil.rmtree(_TMPDIR, ignore_errors=True)

print(f"\n{'=' * 40}\n{sum(checks)}/{len(checks)} 项通过")
sys.exit(0 if all(checks) else 1)
