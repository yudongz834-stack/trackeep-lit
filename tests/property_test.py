# -*- coding: utf-8 -*-
"""属性 / 生成式测试：手写随机生成器（无 hypothesis），机器生成输入 × 不变式恒成立。

断言来源：.project/invariants.yaml（母法 7.3 第二层——机器生成输入验证不变式）+
lit/{strategy,overrides,ledger,engine}.py 的合并 / 解析 / 往返 / 窗口契约。每个属性
≥500 例随机输入；SEED 固定可复现（母法 7.4）；失败打印最小反例输入便于复现。

纯逻辑测试，无需 Qt；绝不联网、绝不真 spawn 引擎、绝不写 Mecha-Core 真实文件——所有
json / 台账 / 期刊表一律 patch 模块级 *_PATH 到 tests/_tmp_* 临时路径，脚本末尾自清理。

运行：venv\\Scripts\\python.exe tests\\property_test.py
      PROPERTY_SEED=7 venv\\Scripts\\python.exe tests\\property_test.py
"""
import copy
import json
import os
import random
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

SEED = int(os.environ.get("PROPERTY_SEED", "42"))
print(f"seed={SEED}")                      # 固定 seed 可复现（母法 7.4）
rng = random.Random(SEED)                  # 单实例顺序消费 → 同 seed 可复现

N_CASES = 500                              # 每属性 ≥500 例

_TMPDIR = Path(__file__).resolve().parent / "_tmp_property"
_TMPDIR.mkdir(exist_ok=True)

# ---- TRACKEEP_CI=1：桩 urllib（本文件本就零联网，计数应为 0）----
_CI_SKIPS = {"n": 0}
if os.environ.get("TRACKEEP_CI") == "1":
    import urllib.request as _urlreq

    def _ci_block(*_a, **_k):
        _CI_SKIPS["n"] += 1
        raise RuntimeError("TRACKEEP_CI: 联网调用已跳过（CI 无外网）")

    _urlreq.urlopen = _ci_block

from lit import config, engine, journals, ledger, overrides, strategy  # noqa: E402

checks = []


def check(name: str, cond: bool, extra: str = "") -> None:
    checks.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {extra}")


def _tmp(name: str) -> Path:
    """tests/_tmp_property/<name>：测试自管临时路径（gitignore 覆盖 tests/_tmp_*）。"""
    p = _TMPDIR / name
    p.unlink(missing_ok=True)
    return p


def _shrink_list(lst, still_fails):
    """贪心缩减列表：逐个尝试删元素，只要 still_fails(缩减后) 仍 True 就保留删除。
    返回最小化后仍触发失败的列表（最小反例便于复现）。不缩到空。"""
    best = list(lst)
    i = 0
    while i < len(best):
        cand = best[:i] + best[i + 1:]
        if cand and still_fails(cand):
            best = cand
        else:
            i += 1
    return best


# ============================ 全局桩：真实文件全转到临时路径 ============================

_OV = _tmp("overrides.json")
_ST = _tmp("strategy.json")
_LED = _tmp("ledger.json")
_JT = _tmp("journal_table.md")
_JT.write_text(
    "| 来源分类 | 期刊全名 | PubMed缩写 | 推荐目录名 | 备注 |\n"
    "|---|---|---|---|---|\n"
    "| 胸部肿瘤与胸外科 | 胸科A | J Thorac Oncol | J Thorac Oncol | x |\n"
    "| 胸部肿瘤与胸外科 | 胸科B | Ann Thorac Surg | Ann Thorac Surg | x |\n"
    "| 流行病学与公共卫生 | 流病A | Lancet Public Health | Lancet Public Health | x |\n"
    "| 流行病学与公共卫生 | 流病B | Epidemiology | Epidemiology | x |\n"
    "| 临床医学综合 | 临床A | NEJM | N Engl J Med | x |\n"
    "| 临床医学综合 | 临床B | BMJ | BMJ | x |\n"
    "| 医学AI与数字医学 | AIA | JAMIA | JAMIA | x |\n"
    "| 医学AI与数字医学 | AIB | NPJ Digit Med | NPJ Digit Med | x |\n"
    "| 基础与转化医学 | 基础A | Nature Medicine | Nat Med | x |\n"
    "| 基础与转化医学 | 基础B | Sci Transl Med | Sci Transl Med | x |\n",
    encoding="utf-8")

