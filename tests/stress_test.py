# -*- coding: utf-8 -*-
"""并发/竞态升档实测：不弹窗、不联网、不真 spawn 引擎、不碰 Mecha-Core 真实文件。

把 INV-09（单飞）+ VS-06（_last_params 锁定）+ VS-07（渲染清空无泄漏）从 gui_test 的
单次/3 轮量级升到 ≥50 轮（稳定优先档），并全程叠加 random.uniform 时序扰动（母法 7.4：
种子必录、可复现）。断言源 = .project/invariants.yaml + .project/vulnerable-scenarios.yaml。

场景（每场景 ≥50 轮）：
  1. 检索连点：慢引擎（job 内 sleep 0.1–0.2s）+ running 窗口内连击检索按钮 ≥5 次
     → run_search 恰 1 次（INV-09 单飞）
  2. 导入连点：确认框 Yes + 连击导入按钮 ≥5 次 → run_import 恰 1 次（INV-09 单飞）
  3. running 窗口乱点：检索运行中触发导入 / AI 复筛 / 切刊 / 切模式 → 全被拦
     （引擎调用不增、deepseek 不调、_last_params 不被污染、检索目标仍是发起时锁定的刊）
  4. 渲染→清空 ×50：控件计数恒定（VS-07 升档版）
  5. 时序扰动：random.uniform 抖动 + seed 打印 / 可复现

绝不联网、绝不真跑引擎写路径：engine.run_search/run_import 一律换可编程 mock；
json/md/台账路径全 patch 到 tests/_tmp_stress（gitignore 覆盖 tests/_tmp_*）。

运行：D:\\trackeep-lit\\venv\\Scripts\\python.exe tests\\stress_test.py
"""
import os
import sys
import time
import random
import traceback
from pathlib import Path

# 必须在 import Qt 之前：无显示器渲染 + 自检环境标记
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["TRACKEEP_SELFTEST"] = "1"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

# 母法 7.4：种子必录、可复现。STRESS_SEED 环境变量可覆写（默认 42）。
SEED = int(os.environ.get("STRESS_SEED", "42"))
random.seed(SEED)
print(f"seed={SEED}")

ROUNDS = 50   # 每场景最少 50 轮（稳定优先档；本档位远超 gui_test 的 3 轮）

_TMPDIR = Path(__file__).resolve().parent / "_tmp_stress"
_TMPDIR.mkdir(exist_ok=True)


def _tmp(name: str) -> Path:
    """tests/_tmp_stress/<name>：测试自管的临时路径（gitignore 覆盖 tests/_tmp_*）。"""
    p = _TMPDIR / name
    p.unlink(missing_ok=True)
    return p


# ---- 真实文件全桩到临时路径（绝不读写 Mecha-Core / 凭证）----
from lit import deepseek, engine, journals, ledger, overrides, strategy  # noqa: E402

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

# 默认全开后胸外 AI 默认开 → _on_import_clicked 在 _ai_verdicts is None 时弹 information 锁死
# （offscreen 模态挂死）。场景 1-5 用 JTO（胸外）测单飞/渲染/锁定，与 AI 无关——先显式关
# 胸外 DeepSeek 隔离 AI 门控；场景 6 风暴自带 _ST 覆写（enabled=True）+ information 桩，不受影响。
strategy.save_category("胸部肿瘤与胸外科", {"editorial": False, "letter": False,
    "topicFilter": {"enabled": False, "terms": ""},
    "deepseek": {"enabled": False, "criteria": ""}})


# ---- 合成回执（与 gui_test 同构）----
def _item(status, n=1, title=None):
    return [{"title": (title or "%s 文献 %d" % (status, i)),
             "status": status, "type": "Journal Article", "pmid": 10000 + i,
             "doi": "10.1000/%d" % i, "hasAbstract": True} for i in range(n)]


