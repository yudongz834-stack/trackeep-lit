# -*- coding: utf-8 -*-
"""对抗测试：主动证明系统能被畸形输入破坏（母法 7.5）。

姿态 = 主动证伪，不是确认系统正常。每类喂多个畸形变体，断言「不崩或人话报错」——
真崩就如实 [FAIL] 并入末尾产品缺陷候选清单（只报不修：产品代码不在本测试的改动面）。

绝不联网（urllib 全程网闸 + DeepSeek 局部 mock）、绝不真 spawn 引擎（subprocess.run 换桩）、
绝不读写 Mecha-Core 真实文件（所有 json/md/台账 patch 模块级 *_PATH 常量到 tests/_tmp_adv，
末尾自清理）。涉 Qt 的回执渲染用例：offscreen + TRACKEEP_SELFTEST 前置（与 gui_test 一致）。

断言来源：.project/invariants.yaml（INV-03/04/06/08 等）+ .project/vulnerable-scenarios.yaml。

运行：D:\\trackeep-lit\\venv\\Scripts\\python.exe tests\\adversarial_test.py
      TRACKEEP_CI=1 同上（CI 无外网：网闸计数 + 跳过行）
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
from datetime import date, timedelta
from pathlib import Path

# 涉 Qt 的回执渲染用例：无显示器渲染 + 自检环境标记（必须在 import Qt 之前）
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["TRACKEEP_SELFTEST"] = "1"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

_TMPDIR = Path(__file__).resolve().parent / "_tmp_adv"
_TMPDIR.mkdir(exist_ok=True)

from lit import config, deepseek, engine, journals, ledger, overrides, strategy  # noqa: E402

checks = []


def check(name: str, cond: bool, extra: str = "") -> None:
    checks.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {extra}")


def _tmp(name: str) -> Path:
    """tests/_tmp_adv/<name>：测试自管临时路径（gitignore 覆盖 tests/_tmp_*）。"""
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


# ---- urllib 全程网闸：默认拦截真实联网（普通跑也不联网），DeepSeek 用例用局部 mock 覆盖 ----
import urllib.request as _urlreq  # noqa: E402

_CI_SKIPS = {"n": 0}


def _block_net(*_a, **_k):
    _CI_SKIPS["n"] += 1
    raise RuntimeError("adversarial_test: 真实联网已拦截（绝不联网）")


_urlreq.urlopen = _block_net   # 默认网闸；DeepSeek 用例临时换桩、用完还原回它

# DeepSeek 用例需要 token 在场（哨兵假值，绝不外传/打印）；末尾还原
_ENV_TOKEN_ORIG = os.environ.get("DEEPSEEK_TOKEN")
os.environ["DEEPSEEK_TOKEN"] = "adv-test-sentinel-not-real"

# 真实文件全桩到临时路径（绝不读写 Mecha-Core / 凭证）
_OV = _tmp("overrides.json")
_ST = _tmp("strategy.json")
_LED = _tmp("ledger.json")
_JT = _tmp("journal_table.md")
overrides.OVERRIDES_PATH = _OV
strategy.STRATEGY_PATH = _ST
ledger.LEDGER_PATH = _LED
journals.JOURNAL_TABLE = _JT

# 合法 5 分类期刊表（供 category_of / HarvestPage 构建用；畸形用例各自覆写）
_JT.write_text(
    "| 来源分类 | 期刊全名 | PubMed缩写 | 推荐目录名 | 备注 |\n"
    "|---|---|---|---|---|\n"
    "| 胸部肿瘤与胸外科 | 胸科A | J Thorac Oncol | J Thorac Oncol | x |\n"
    "| 胸部肿瘤与胸外科 | 胸科B | Ann Thorac Surg | Ann Thorac Surg | x |\n"
    "| 临床医学综合 | 临床A | NEJM | N Engl J Med | x |\n", encoding="utf-8")

_DEFECTS: list[dict] = []   # 产品缺陷候选清单（只报不修）


def _defect(sev: str, cat: str, phen: str, loc: str, err: str) -> None:
    _DEFECTS.append({"sev": sev, "cat": cat, "phen": phen, "loc": loc, "err": err})


# ============================ 1. 畸形 TRACKEEP_JSON 流（engine 解析） ============================

class _FakeSpawn:
    """假 subprocess.run：返回合成 CompletedProcess（或抛注入异常）。喂可控 stdout 验解析。"""

    def __init__(self, stdout="", returncode=0, stderr="", raise_exc=None):
        self.calls = []
        self.stdout, self.returncode, self.stderr = stdout, returncode, stderr
        self.raise_exc = raise_exc

    def __call__(self, argv, **kwargs):
        self.calls.append((list(argv), dict(kwargs)))
        if self.raise_exc is not None:
            raise self.raise_exc
        return subprocess.CompletedProcess(args=argv, returncode=self.returncode,
                                           stdout=self.stdout, stderr=self.stderr)


_EXISTING_ENGINE = _tmp("fake_engine.ps1")
_EXISTING_ENGINE.write_text("# fake engine for adversarial parsing tests\n", encoding="utf-8")


def _eng_parse(stdout: str):
    """用可控 stdout 跑一次 run_search（dry-run），返回解析结果或抛异常。"""
    fake = _FakeSpawn(stdout=stdout)
    with _Patch(config, "ENGINE_PATH", _EXISTING_ENGINE), \
            _Patch(engine.subprocess, "run", fake):
        return engine.run_search("J Thorac Oncol", reldate_days=30)


# 前缀后跟非法 JSON —— _run_engine 的 json.loads 未包 try，会抛原始 JSONDecodeError（非 RuntimeError）
try:
    _eng_parse("TRACKEEP_JSON {这不是合法json")
    check("engine: 前缀+非法JSON → 应人话 RuntimeError", False, "(没抛)")
except RuntimeError:
    check("engine: 前缀+非法JSON → 人话 RuntimeError", True)
except Exception as e:
    check("engine: 前缀+非法JSON → 人话 RuntimeError", False,
          "(抛原始 %s，未转 RuntimeError)" % type(e).__name__)
    _defect("hard", "engine",
            "TRACKEEP_JSON 后非法 JSON 抛原始 JSONDecodeError，未转人话 RuntimeError（违 INV-03 精神）",
            "lit/engine.py:122 json.loads(line[len(_PREFIX):]) 未包 try",
            "%s: %s" % (type(e).__name__, str(e)[:80]))

# 前缀行出现两次 → 解析循环 break 在首命中，取第一行（行为确定）
r = _eng_parse('TRACKEEP_JSON {"found": 1}\nTRACKEEP_JSON {"found": 2}\n噪声')
check("engine: 两行 TRACKEEP_JSON → 取首行（行为确定）",
      r.get("found") == 1, "(found=%s)" % r.get("found"))

# JSON 深嵌套 50 层 → json.loads 不崩（Python 默认递归上限远高于此）
_nested = "1"
for _ in range(50):
    _nested = '{"x":' + _nested + '}'
r = _eng_parse("TRACKEEP_JSON " + _nested)
check("engine: JSON 深嵌套 50 层 → 解析不崩", isinstance(r, dict),
      "(type=%s)" % type(r).__name__)

# 前缀大小写错（旧 MECHA_JSON 残留）→ 无行命中 → RuntimeError「未找到」（验 wire 全迁）
try:
    _eng_parse('MECHA_JSON {"found": 1}\n噪声')
    check("engine: 旧前缀 MECHA_JSON → 应报未找到", False, "(没抛)")
except RuntimeError as e:
    check("engine: 旧前缀 MECHA_JSON → RuntimeError「未找到 TRACKEEP_JSON」",
          "未找到" in str(e) and "TRACKEEP_JSON" in str(e))


# ============================ 2. 畸形台账（ledger） ============================

def _led_write(d: dict) -> None:
    _LED.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8-sig")


_today = date.today()
with _Patch(ledger, "LEDGER_PATH", _LED):
    # batches 非 list → _load_batches 兜 [] → (60, None)
    _led_write({"batches": "notalist"})
    d, _ = ledger.reldate_for("X")
    check("ledger: batches 非 list → 不崩、窗口 ∈[7,400]", 7 <= d <= 400, "(days=%d)" % d)

    # time 未来日期 → gap 负 → 夹下限 7（绝不为负）
    _led_write({"batches": [{"journal": "X", "time": (_today + timedelta(days=50)).isoformat()}]})
    d, _ = ledger.reldate_for("X")
    check("ledger: 未来 time → 窗口仍 ∈[7,400] 不为负", 7 <= d <= 400, "(days=%d)" % d)

    # 年份 9999（极远未来）→ 夹下限 7
    _led_write({"batches": [{"journal": "Y", "time": "9999-12-31"}]})
    d, _ = ledger.reldate_for("Y")
    check("ledger: time 9999 → 窗口 ∈[7,400]", 7 <= d <= 400, "(days=%d)" % d)

    # 年份 0001（极远过去）→ 夹上限 400
    _led_write({"batches": [{"journal": "Z", "time": "0001-01-01"}]})
    d, _ = ledger.reldate_for("Z")
    check("ledger: time 0001 → 窗口 ∈[7,400]", 7 <= d <= 400, "(days=%d)" % d)

    # time 为数字 → fromisoformat(str(12345)) 失败 → 跳过 → (60, None)
    _led_write({"batches": [{"journal": "W", "time": 12345}]})
    check("ledger: time 为数字 → 跳过 → (60, None)",
          ledger.reldate_for("W") == (60, None))

    # time 为 null → `if not t` 跳过 → (60, None)
    _led_write({"batches": [{"journal": "V", "time": None}]})
    check("ledger: time 为 null → 跳过 → (60, None)",
          ledger.reldate_for("V") == (60, None))


# ============================ 3. 畸形策略/例外表（strategy / overrides） ============================

def _st_write(payload) -> None:
    if isinstance(payload, str):
        _ST.write_text(payload, encoding="utf-8")
    else:
        _ST.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


with _Patch(strategy, "STRATEGY_PATH", _ST), _Patch(overrides, "OVERRIDES_PATH", _OV):
    # categories 非 dict → load() 强制 {} → get_category 兜 CATEGORY_DEFAULT
    _st_write({"version": 1, "categories": "notadict"})
    gc = strategy.get_category("胸部肿瘤与胸外科")
    check("strategy: categories 非 dict → get_category 兜默认不崩",
          gc["editorial"] is False and gc["topicFilter"]["enabled"] is False)

    # topicFilter 为字符串（非 dict）→ 子字典逐字段兜默认时 isinstance 失败 → 默认
    _st_write({"version": 1, "categories": {"胸部肿瘤与胸外科": {"topicFilter": "lung[tiab]"}}})
    gc = strategy.get_category("胸部肿瘤与胸外科")
    check("strategy: topicFilter 字符串 → 兜默认不崩",
          gc["topicFilter"]["enabled"] is False, "(tf=%r)" % gc["topicFilter"])

    # deepseek 为 null → 同上兜默认
    _st_write({"version": 1, "categories": {"胸部肿瘤与胸外科": {"deepseek": None}}})
    gc = strategy.get_category("胸部肿瘤与胸外科")
    check("strategy: deepseek=null → 兜默认不崩", gc["deepseek"]["enabled"] is False)

    # version 缺失 → load/get_category 不依赖 version
    _st_write({"categories": {}})
    check("strategy: version 缺失 → load 不崩",
          strategy.load().get("categories") == {})

    # version 为字符串 → 原样保留、不影响 get_category/resolve
    _st_write({"version": "bad", "categories": {}})
    check("strategy: version 字符串 → 不崩", strategy.load().get("version") == "bad")

    # resolve 未知刊 → category_of None → base=CATEGORY_DEFAULT → 兜默认
    r = strategy.resolve("根本不存在的刊名XYZ")
    check("strategy: resolve 未知刊 → 兜默认不崩",
          r["editorial"] is False and r["topic"] is None and r["deepseek_enabled"] is False)


# ============================ 4. 畸形期刊表（journals） ============================

with _Patch(journals, "JOURNAL_TABLE", _JT):
    # 空文件 → 解析空 → 回退静态胸外 10
    _JT.write_text("", encoding="utf-8")
    check("journals: 空文件 → 回退静态 10 不崩",
          journals.load().get("胸部肿瘤与胸外科") == journals._FALLBACK["胸部肿瘤与胸外科"])

    # 只有表头 + 分隔行（无数据行）→ 回退静态 10
    _JT.write_text("| 来源分类 | 期刊全名 | PubMed缩写 | 推荐目录名 | 备注 |\n"
                   "|---|---|---|---|---|\n", encoding="utf-8")
    check("journals: 只有表头 → 回退静态 10",
          journals.load().get("胸部肿瘤与胸外科") == journals._FALLBACK["胸部肿瘤与胸外科"])

    # 单行 100 列 → split('|') 后取 cells[1]/cells[4]，不崩
    _JT.write_text("|" + "|".join("c%d" % i for i in range(100)) + "|\n", encoding="utf-8")
    check("journals: 单行 100 列 → 取 cells[1]/cells[4] 不崩",
          isinstance(journals.load(), dict))

    # 单元格超长（5k 字符）→ 长字符串照常入列
    _long = "J" * 5000
    _JT.write_text("| 胸部肿瘤与胸外科 | %s | %s | %s | x |\n"
                   % (_long, _long, _long), encoding="utf-8")
    check("journals: 单元格超长 → 不崩", _long in journals.all_journals())

    # 重复刊名跨分类 → category_of 按 CATEGORIES 顺序取首命中；all_journals 双计
    _JT.write_text(
        "| 来源分类 | 期刊全名 | PubMed缩写 | 推荐目录名 | 备注 |\n|---|---|---|---|---|\n"
        "| 胸部肿瘤与胸外科 | A | Dup | Dup | x |\n"
        "| 临床医学综合 | B | Dup | Dup | x |\n", encoding="utf-8")
    _ddup = journals.load()
    check("journals: 重复刊名跨分类 → category_of 取首命中分类",
          journals.category_of("Dup", _ddup) == "胸部肿瘤与胸外科")
    check("journals: 重复刊名跨分类 → all_journals 双计（行为确定）",
          journals.all_journals(_ddup).count("Dup") == 2)

# 还原合法表，供后续 HarvestPage 构建用
_JT.write_text(
    "| 来源分类 | 期刊全名 | PubMed缩写 | 推荐目录名 | 备注 |\n"
    "|---|---|---|---|---|\n"
    "| 胸部肿瘤与胸外科 | 胸科A | J Thorac Oncol | J Thorac Oncol | x |\n"
    "| 胸部肿瘤与胸外科 | 胸科B | Ann Thorac Surg | Ann Thorac Surg | x |\n"
    "| 临床医学综合 | 临床A | NEJM | N Engl J Med | x |\n", encoding="utf-8")


# ============================ 5. DeepSeek 返回对抗（直接调 _deepseek_judge，mock urlopen） ============================

class _FakeResp:
    """假 urlopen 响应：read 返回合成 body，支持 with 上下文。"""

    def __init__(self, data: bytes):
        self._data = data

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _ds_resp(text: str) -> bytes:
    """构 Anthropic 兼容响应 body：{content:[{type:text, text:<text>}]}。"""
    return json.dumps({"content": [{"type": "text", "text": text}]},
                      ensure_ascii=False).encode("utf-8")


def _ds(text_or_bytes, items=None, abstracts=None, criteria="主体聚焦肺癌"):
    """局部换桩 urlopen 返回合成 body，调 _deepseek_judge，用完还原网闸。"""
    items = items if items is not None else [{"pmid": 1, "title": "T1"}]
    abstracts = abstracts if abstracts is not None else {"1": "abs1"}
    body = text_or_bytes if isinstance(text_or_bytes, bytes) else _ds_resp(text_or_bytes)
    resp = _FakeResp(body)
    saved = _urlreq.urlopen
    _urlreq.urlopen = lambda req, timeout=None: resp
    try:
        return deepseek._deepseek_judge(items, abstracts, criteria, timeout=30)
    finally:
        _urlreq.urlopen = saved   # 还原回 _block_net（绝不还原成真实 urlopen）


# (a) 返回无 JSON 数组（text 无 [...]）→ RuntimeError 人话
try:
    _ds("我觉得这几篇都不相关")
    check("DS: 返回无 JSON 数组 → 应 RuntimeError", False, "(没抛)")
except RuntimeError as e:
    check("DS: 返回无 JSON 数组 → RuntimeError 人话", "无法解析" in str(e) or "JSON" in str(e))
except Exception as e:
    check("DS: 返回无 JSON 数组 → RuntimeError 人话", False, "(%s)" % type(e).__name__)
    _defect("hard", "deepseek", "无 JSON 数组应抛 RuntimeError 却抛了别的",
            "lit/deepseek.py:85-87", "%s" % type(e).__name__)

# (b) 数组元素缺 n → idx2pmid.get(None)=None → 安全忽略（不崩、 verdicts 不含该项）
v = _ds(json.dumps([{"keep": True, "reason": "x"}], ensure_ascii=False))
check("DS: 数组元素缺 n → 安全忽略不崩", v == {}, "(verdicts=%s)" % v)

# (c) n 越界 → 同上安全忽略
v = _ds(json.dumps([{"n": 999, "keep": True}], ensure_ascii=False))
check("DS: n 越界 → 安全忽略不崩", v == {}, "(verdicts=%s)" % v)

# (d) keep 为字符串 "false" → bool("false")=True 误判为「留」（应 drop）
v = _ds(json.dumps([{"n": 1, "keep": "false", "reason": "x"}], ensure_ascii=False))
_got = (v.get("1") or {}).get("keep")
check("DS: keep 字符串'false' → 应判 drop(keep=False)", _got is False,
      "(实际 keep=%r)" % _got)
if _got is not False:
    _defect("hard", "deepseek",
            "keep 字段为字符串时 bool(v.get('keep')) 误判：'false'→True（应 drop 却判留）",
            "lit/deepseek.py:92 bool(v.get('keep'))",
            "keep='false' → verdict.keep=True（应为 False）")

# (e) 顶层非 JSON（网关 HTML 错误页等）→ json.loads 抛原始 JSONDecodeError（非 RuntimeError）
try:
    _ds(b"<html>gateway 502 error</html>")
    check("DS: 顶层非 JSON → 应 RuntimeError", False, "(没抛)")
except RuntimeError:
    check("DS: 顶层非 JSON → RuntimeError 人话", True)
except Exception as e:
    check("DS: 顶层非 JSON → RuntimeError 人话", False,
          "(抛原始 %s)" % type(e).__name__)
    _defect("hard", "deepseek",
            "顶层非 JSON 响应抛原始 JSONDecodeError，未转人话 RuntimeError",
            "lit/deepseek.py:82 data = json.loads(raw) 未包 try",
            "%s" % type(e).__name__)

# (f) 正则命中 [...] 但内部非法 JSON（键未加引号）→ json.loads 抛原始异常
try:
    _ds("[{n:1,keep:true}]")
    check("DS: 数组内非法 JSON → 应 RuntimeError", False, "(没抛)")
except RuntimeError:
    check("DS: 数组内非法 JSON → RuntimeError 人话", True)
except Exception as e:
    check("DS: 数组内非法 JSON → RuntimeError 人话", False,
          "(抛原始 %s)" % type(e).__name__)
    _defect("hard", "deepseek",
            "正则命中的 [...] 内部非法 JSON 抛原始 JSONDecodeError，未转人话 RuntimeError",
            "lit/deepseek.py:89 for v in json.loads(m.group(0)) 未包 try",
            "%s" % type(e).__name__)


# ============================ 6. 畸形引擎回执（_render_receipt / _render_import_receipt） ============================
# 涉 Qt：offscreen 渲染。构建失败则跳过本节、不连累前面非 Qt 节。
_harvest = None
_app = None
try:
    from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402
    from ui import style  # noqa: E402
    from ui.pages.harvest_page import HarvestPage  # noqa: E402
    _app = QApplication.instance() or QApplication([])
    _app.setStyleSheet(style.QSS)
    _harvest = HarvestPage()
    _harvest.show()
    _app.processEvents()
except Exception as e:
    check("render: Qt/采集台 构建 → 不崩", False,
          "(%s: %s)" % (type(e).__name__, str(e)[:100]))
    _defect("infra", "render", "Qt 或 HarvestPage 构建失败（本节用例全部跳过）",
            "adversarial render 节初始化", "%s: %s" % (type(e).__name__, str(e)[:120]))


def _walk(layout):
    for i in range(layout.count()):
        it = layout.itemAt(i)
        w = it.widget() if it else None
        if w is not None:
            yield w
            lay = w.layout()
            if lay is not None:
                yield from _walk(lay)
        elif it is not None and it.layout() is not None:
            yield from _walk(it.layout())


if _harvest is not None:
    def _label_texts():
        return [w.text() for w in _walk(_harvest.receipt_box) if isinstance(w, QLabel)]

    def _no_crash(label: str, fn):
        """fn() 调 _render_receipt/_render_import_receipt。不崩=PASS；崩=FAIL+hard 缺陷。"""
        try:
            fn()
            _app.processEvents()
            check(label, True)
        except Exception as e:
            check(label, False, "(%s)" % type(e).__name__)
            _defect("hard", "render", label,
                    "ui/pages/harvest_page.py _render_receipt/_render_import_receipt",
                    "%s: %s" % (type(e).__name__, str(e)[:110]))

    _P = {"journal": "J Thorac Oncol", "mode": "latest", "reldate_days": 30,
          "inc_ed": False, "inc_lt": False, "topic": None}

    # --- _render_receipt 变体 ---
    _no_crash("render: 缺 counts", lambda: _harvest._render_receipt("J Thorac Oncol",
        {"found": 5, "items": [{"title": "t", "status": "new"}],
         "collection": {"exists": True, "key": "K"}}, _P))
    _no_crash("render: 缺 items", lambda: _harvest._render_receipt("J Thorac Oncol",
        {"found": 5, "counts": {"new": 2, "dup": 1, "suspect": 0},
         "collection": {"exists": True, "key": "K"}}, _P))
    _no_crash("render: counts 与 items 数不一致", lambda: _harvest._render_receipt(
        "J Thorac Oncol",
        {"found": 6, "counts": {"new": 5, "dup": 1},
         "items": [{"title": "only1", "status": "new"}],
         "collection": {"exists": True, "key": "K"}}, _P))
    # 软缺陷：统计行按 counts 显示（"新增 5"），与 items 实际 1 条不符 → 谎报（INV-04 精神）
    _defect("soft", "render",
            "counts.new 与 items 实际条数不一致时，统计行按 counts 显示（谎报）",
            "harvest_page.py:654 _stat_chip 用 counts.get 而非 len(items)",
            "显示「新增 5」但 items 仅 1 条 new")

    _no_crash("render: item 缺 title", lambda: _harvest._render_receipt("J Thorac Oncol",
        {"found": 1, "counts": {"new": 1}, "items": [{"status": "new"}],
         "collection": {"exists": True, "key": "K"}}, _P))

    # item 缺 status / 未知 status：不崩，但该 item 被静默丢弃（order 不含 "?"）
    _harvest._render_receipt("J Thorac Oncol",
        {"found": 1, "counts": {"new": 1}, "items": [{"title": "NoStatusItem"}],
         "collection": {"exists": True, "key": "K"}}, _P)
    _app.processEvents()
    check("render: item 缺 status → 不崩 +（软缺陷）item 静默不出现",
          "NoStatusItem" not in _label_texts())
    _defect("soft", "render",
            "items 中 status 缺失/未知值 的条目被静默丢弃（不在回执显示）",
            "harvest_page.py:682 groups.setdefault(it.get('status') or '?')；order 不含 '?'",
            "该 item 不可见")

    _harvest._render_receipt("J Thorac Oncol",
        {"found": 1, "counts": {"new": 1},
         "items": [{"title": "WeirdStatusItem", "status": "bizarre"}],
         "collection": {"exists": True, "key": "K"}}, _P)
    _app.processEvents()
    check("render: status 未知值 → 不崩 +（软缺陷）静默丢弃",
          "WeirdStatusItem" not in _label_texts())

    _no_crash("render: title 10k+换行+控制字符", lambda: _harvest._render_receipt(
        "J Thorac Oncol",
        {"found": 1, "counts": {"new": 1},
         "items": [{"title": "A" * 5000 + "\n\r\t" + "B" * 5000 + "\x00\x01\x1b",
                    "status": "new"}],
         "collection": {"exists": True, "key": "K"}}, _P))
    _no_crash("render: found 为负数", lambda: _harvest._render_receipt("J Thorac Oncol",
        {"found": -5, "counts": {}, "items": [],
         "collection": {"exists": True, "key": "K"}}, _P))
    # found 为字符串 → 第 661 行 "abc" >= 1000 抛 TypeError（硬缺陷）
    _no_crash("render: found 为字符串", lambda: _harvest._render_receipt("J Thorac Oncol",
        {"found": "abc", "counts": {}, "items": [],
         "collection": {"exists": True, "key": "K"}}, _P))
    _no_crash("render: collection 缺失", lambda: _harvest._render_receipt("J Thorac Oncol",
        {"found": 1, "counts": {"new": 1}, "items": [{"title": "t", "status": "new"}]}, _P))
    # payload(r) 为 list / None → 第 650 行 r.get(...) 抛 AttributeError（硬缺陷）
    _no_crash("render: payload(r) 为 list", lambda: _harvest._render_receipt(
        "J Thorac Oncol", ["a", "b"], _P))
    _no_crash("render: payload(r) 为 None", lambda: _harvest._render_receipt(
        "J Thorac Oncol", None, _P))
    # collection 为 list → 第 766 行 coll.get(...) 抛 AttributeError（硬缺陷）
    _no_crash("render: collection 为 list", lambda: _harvest._render_receipt("J Thorac Oncol",
        {"found": 1, "counts": {}, "items": [], "collection": ["x", "y"]}, _P))

    # --- _render_import_receipt 变体 ---
    _no_crash("render(import): 缺 counts", lambda: _harvest._render_import_receipt(_P,
        {"items": [{"title": "t", "status": "imported"}]}))
    _no_crash("render(import): 缺 items", lambda: _harvest._render_import_receipt(_P,
        {"counts": {"imported": 2, "failed": 1, "dup": 0}}))
    # collection 为 list → 第 975 行 coll.get(...) 抛 AttributeError（硬缺陷）
    _no_crash("render(import): collection 为 list", lambda: _harvest._render_import_receipt(_P,
        {"counts": {}, "items": [], "collection": ["z"]}))
    # payload 为 None / list → 第 916 行 r.get(...) 抛 AttributeError（硬缺陷）
    _no_crash("render(import): payload 为 None", lambda: _harvest._render_import_receipt(_P, None))
    _no_crash("render(import): payload 为 list", lambda: _harvest._render_import_receipt(_P, ["x"]))


# ============================ 7. FuncWorker BaseException 兜底（防 _running 永不复位） ============================
# job 抛 SystemExit（BaseException 子类，不被 except Exception 捕获）→ run 应仍发 failed 信号、
# 线程正常收尾；否则 done/failed 均不发、_running 永不复位、UI 永卡。复用上面 render 节的 _app。
if _app is not None:
    from ui.workers import FuncWorker  # noqa: E402

    def _se_job():
        raise SystemExit("boom")

    _fw = FuncWorker(_se_job)
    _fw_state = {"failed": None}
    _fw.failed.connect(lambda msg: _fw_state.__setitem__("failed", msg))
    _fw.start()
    _fw.wait(5000)
    _app.processEvents()
    check("workers: job 抛 SystemExit → failed 信号发射 + 线程收尾",
          _fw_state["failed"] is not None and "SystemExit" in _fw_state["failed"]
          and not _fw.isRunning(),
          "(failed=%r isRunning=%s)" % (_fw_state["failed"], _fw.isRunning()))


# ============================ 收尾 ============================

shutil.rmtree(_TMPDIR, ignore_errors=True)

# 还原 token / 保持网闸（防收尾阶段误触真实联网）
if _ENV_TOKEN_ORIG is not None:
    os.environ["DEEPSEEK_TOKEN"] = _ENV_TOKEN_ORIG
else:
    os.environ.pop("DEEPSEEK_TOKEN", None)
_urlreq.urlopen = _block_net

if _DEFECTS:
    print("\n" + "=" * 40)
    print("产品缺陷候选清单（只报不修，共 %d 条）：" % len(_DEFECTS))
    for i, d in enumerate(_DEFECTS, 1):
        print("  [%d] (%s) [%s] %s" % (i, d["sev"], d["cat"], d["phen"]))
        print("        定位: %s" % d["loc"])
        print("        现象: %s" % d["err"])

if os.environ.get("TRACKEEP_CI") == "1":
    print("[CI] TRACKEEP_CI 联网检查跳过 %d 次" % _CI_SKIPS["n"])

print("\n" + "=" * 40)
print("%d/%d 项通过" % (sum(checks), len(checks)))
sys.exit(0 if all(checks) else 1)