overrides.OVERRIDES_PATH = _OV
strategy.STRATEGY_PATH = _ST
ledger.LEDGER_PATH = _LED
journals.JOURNAL_TABLE = _JT

# 引擎路径预检要「存在」——指到假脚本；subprocess.run 换可变桩（property 2 用）
_EXISTING_ENGINE = _tmp("fake_engine.ps1")
_EXISTING_ENGINE.write_text("# fake engine for property tests\n", encoding="utf-8")
config.ENGINE_PATH = _EXISTING_ENGINE


class _MutSpawn:
    """可变 stdout 的假 subprocess.run：不真起进程，run_search/run_import 共用。"""

    def __init__(self):
        self.stdout = ""

    def __call__(self, argv, **kwargs):
        return subprocess.CompletedProcess(args=argv, returncode=0,
                                           stdout=self.stdout, stderr="")


_MOCK_SPAWN = _MutSpawn()
_orig_run = engine.subprocess.run
engine.subprocess.run = _MOCK_SPAWN

_ALL_JOURNALS = journals.all_journals()      # 10 刊（依赖上面 patch 后的期刊表）
_CATS = list(journals.CATEGORIES)


def _write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


# ============================ 属性 1：resolve 合并契约不变式 ============================

def _gen_raw_category(rng):
    """随机分类策略 dict：含缺键 / 半缺子字典（topicFilter 只有 enabled 没 terms 等）。"""
    cat = {}
    if rng.random() < 0.8:
        cat["editorial"] = rng.choice([True, False])
    if rng.random() < 0.8:
        cat["letter"] = rng.choice([True, False])
    r = rng.random()
    if r < 0.2:
        pass                                    # topicFilter 缺
    elif r < 0.4:
        cat["topicFilter"] = {"enabled": rng.choice([True, False])}      # 半缺：无 terms
    elif r < 0.5:
        cat["topicFilter"] = {"terms": rng.choice(["", "lung[tiab]"])}   # 半缺：无 enabled
    else:
        cat["topicFilter"] = {"enabled": rng.choice([True, False]),
                              "terms": rng.choice(["", "  ", "lung[tiab]", "x"])}
    r = rng.random()
    if r < 0.3:
        pass                                    # deepseek 缺
    elif r < 0.5:
        cat["deepseek"] = {"enabled": rng.choice([True, False])}         # 半缺：无 criteria
    elif r < 0.6:
        cat["deepseek"] = {"criteria": rng.choice(["", "判据"])}         # 半缺：无 enabled
    else:
        cat["deepseek"] = {"enabled": rng.choice([True, False]),
                           "criteria": rng.choice(["", "判据A"])}
    return cat


def _gen_raw_override(rng):
    """随机单刊例外 dict：含缺键（不含某字段即「未显式」）；deepseek 含半缺 / 畸形变体。"""
    ov = {}
    if rng.random() < 0.6:
        ov["includeEditorial"] = rng.choice([True, False])
    if rng.random() < 0.6:
        ov["includeLetter"] = rng.choice([True, False])
    r = rng.random()
    if r < 0.3:
        pass                                                      # topicFilter 缺
    elif r < 0.45:
        ov["topicFilter"] = None
    elif r < 0.6:
        ov["topicFilter"] = rng.choice(["", "  ", "\t"])          # 空串 / 空白（falsy / truthy 混）
    else:
        ov["topicFilter"] = rng.choice(["lung[tiab]", "  esophag*[tiab]  ", "x"])
    # deepseek 覆写（含半缺 / 畸形 → resolve 应安全回落分类，预言机同口径）
    r = rng.random()
    if r < 0.35:
        pass                                                      # deepseek 缺
    elif r < 0.5:
        ov["deepseek"] = {"enabled": rng.choice([True, False])}   # 半缺 criteria
    elif r < 0.62:
        ov["deepseek"] = {"criteria": rng.choice(["", "判据O"])}  # 半缺 enabled
    elif r < 0.78:
        ov["deepseek"] = {"enabled": rng.choice([True, False, None]),
                          "criteria": rng.choice([None, "", "判据P", "  判据P  "])}
    else:
        ov["deepseek"] = rng.choice(["notadict", None, {"enabled": "yes"},
                                      {"criteria": 123}, {"enabled": True, "criteria": 123}])
    return ov