def _receipt(found=31, new=5, dup=3, suspect=2, exists=True):
    items = _item("new", new) + _item("dup", dup) + _item("suspect", suspect)
    return {"found": found, "query": "synth[ta]", "journal": "J Thorac Oncol",
            "mode": "latest",
            "counts": {"new": new, "dup": dup, "suspect": suspect},
            "items": items,
            "collection": {"exists": exists, "key": "KEYXYZ"},
            "taMismatch": False, "broadCount": 9}


_PARAMS = {"journal": "J Thorac Oncol", "mode": "latest", "reldate_days": 30,
           "inc_ed": False, "inc_lt": False, "topic": None}


# ---- engine / deepseek 桥无条件换成可编程 mock（绝不真 spawn 引擎 / 真联网）----
class EngineMock:
    """记录调用 + 参数；run_search/run_import 内 sleep 模拟慢引擎，撑开 running 窗口。"""

    def __init__(self):
        self.calls = []
        self.search_delay = 0.15
        self.import_delay = 0.15
        self.search_return = _receipt(found=31, new=5, dup=3, suspect=2)
        self.import_return = {"found": 8, "journal": "J Thorac Oncol", "mode": "latest",
                              "counts": {"imported": 5, "failed": 0, "dup": 3, "suspect": 0},
                              "items": _item("imported", 5) + _item("dup", 3),
                              "collection": {"exists": True, "key": "KEYXYZ"}}

    def run_search(self, journal, **kw):
        self.calls.append(("search", journal, dict(kw)))
        if self.search_delay:
            time.sleep(self.search_delay)
        return self.search_return

    def run_import(self, journal, **kw):
        self.calls.append(("import", journal, dict(kw)))
        if self.import_delay:
            time.sleep(self.import_delay)
        return self.import_return

    def reset(self):
        self.calls = []


class DeepSeekMock:
    """记录 classify 调用；running 窗口内 _start_ai_filter 应被拦 → 0 调用。"""

    def __init__(self):
        self.calls = []

    def classify(self, items, criteria, **kw):
        self.calls.append((len(items), criteria))
        return {str(it.get("pmid")): {"keep": True, "reason": "mock"} for it in items}

    def reset(self):
        self.calls = []


_eng = EngineMock()
_ds = DeepSeekMock()
engine.run_search = _eng.run_search
engine.run_import = _eng.run_import
deepseek.classify = _ds.classify


# ---- TRACKEEP_CI=1：urllib 桩成立即失败 + 计数（本应用不使用 requests）----
_CI_SKIPS = {"n": 0}
if os.environ.get("TRACKEEP_CI") == "1":
    import urllib.request as _urlreq

    def _ci_block(*_a, **_k):
        _CI_SKIPS["n"] += 1
        raise RuntimeError("TRACKEEP_CI: 联网调用已跳过（CI 无外网）")

    _urlreq.urlopen = _ci_block


from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from ui import style  # noqa: E402
from ui.main_window import MainWindow, page_index  # noqa: E402

checks = []


def check(name: str, fn) -> None:
    try:
        fn()
        checks.append(True)
        print(f"[PASS] {name}")
    except Exception:
        checks.append(False)
        print(f"[FAIL] {name}")
        traceback.print_exc()


app = QApplication(sys.argv)
app.setStyleSheet(style.QSS)

win = MainWindow()
win.show()
app.processEvents()

harvest = win.pages[page_index("采集台")]


def _drain(page, timeout=5.0):
    """泵事件等页面的后台线程收尾（run_async 的 worker 跑完 done/failed）。"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        app.processEvents()
        if not getattr(page, "_workers", []):
            return True
        time.sleep(0.01)
    return False


def _walk(layout):
    """递归遍历 receipt_box 下所有 widget（QLabel/QPushButton/QFrame…，含嵌套布局）。"""
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


def _wait_calls(predicate, timeout=3.0):
    """等 predicate(_eng) 成立（后台 worker 已记下调用），避免主线程 snapshot 与
    后台线程 append 赛跑（worker 在 run_search/run_import 开头记调用、随后 sleep，
    主线程 click 后立刻读 _eng.calls 可能读到空）。"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        if predicate():
            return True
        time.sleep(0.002)
    return False