def _expected_base(raw_cat):
    """get_category 规约预言机：深拷默认 + 填已存字段（半缺子字典逐字段兜）。"""
    base = copy.deepcopy(strategy.CATEGORY_DEFAULT)
    if isinstance(raw_cat, dict):
        for k in ("editorial", "letter"):
            if k in raw_cat:
                base[k] = bool(raw_cat[k])
        for sub in ("topicFilter", "deepseek"):
            se = raw_cat.get(sub)
            if isinstance(se, dict):
                for fk in base[sub]:
                    if fk in se:
                        base[sub][fk] = se[fk]
    return base


def _resolve_invariant_fail(result, raw_ov, base):
    """高层不变式陈述（非重实现 resolve）：任一不过返 (原因, 反例串)，全过返 None。"""
    # 形状：恒 5 键 + 类型恒定
    if set(result.keys()) != {"editorial", "letter", "topic",
                              "deepseek_enabled", "deepseek_criteria"}:
        return ("keys", repr(sorted(result.keys())))
    if not isinstance(result["editorial"], bool):
        return ("editorial 非布尔", repr(result["editorial"]))
    if not isinstance(result["letter"], bool):
        return ("letter 非布尔", repr(result["letter"]))
    if result["topic"] is not None and not isinstance(result["topic"], str):
        return ("topic 非 str|None", repr(result["topic"]))
    if not isinstance(result["deepseek_enabled"], bool):
        return ("deepseek_enabled 非布尔", repr(result["deepseek_enabled"]))
    if not isinstance(result["deepseek_criteria"], str):
        return ("deepseek_criteria 非 str", repr(result["deepseek_criteria"]))
    # editorial / letter：单刊显式优先；无显式 = 分类默认
    if "includeEditorial" in raw_ov:
        if result["editorial"] != bool(raw_ov["includeEditorial"]):
            return ("editorial 单刊未优先", f"ov={raw_ov['includeEditorial']!r} got={result['editorial']!r}")
    elif result["editorial"] != bool(base["editorial"]):
        return ("editorial 未取分类默认", f"base={base['editorial']} got={result['editorial']}")
    if "includeLetter" in raw_ov:
        if result["letter"] != bool(raw_ov["includeLetter"]):
            return ("letter 单刊未优先", f"ov={raw_ov['includeLetter']!r} got={result['letter']!r}")
    elif result["letter"] != bool(base["letter"]):
        return ("letter 未取分类默认", f"base={base['letter']} got={result['letter']}")
    # topic：非 None ⟺（单刊显式 topicFilter 真值）或（分类 enabled 且 terms.strip() 非空）
    explicit = bool(raw_ov.get("topicFilter"))    # None/"" 假，非空串（含纯空白）真
    cat_active = bool(base["topicFilter"]["enabled"]) and bool(base["topicFilter"]["terms"].strip())
    if (result["topic"] is not None) != (explicit or cat_active):
        return ("topic 非 None 当且仅当", f"explicit={explicit} cat_active={cat_active} got={result['topic']!r}")
    if explicit:
        if result["topic"] != raw_ov["topicFilter"]:      # 单刊 topicFilter 原样不 strip
            return ("topic 单刊原样", f"ov={raw_ov['topicFilter']!r} got={result['topic']!r}")
    elif cat_active:
        if result["topic"] != base["topicFilter"]["terms"].strip():
            return ("topic 分类 strip", f"base={base['topicFilter']['terms']!r} got={result['topic']!r}")
    # deepseek：单刊 override 优先（enabled 显式 bool 用它；criteria 非空 str 用它），否则分类；
    # 畸形 override（非 dict / enabled 非 bool / criteria 非 str）预言机同 resolve 安全回落分类
    ds_ov = raw_ov.get("deepseek")
    exp_enabled = bool(base["deepseek"]["enabled"])
    exp_criteria = base["deepseek"]["criteria"] or ""
    if isinstance(ds_ov, dict):
        ov_en = ds_ov.get("enabled")
        if isinstance(ov_en, bool):
            exp_enabled = ov_en
        ov_cr = ds_ov.get("criteria")
        if isinstance(ov_cr, str) and ov_cr.strip():
            exp_criteria = ov_cr.strip()
    if result["deepseek_enabled"] != exp_enabled:
        return ("deepseek_enabled", f"exp={exp_enabled} got={result['deepseek_enabled']!r} | ds_ov={ds_ov!r}")
    if result["deepseek_criteria"] != exp_criteria:
        return ("deepseek_criteria", f"exp={exp_criteria!r} got={result['deepseek_criteria']!r} | ds_ov={ds_ov!r}")
    return None