def _patch_question(ans):
    orig = QMessageBox.question
    QMessageBox.question = lambda *a, **k: ans
    return orig


def _search_calls():
    return [c for c in _eng.calls if c[0] == "search"]


def _import_calls():
    return [c for c in _eng.calls if c[0] == "import"]


def _reset_running():
    """每轮收尾：确保 _running 归位、无残留 worker，避免跨轮污染。"""
    if harvest._workers:
        _drain(harvest, 3)
    harvest._running = False
    harvest._end_running_ui()   # 停秒表 + 收进度条 + 解冻树/配置（未运行态调用是幂等 no-op）
    harvest._running = False


# ============================ 1. 检索连点 ×50（INV-09 单飞）============================

def search_mash():
    for rnd in range(ROUNDS):
        _reset_running()
        _eng.reset()
        harvest._select_journal("J Thorac Oncol")
        app.processEvents()
        # 慢引擎：撑开 running 窗口（job 后台 sleep），连点全落在 running 态内
        _eng.search_delay = random.uniform(0.10, 0.20)
        clicks = 5 + (rnd % 3)   # 5/6/7 轮转，每轮都 ≥5
        for _ in range(clicks):
            harvest.search_btn.click()
            time.sleep(random.uniform(0, 0.003))   # 人类连点间隔抖动
        # 等后台 worker 记下这一次调用（避免与线程 append 赛跑读到 0）
        assert _wait_calls(lambda: _search_calls()), f"round {rnd}: 检索 worker 未记录调用"
        # 连点 N 次，_start_search 的 _running 守卫只放行第一次 → run_search 恰 1 次
        n = len(_search_calls())
        assert n == 1, f"round {rnd}: 检索连点 {clicks} 次 → run_search {n} 次（应 1）"
        assert harvest._running, f"round {rnd}: 连点后应处 running 态"
        ok = _drain(harvest, 5)
        assert ok, f"round {rnd}: 检索 worker 未在 5s 内收尾"
        assert not harvest._running, f"round {rnd}: 收尾后 _running 应归位"
        # drain 后终值断言（主驾加固）：全部 worker 已收尾、记录必齐——晚到的重复 spawn 无处可藏
        n_final = len(_search_calls())
        assert n_final == 1, f"round {rnd}: drain 后 run_search 终值 {n_final}（应 1，疑晚到重复 spawn）"


check("INV-09: 检索连点 ×%d → run_search 恰 1 次/轮" % ROUNDS, search_mash)


# ============================ 2. 导入连点 ×50（INV-09 单飞）============================

def import_mash():
    for rnd in range(ROUNDS):
        _reset_running()
        _eng.reset()
        harvest._select_journal("J Thorac Oncol")
        app.processEvents()
        # 渲染 new>0 的回执，造出导入按钮
        harvest._render_receipt("J Thorac Oncol", _receipt(found=31, new=5), dict(_PARAMS))
        harvest._last_params = dict(_PARAMS)
        app.processEvents()
        imp_btns = [b for b in harvest._action_btns if "Zotero" in b.text()]
        assert imp_btns, f"round {rnd}: 前置缺导入按钮"
        _eng.import_delay = random.uniform(0.10, 0.20)
        # 确认框一律 Yes：验证连点被 _running 守卫拦，而非被取消框挡掉
        orig_q = _patch_question(QMessageBox.Yes)
        clicks = 5 + (rnd % 3)
        try:
            for _ in range(clicks):
                imp_btns[0].click()
                time.sleep(random.uniform(0, 0.003))
        finally:
            QMessageBox.question = orig_q
        assert _wait_calls(lambda: _import_calls()), f"round {rnd}: 导入 worker 未记录调用"
        n = len(_import_calls())
        assert n == 1, f"round {rnd}: 导入连点 {clicks} 次 → run_import {n} 次（应 1）"
        assert harvest._running, f"round {rnd}: 连点后应处 running 态"
        ok = _drain(harvest, 5)
        assert ok, f"round {rnd}: 导入 worker 未在 5s 内收尾"
        assert not harvest._running
        n_final = len(_import_calls())
        assert n_final == 1, f"round {rnd}: drain 后 run_import 终值 {n_final}（应 1，疑晚到重复 spawn）"