def _prop1_resolve(rng):
    for i in range(N_CASES):
        j = rng.choice(_ALL_JOURNALS)
        cat = journals.category_of(j)
        raw_cat = _gen_raw_category(rng)
        raw_ov = _gen_raw_override(rng)
        _write_json(_ST, {"version": 1, "categories": {cat: raw_cat}})
        _write_json(_OV, {j: raw_ov})
        try:
            result = strategy.resolve(j)
            base = _expected_base(raw_cat)
            fail = _resolve_invariant_fail(result, raw_ov, base)
            if fail is None:
                continue
            why, detail = fail
        except Exception as e:
            why, detail = "resolve 抛异常", f"{type(e).__name__}: {e}"
        return i + 1, why, f"detail={detail} | journal={j!r} cat={raw_cat!r} ov={raw_ov!r}"
    return N_CASES, None, None


n, why, ce = _prop1_resolve(rng)
check("属性1: resolve 合并契约（显式优先/topic iff/5 键恒型/永不抛）",
      why is None,
      f"({n} 例)" if why is None else f"(反例@{n}: {why} | {ce})")


# ============================ 属性 2：TRACKEEP_JSON 解析属性 ============================

_PREFIX = "TRACKEEP_JSON "

# 噪声词：均不可单独构成合法前缀行（"TRACKEEP_JSON" 13 字符 < 14 字符前缀）
_NOISE_WORDS = ["PowerShell 启动噪声", "进度 1/3", "warn: skip", "TRACKEEP_JSON",
                'MECHA_JSON {"a":1}', "导入中...", "==done==", "TRACKEEP_JSONX foo",
                '{"not_prefixed":true}', "", "  "]


def _parse_oracle(stdout):
    """解析预言机：首个 strip+lstrip(BOM) 后以 TRACKEEP_JSON 开头的行 → json.loads；无 → None。"""
    for ln in stdout.splitlines():
        s = ln.strip().lstrip("﻿")
        if s.startswith(_PREFIX):
            return json.loads(s[len(_PREFIX):])
    return None


def _gen_lines(rng):
    """随机噪声行集 + 随机位置插入 0~3 条合法前缀行（随机 BOM / 前导空白）。"""
    n_noise = rng.randint(0, 8)
    lines = [rng.choice(_NOISE_WORDS) for _ in range(n_noise)]
    n_valid = rng.choices([0, 1, 2, 3], weights=[3, 5, 2, 1])[0]
    for _ in range(n_valid):
        payload = {"found": rng.randint(0, 999), "tag": rng.choice(["a", "b"]),
                   "n": rng.randint(0, 50)}
        line = _PREFIX + json.dumps(payload, ensure_ascii=False)
        if rng.random() < 0.3:
            line = "﻿" + line
        if rng.random() < 0.3:
            line = "  " + line
        lines.insert(rng.randint(0, len(lines)), line)
    return lines


def _p2_engine_result(stdout):
    _MOCK_SPAWN.stdout = stdout
    try:
        return ("ok", engine.run_search("J Thorac Oncol", reldate_days=30))
    except RuntimeError as e:
        return ("runtime", str(e))
    except Exception as e:
        return ("exc", type(e).__name__, str(e))