check("INV-09: 导入连点 ×%d → run_import 恰 1 次/轮" % ROUNDS, import_mash)


# ============================ 3. running 窗口乱点 ×50（INV-09 + VS-06）============================

def running_interleave():
    for rnd in range(ROUNDS):
        _reset_running()
        _eng.reset()
        _ds.reset()
        harvest._select_journal("J Thorac Oncol")
        app.processEvents()
        # 预置「上一次检索的锁定目标 + 结果」，验证乱点不污染
        harvest._last_params = dict(_PARAMS)
        harvest._last_result = _receipt(found=31, new=5)
        _eng.search_delay = random.uniform(0.10, 0.20)
        # 发起检索：_start_search 同步置 _running=True、清 _last_params=None、锁 _search_journal
        harvest.search_btn.click()
        assert harvest._running, f"round {rnd}: 前置未进 running"
        assert harvest._last_params is None, f"round {rnd}: 检索发起应清 _last_params"
        # 等检索 worker 记下自身那一次调用再 snapshot，避免与后台 append 赛跑
        assert _wait_calls(lambda: _search_calls()), f"round {rnd}: 检索 worker 未记录调用"
        calls_before = len(_eng.calls)
        ds_before = len(_ds.calls)
        # 乱点：导入（确认框 Yes）/ AI 复筛 / 切刊 / 切模式 —— 全应被 _running 守卫拦
        orig_q = _patch_question(QMessageBox.Yes)
        try:
            harvest._on_import_clicked(harvest._last_result)   # _running 守卫拦（不弹框、不 spawn）
            harvest._start_ai_filter()                          # _running 守卫拦（不调 deepseek）
        finally:
            QMessageBox.question = orig_q
        harvest._select_journal("Ann Thorac Surg")             # 切刊（程序化；不改 _last_params）
        harvest.rb_back.setChecked(True)                        # 切到回填模式
        harvest.rb_latest.setChecked(True)                      # 切回最新模式
        # 断言：引擎调用不增、复筛不调、_last_params 未被污染（检索发起后应仍 None）
        assert len(_eng.calls) == calls_before, \
            f"round {rnd}: running 内乱点新增引擎调用 {_eng.calls[calls_before:]}"
        assert len(_ds.calls) == ds_before, \
            f"round {rnd}: running 内 _start_ai_filter 不应调 deepseek.classify"
        assert harvest._last_params is None, \
            f"round {rnd}: 切刊/切模式不应回填 _last_params"
        # 收尾检索：done 锁定的应是发起时锁定的刊（J Thorac Oncol），不是乱点切到的 Ann Thorac Surg
        ok = _drain(harvest, 5)
        assert ok, f"round {rnd}: 检索 worker 未在 5s 内收尾"
        assert harvest._last_params is not None, f"round {rnd}: 检索成功应锁定 _last_params"
        assert harvest._last_params["journal"] == "J Thorac Oncol", \
            f"round {rnd}: 检索目标被切刊污染 → {harvest._last_params['journal']}"


check("INV-09/VS-06: running 窗口乱点（导入/复筛/切刊/切模式）全被拦 ×%d" % ROUNDS,
      running_interleave)


# ============================ 4. 渲染→清空 ×50（VS-07 升档）============================