def _p2_disagree(lines, sep, wrap_bom):
    stdout = ("﻿" if wrap_bom else "") + sep.join(lines)
    oracle = _parse_oracle(stdout)
    got = _p2_engine_result(stdout)
    if oracle is not None:
        return got != ("ok", oracle), oracle, got
    disagree = not (got[0] == "runtime" and "TRACKEEP_JSON" in got[1])
    return disagree, oracle, got


def _prop2_parse(rng):
    for i in range(N_CASES):
        lines = _gen_lines(rng)
        sep = rng.choice(["\n", "\r\n"])
        wrap_bom = rng.random() < 0.2
        disagree, oracle, got = _p2_disagree(lines, sep, wrap_bom)
        if disagree:
            shrunk = _shrink_list(
                lines, lambda L: _p2_disagree(L, "\n", False)[0])
            return (i + 1,
                    f"oracle={oracle!r} engine={got!r}",
                    f"shrunk_lines={shrunk!r}")
    return N_CASES, None, None


n, why, ce = _prop2_parse(rng)
check("属性2: TRACKEEP_JSON 解析（有合法行→取首条 payload / 无→RuntimeError）",
      why is None,
      f"({n} 例)" if why is None else f"(反例@{n}: {why} | {ce})")


# ============================ 属性 3：overrides 往返属性 ============================

def _norm_ov_cfg(cfg):
    """save→get 的归一预言机：topicFilter 空串/空白/None 等价归 None（strip 后空）；
    deepseek 经 `_normalize_deepseek` 同口径归一（非 dict / 非 bool / 非 str → None）。"""
    tf = cfg.get("topicFilter", None)
    tf = tf.strip() if isinstance(tf, str) else tf
    tf = tf or None
    ds = cfg.get("deepseek")
    if not isinstance(ds, dict):
        ds = {}
    en = ds.get("enabled")
    en = en if isinstance(en, bool) else None
    cr = ds.get("criteria")
    cr = cr.strip() if isinstance(cr, str) else None
    cr = cr or None
    return {"includeEditorial": bool(cfg.get("includeEditorial", False)),
            "includeLetter": bool(cfg.get("includeLetter", False)),
            "topicFilter": tf,
            "deepseek": {"enabled": en, "criteria": cr}}


def _gen_ov_cfg(rng):
    r = rng.random()
    if r < 0.3:
        deepseek = None                                   # 不设（= 继承）
    elif r < 0.5:
        deepseek = {"enabled": rng.choice([True, False])}  # 半缺 criteria
    elif r < 0.7:
        deepseek = {"criteria": rng.choice(["", "判据Z"])}  # 半缺 enabled
    else:
        deepseek = {"enabled": rng.choice([True, False]),
                    "criteria": rng.choice([None, "", "判据W", "  判据W  "])}
    return {
        "includeEditorial": rng.choice([True, False]),
        "includeLetter": rng.choice([True, False]),
        "topicFilter": rng.choice([None, "", "  ", "lung[tiab]", "  lung[tiab]  ", "\t"]),
        "deepseek": deepseek,
    }


_OV_POOL = ["J Thorac Oncol", "Ann Thorac Surg", "Lung Cancer", "Chest", "N Engl J Med", "BMJ"]


def _prop3_overrides(rng):
    _OV.unlink(missing_ok=True)                 # 干净起点（隔离属性 1 的 _OV 残留）
    state = {}                                  # journal -> 最后一次写的归一 cfg
    for i in range(N_CASES):
        j = rng.choice(_OV_POOL)
        cfg = _gen_ov_cfg(rng)
        overrides.save(j, cfg)
        state[j] = _norm_ov_cfg(cfg)
        # 原子弱验证：写后即 json.loads 得回
        try:
            json.loads(_OV.read_text(encoding="utf-8-sig"))
            atomic_ok = True
        except Exception:
            atomic_ok = False
        # save→get 语义恒等（当前刊）
        self_ok = overrides.get(j) == state[j]
        # 多刊乱序反复写：任一刊读数只受自己最后一次写影响
        indep_ok = all(overrides.get(k) == v for k, v in state.items())
        if not (atomic_ok and self_ok and indep_ok):
            why = ("atomic" if not atomic_ok else "self" if not self_ok else "indep")
            return (i + 1, f"{why} 不成立",
                    f"j={j!r} cfg={cfg!r} state={state!r} get(j)={overrides.get(j)!r}")
    return N_CASES, None, None