def render_clear_loop():
    from PySide6.QtWidgets import QLabel, QPushButton, QFrame

    def _widget_count():
        return sum(1 for w in _walk(harvest.receipt_box)
                   if isinstance(w, (QLabel, QPushButton, QFrame)))

    _reset_running()
    r = _receipt(found=31, new=5, dup=3, suspect=2)
    params = dict(_PARAMS)
    baseline = None
    counts = []
    for rnd in range(ROUNDS):
        harvest._render_receipt("J Thorac Oncol", r, params)
        app.processEvents()
        c = _widget_count()
        counts.append(c)
        if baseline is None:
            baseline = c
        else:
            assert c == baseline, \
                f"round {rnd}: 控件计数漂移 {baseline}→{c}（前 8 轮 {counts[:8]}）"
        harvest._clear_receipt()
        app.processEvents()   # deleteLater 在事件循环里真正释放
        time.sleep(random.uniform(0, 0.002))
    # 末轮再渲染一次，控件数应与首轮一致（无累积残留）
    harvest._render_receipt("J Thorac Oncol", r, params)
    app.processEvents()
    assert _widget_count() == baseline, "末轮渲染控件数与首轮不一致（VS-07 累积泄漏）"


check("VS-07: 渲染→清空 ×%d 控件计数恒定（无累积泄漏）" % ROUNDS, render_clear_loop)


# ============================ 5. 时序扰动 seed 可复现（母法 7.4）============================

def seed_reproducible():
    # seed 已在开跑时打印；本断言验证「同 seed → 同抖动序列」（独立 Random 实例，不扰主流程）
    a = random.Random(SEED)
    b = random.Random(SEED)
    seq_a = [a.uniform(0.10, 0.20) for _ in range(20)]
    seq_b = [b.uniform(0.10, 0.20) for _ in range(20)]
    assert seq_a == seq_b, "同 seed 必须产生同 uniform 序列"
    # 不同 seed 应（几乎必然）产生不同序列
    c = random.Random(SEED + 1)
    seq_c = [c.uniform(0.10, 0.20) for _ in range(20)]
    assert seq_c != seq_a, "不同 seed 不应产生同序列"


check("母法7.4: 时序扰动 seed 打印 + 同 seed 可复现", seed_reproducible)


# ============================ 6. 随机事件风暴 ×50（BL-02：真随机序列）============================
# 复用 SEED 机制（STRESS_SEED 覆写、seed 已打印可复现）；独立 random.Random 不扰既有场景流。
# 每轮从动作池随机抽 8–15 步；引擎 mock 可编程（随机延迟 + 5 种回执变体，含未知 status /
# counts≠items 走 BL-07①② 新渲染路径）；deepseek mock 随机判决或抛 RuntimeError。

def random_event_storm():
    import json
    rng = random.Random(SEED + 600)            # 独立 RNG，不扰主流程 random 序列
    all_jnames = journals.all_journals()       # 10 个合法刊名（树叶子 = 推荐目录名）
    cat_nodes = list(harvest._cat_nodes.values())

    # 启用一个分类的 DeepSeek → 选该类期刊 + new>0 时出 AI 复筛按钮（否则「若在」跳过）
    _ST.write_text(json.dumps({"version": 1, "categories": {
        "胸部肿瘤与胸外科": {"editorial": False, "letter": False,
                          "topicFilter": {"enabled": False, "terms": ""},
                          "deepseek": {"enabled": True, "criteria": "主体聚焦肺癌"}}}},
        ensure_ascii=False), encoding="utf-8")

    # ---- 回执变体工厂（5 种，覆盖 BL-07①② 新渲染路径）----
    def _sitem(status, n=1, title=None, base_pmid=20000):
        return [{"title": (title or "%s 风暴 %d" % (status, i)), "status": status,
                 "type": "Journal Article", "pmid": base_pmid + i, "doi": "10.2/%d" % i,
                 "hasAbstract": True} for i in range(n)]

    def make_search_receipt(journal):
        v = rng.choice(["normal", "new0", "found0", "unknown", "mismatch"])
        base = {"query": "storm[ta]", "journal": journal, "mode": "latest",
                "collection": {"exists": True, "key": "STORMK"}, "taMismatch": False,
                "broadCount": 3}
        if v == "found0":
            return {**base, "found": 0, "counts": {"new": 0, "dup": 0, "suspect": 0}, "items": []}
        if v == "unknown":                              # 含未知 status → BL-07② 其他卡
            items = _sitem("new", 2) + [{"title": "weird-storm", "status": "bizarre"},
                                        {"title": "nostatus-storm"}]
            return {**base, "found": len(items), "counts": {"new": 2, "dup": 0, "suspect": 0},
                    "items": items}
        if v == "mismatch":                             # counts≠items → BL-07① 警示
            items = _sitem("new", 1) + _sitem("dup", 1)
            return {**base, "found": 5, "counts": {"new": 3, "dup": 1, "suspect": 0},
                    "items": items}
        if v == "new0":
            items = _sitem("dup", 2) + _sitem("suspect", 1)
            return {**base, "found": 3, "counts": {"new": 0, "dup": 2, "suspect": 1},
                    "items": items}
        items = _sitem("new", 2) + _sitem("dup", 1) + _sitem("suspect", 1)   # normal
        return {**base, "found": 4, "counts": {"new": 2, "dup": 1, "suspect": 1},
                "items": items}

    def make_import_receipt(journal):
        v = rng.choice(["ok", "failed", "unknown", "mismatch"])
        base = {"journal": journal, "mode": "latest",
                "collection": {"exists": True, "key": "STORMK"}}
        if v == "unknown":
            items = _sitem("imported", 1) + [{"title": "weird-imp", "status": "bizarre"}]
            return {**base, "counts": {"imported": 1, "failed": 0, "dup": 0}, "items": items}
        if v == "mismatch":
            items = _sitem("imported", 1)
            return {**base, "counts": {"imported": 3, "failed": 1, "dup": 0}, "items": items}
        if v == "failed":
            items = _sitem("imported", 2) + _sitem("failed", 1) + _sitem("dup", 1)
            return {**base, "counts": {"imported": 2, "failed": 1, "dup": 1}, "items": items}
        items = _sitem("imported", 2) + _sitem("dup", 1)                       # ok
        return {**base, "counts": {"imported": 2, "failed": 0, "dup": 1}, "items": items}

    # ---- 风暴用 engine / deepseek mock（随机延迟 + 随机回执 / 判决或抛），记入 _eng.calls ----
    _orig_search = engine.run_search
    _orig_import = engine.run_import
    _orig_ds = deepseek.classify

    def storm_search(journal, **kw):
        _eng.calls.append(("search", journal, dict(kw)))   # 记入供 _search_calls 读
        time.sleep(rng.uniform(0, 0.15))
        return make_search_receipt(journal)

    def storm_import(journal, **kw):
        _eng.calls.append(("import", journal, dict(kw)))
        time.sleep(rng.uniform(0, 0.15))
        return make_import_receipt(journal)

    def storm_classify(items, criteria, **kw):
        if rng.random() < 0.3:
            raise RuntimeError("storm: DeepSeek 随机失败")
        time.sleep(rng.uniform(0, 0.05))
        return {str(it.get("pmid")): {"keep": rng.choice([True, False]), "reason": "storm"}
                for it in items}

    engine.run_search = storm_search
    engine.run_import = storm_import
    deepseek.classify = storm_classify

    STORM_ROUNDS = 50
    try:
        for rnd in range(STORM_ROUNDS):
            action_log = []
            _reset_running()
            _eng.reset()
            harvest._select_journal(rng.choice(all_jnames))
            app.processEvents()
            search_clicks_nr = 0      # 非 running 窗口的检索点击（INV-09 有效点击上界）
            import_clicks_nr = 0

            for _ in range(rng.randint(8, 15)):
                action = rng.choice(["tree", "mode", "backfill", "exc_ed", "exc_lt",
                                     "topic", "search", "ai", "import", "jitter"])
                action_log.append(action)
                if action == "tree":
                    if rng.random() < 0.5:
                        harvest._select_journal(rng.choice(all_jnames))
                    else:
                        harvest.tree.setCurrentItem(rng.choice(cat_nodes))
                elif action == "mode":
                    (harvest.rb_latest if rng.random() < 0.5 else harvest.rb_back).setChecked(True)
                elif action == "backfill":
                    harvest.rb_back.setChecked(True)
                    harvest.cb_year.setCurrentIndex(rng.randrange(harvest.cb_year.count()))
                    harvest.cb_month.setCurrentIndex(rng.randrange(harvest.cb_month.count()))
                elif action == "exc_ed":
                    harvest.cb_editorial.setChecked(rng.choice([True, False]))
                elif action == "exc_lt":
                    harvest.cb_letter.setChecked(rng.choice([True, False]))
                elif action == "topic":
                    harvest.topic_edit.setText(rng.choice(["", "lung[tiab]", "筛查"]))
                    harvest._on_exception_changed()
                elif action == "search":
                    if not harvest._running:
                        search_clicks_nr += 1
                    harvest.search_btn.click()
                elif action == "ai":
                    aibtns = [b for b in harvest._action_btns if "DeepSeek" in b.text()]
                    if aibtns and not harvest._running:
                        aibtns[0].click()
                elif action == "import":
                    impbtns = [b for b in harvest._action_btns if "Zotero" in b.text()]
                    if impbtns:
                        if not harvest._running:
                            import_clicks_nr += 1
                        orig_q = _patch_question(rng.choice([QMessageBox.Yes, QMessageBox.No]))
                        # 6b-2 门控：AI-enabled 刊未跑 AI 就导入 → 弹 information（模态，
                        # offscreen 会阻塞）→ 一并桩掉自动 Ok，让锁死路径不卡死风暴
                        orig_info = QMessageBox.information
                        QMessageBox.information = lambda *a, **k: QMessageBox.Ok
                        try:
                            impbtns[0].click()
                        finally:
                            QMessageBox.question = orig_q
                            QMessageBox.information = orig_info
                # jitter 无显式分支：仅下方 processEvents + 抖动
                app.processEvents()
                time.sleep(rng.uniform(0, 0.005))

            ok = _drain(harvest, 8)
            sc = _search_calls()
            ic = _import_calls()
            try:
                assert ok, "worker 未在 8s 内收尾"
                assert not harvest._running, "_running 未归位"
                assert harvest.tree.isEnabled(), "树未解冻"
                assert harvest._config_panel.isEnabled(), "配置区未解冻"
                assert len(sc) <= search_clicks_nr, \
                    f"run_search {len(sc)} > 有效点击 {search_clicks_nr}"
                assert len(ic) <= import_clicks_nr, \
                    f"run_import {len(ic)} > 有效点击 {import_clicks_nr}"
                # VS-06：_last_params（若非 None）的 journal 必属发起检索时的刊
                if harvest._last_params is not None:
                    lj = harvest._last_params.get("journal")
                    assert lj in all_jnames, f"_last_params.journal={lj!r} 非合法刊"
                    if sc:
                        assert lj == sc[-1][1], \
                            f"_last_params.journal={lj!r} ≠ 末次检索 {sc[-1][1]!r}"
            except AssertionError as e:
                print(f"风暴失败：seed={SEED} round={rnd} seq={action_log} "
                      f"search={len(sc)}/{search_clicks_nr} import={len(ic)}/{import_clicks_nr} "
                      f"params={harvest._last_params} :: {e}")
                raise
    finally:
        engine.run_search = _orig_search
        engine.run_import = _orig_import
        deepseek.classify = _orig_ds


check("BL-02: 随机事件风暴 ×%d（不崩/_running 归位/单飞/_last_params 锁定）" % 50,
      random_event_storm)


# ============================ 收尾 ============================
import shutil  # noqa: E402

_reset_running()
for p in win.pages:
    if getattr(p, "_workers", None):
        _drain(p, 2)
shutil.rmtree(_TMPDIR, ignore_errors=True)

if os.environ.get("TRACKEEP_CI") == "1":
    print(f"[CI] TRACKEEP_CI 联网检查跳过 {_CI_SKIPS['n']} 次")

print(f"\n{'=' * 40}\n{sum(checks)}/{len(checks)} 项通过")
sys.exit(0 if all(checks) else 1)