n, why, ce = _prop3_overrides(rng)
check("属性3: overrides 往返（save→get 语义恒等 / 多刊乱序独立 / 写后即合法 JSON）",
      why is None,
      f"({n} 例)" if why is None else f"(反例@{n}: {why} | {ce})")


# ============================ 属性 4：strategy 往返属性 ============================

def _norm_policy(p):
    """save_category→get_category 的归一预言机（与 save_category 写出结构同构）。"""
    tf = p.get("topicFilter") or {}
    ds = p.get("deepseek") or {}
    return {
        "editorial": bool(p.get("editorial", False)),
        "letter": bool(p.get("letter", False)),
        "topicFilter": {"enabled": bool(tf.get("enabled", False)),
                        "terms": tf.get("terms", "") or ""},
        "deepseek": {"enabled": bool(ds.get("enabled", False)),
                     "criteria": ds.get("criteria", "") or ""},
    }


def _gen_policy(rng):
    """随机策略（含半缺子字典，验 save_category 兜默认补全）。"""
    p = {}
    if rng.random() < 0.9:
        p["editorial"] = rng.choice([True, False])
    if rng.random() < 0.9:
        p["letter"] = rng.choice([True, False])
    r = rng.random()
    if r < 0.2:
        pass
    elif r < 0.4:
        p["topicFilter"] = {"enabled": rng.choice([True, False])}
    else:
        p["topicFilter"] = {"enabled": rng.choice([True, False]),
                            "terms": rng.choice(["", "  ", "lung[tiab]"])}
    r = rng.random()
    if r < 0.3:
        pass
    elif r < 0.5:
        p["deepseek"] = {"enabled": rng.choice([True, False])}
    else:
        p["deepseek"] = {"enabled": rng.choice([True, False]),
                         "criteria": rng.choice(["", "判据A"])}
    return p


def _prop4_strategy(rng):
    _ST.unlink(missing_ok=True)                 # 干净起点（隔离属性 1 的 _ST 残留）
    # (a) 往返：随机分类子集反复 save_category；未写分类恒等默认；version 恒在
    saved = {}                                 # cat -> 最后一次写的归一 policy
    for i in range(N_CASES):
        cat = rng.choice(_CATS)
        pol = _gen_policy(rng)
        strategy.save_category(cat, pol)
        saved[cat] = _norm_policy(pol)
        data = strategy.load()
        ver_ok = data.get("version") == 1
        unsaved_ok = all(strategy.get_category(c) == copy.deepcopy(strategy.CATEGORY_DEFAULT)
                         for c in _CATS if c not in saved)
        saved_ok = all(strategy.get_category(c) == v for c, v in saved.items())
        if not (ver_ok and unsaved_ok and saved_ok):
            why = ("version" if not ver_ok else "unsaved_default" if not unsaved_ok else "saved_roundtrip")
            return (f"4a-{i + 1}", why,
                    f"cat={cat!r} pol={pol!r} saved={saved!r}")
    # (b) 半缺补全：直接写半缺存档，get_category 永远补全完整结构
    for i in range(N_CASES):
        cat = rng.choice(_CATS)
        raw = _gen_raw_category(rng)
        _write_json(_ST, {"version": 1, "categories": {cat: raw}})
        got = strategy.get_category(cat)
        expected = _expected_base(raw)
        struct_ok = got == expected
        shape_ok = (set(got.keys()) == set(strategy.CATEGORY_DEFAULT.keys())
                    and isinstance(got["editorial"], bool) and isinstance(got["letter"], bool)
                    and set(got["topicFilter"].keys()) == {"enabled", "terms"}
                    and set(got["deepseek"].keys()) == {"enabled", "criteria"})
        if not (struct_ok and shape_ok):
            why = "struct" if not struct_ok else "shape"
            return (f"4b-{i + 1}", f"{why} got={got!r} expected={expected!r}",
                    f"cat={cat!r} raw={raw!r}")
    return N_CASES * 2, None, None


n, why, ce = _prop4_strategy(rng)
check("属性4: strategy 往返（未写分类恒默认/version 恒在/半缺存档恒补全完整结构）",
      why is None,
      f"({n} 例)" if why is None else f"(反例@{n}: {why} | {ce})")


# ============================ 属性 5：ledger 窗口属性 ============================

def _expected_last(batches, target):
    """last_date 规约预言机：target 刊合法 time 的最大值；无 → None。"""
    vs = []
    for b in batches:
        if not isinstance(b, dict) or b.get("journal") != target:
            continue
        t = b.get("time")
        if not t:
            continue
        try:
            vs.append(datetime.fromisoformat(str(t)).date())
        except ValueError:
            continue
    return max(vs) if vs else None


def _gen_batches(rng, target):
    today = date.today()
    batches = []
    valid = []
    for _ in range(rng.randint(0, 5)):             # 合法日期（含未来日，测夹上下限）
        delta = rng.randint(-30, 600)              # -30=未来 30 天；600=过去 600 天
        d = today - timedelta(days=delta)
        valid.append(d)
        batches.append({"journal": target, "time": d.isoformat()})
    for _ in range(rng.randint(0, 4)):             # 坏值混入（只应被跳过）
        kind = rng.choice(["junk", "missing_time", "non_dict", "bad_date"])
        if kind == "junk":
            batches.append({"journal": target, "time": rng.choice(["not-a-date", "xyz", ""])})
        elif kind == "missing_time":
            batches.append({"journal": target})
        elif kind == "non_dict":
            batches.append(["journal", target])
        else:
            batches.append({"journal": target, "time": rng.choice(["2026-02-30", "2026-13-99"])})
    for _ in range(rng.randint(0, 4)):             # 其它刊噪声（不应影响 target）
        batches.append({"journal": "OTHER",
                        "time": (today - timedelta(days=rng.randint(0, 300))).isoformat()})
    rng.shuffle(batches)
    return batches, valid


def _prop5_ledger(rng):
    for i in range(N_CASES):
        target = rng.choice(["J Thorac Oncol", "X", "Y", "Z"])
        batches, valid = _gen_batches(rng, target)
        _LED.write_text(json.dumps({"batches": batches}, ensure_ascii=False),
                        encoding="utf-8-sig")
        expected = max(valid) if valid else None
        try:
            got = ledger.last_date(target)
            days, _last = ledger.reldate_for(target)
            threw = False
        except Exception as e:
            got, days = ("EXC:" + type(e).__name__), None
            threw = True
        last_ok = (got == expected)
        range_ok = (days is not None and 7 <= days <= 400)
        if threw or not last_ok or not range_ok:
            why = ("threw" if threw else "last_date" if not last_ok else "reldate_range")
            # 最小反例：缩 batches 至仍复现 last_date 不符的最小集
            def _still_fails(L, target=target):
                _LED.write_text(json.dumps({"batches": L}, ensure_ascii=False),
                                encoding="utf-8-sig")
                try:
                    return ledger.last_date(target) != _expected_last(L, target)
                except Exception:
                    return True
            shrunk = _shrink_list(batches, _still_fails)
            return (i + 1, f"{why} got_last={got!r} expected={expected!r} days={days!r}",
                    f"target={target!r} shrunk_batches={shrunk!r}")
    return N_CASES, None, None


n, why, ce = _prop5_ledger(rng)
check("属性5: ledger 窗口（last_date==max 合法 / reldate_for∈[7,400] / 坏值只跳不抛）",
      why is None,
      f"({n} 例)" if why is None else f"(反例@{n}: {why} | {ce})")


# ============================ 收尾：还原 + 清理 ============================

engine.subprocess.run = _orig_run

import shutil  # noqa: E402

if os.environ.get("TRACKEEP_CI") == "1":
    print(f"[CI] TRACKEEP_CI 联网检查跳过 {_CI_SKIPS['n']} 次")

shutil.rmtree(_TMPDIR, ignore_errors=True)

print(f"\n{'=' * 40}\n{sum(checks)}/{len(checks)} 项通过")
sys.exit(0 if all(checks) else 1)
