# -*- coding: utf-8 -*-
"""界面离屏回归：不弹窗、不联网、不真 spawn 引擎、不碰 Mecha-Core 真实文件。

断言来源：.project/invariants.yaml（INV-02/04/09/11）+ .project/vulnerable-scenarios.yaml
（VS-06/07 + 受控建 VS-09）。所有 json/md/台账一律 patch 模块级常量到 tests/_tmp_*；
engine.run_search/run_import 无条件换成可编程 mock；urllib 在 TRACKEEP_CI=1 时再桩一层。

运行：venv\\Scripts\\python.exe tests\\gui_test.py
"""
import os
import sys
import traceback
from pathlib import Path

# 必须在 import Qt 之前：无显示器渲染 + 自检环境标记
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["TRACKEEP_SELFTEST"] = "1"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

_TMPDIR = Path(__file__).resolve().parent / "_tmp_gui"
_TMPDIR.mkdir(exist_ok=True)


def _tmp(name: str) -> Path:
    p = _TMPDIR / name
    p.unlink(missing_ok=True)
    return p


# ---- 真实文件全桩到临时路径（绝不读写 Mecha-Core / 凭证）----
from lit import config, engine, journals, ledger, overrides, strategy, zotero  # noqa: E402

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


# ---- engine 桥无条件换成可编程 mock（绝不真 spawn 引擎）----
class EngineMock:
    """记录调用 + 参数，返回合成回执。run_search/run_import 同构。"""

    def __init__(self):
        self.calls = []                                 # [(kind, journal, kwargs)]
        self.search_return = _receipt(found=31)
        self.import_return = _import_receipt(imported=5, failed=0, dup=3)

    def run_search(self, journal, **kw):
        self.calls.append(("search", journal, dict(kw)))
        return self.search_return

    def run_import(self, journal, **kw):
        self.calls.append(("import", journal, dict(kw)))
        return self.import_return

    def reset(self):
        self.calls = []


def _item(status, n=1, title=None):
    """造 n 条同 status 的合成 item。"""
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


def _import_receipt(imported=5, failed=0, dup=3, suspect=0, exists=True):
    items = (_item("imported", imported) + _item("failed", failed)
             + _item("dup", dup) + _item("suspect", suspect))
    return {"found": imported + failed + dup + suspect, "journal": "J Thorac Oncol",
            "mode": "latest",
            "counts": {"imported": imported, "failed": failed, "dup": dup,
                       "suspect": suspect},
            "items": items,
            "collection": {"exists": exists, "key": "KEYXYZ"}}


_eng = EngineMock()
engine.run_search = _eng.run_search
engine.run_import = _eng.run_import

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
from ui.main_window import MainWindow, PAGE_NAMES, page_index  # noqa: E402

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


def _drain(page, timeout=10.0):
    """泵事件等页面的后台线程收尾（run_async 的 worker 跑完 done/failed）。"""
    import time
    t0 = time.time()
    while time.time() - t0 < timeout:
        app.processEvents()
        if not getattr(page, "_workers", []):
            return True
        time.sleep(0.01)
    return False


def _walk(layout):
    """递归遍历 receipt_box 下所有 widget（QLabel/QPushButton/QFrame…）。"""
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


def _label_texts(page):
    from PySide6.QtWidgets import QLabel
    return [w.text() for w in _walk(page.receipt_box) if isinstance(w, QLabel)]


def _button_texts(page):
    from PySide6.QtWidgets import QPushButton
    return [w.text() for w in _walk(page.receipt_box) if isinstance(w, QPushButton)]


# ============================ 1. 主窗 + 逐页切换 ============================

def main_builds():
    assert win.windowTitle().startswith(config.APP_NAME)
    assert harvest is not None


check("主窗口构建 + 首屏渲染", main_builds)


def page_switch():
    for i, name in enumerate(PAGE_NAMES):
        win.nav.setCurrentRow(i)
        app.processEvents()
        assert win.stack.currentIndex() == i


check("逐页切换（采集台/设置/使用说明）不崩", page_switch)


# ============================ 2. 采集台树路由 ============================

def tree_routing():
    # 分类节点 + 叶子都存在
    cats = list(harvest._cat_nodes.keys())
    assert len(cats) == 5, f"应有 5 分类节点，实际 {cats}"
    # 选分类节点 → 右栈切策略表单
    cat_node = harvest._cat_nodes["胸部肿瘤与胸外科"]
    harvest.tree.setCurrentItem(cat_node)
    app.processEvents()
    assert harvest.stack.currentWidget() is harvest.category_form
    # 选叶子 → 右栈切操作面板
    harvest._select_journal("Ann Thorac Surg")
    app.processEvents()
    assert harvest.stack.currentWidget() is harvest.journal_panel
    assert harvest.current_journal() == "Ann Thorac Surg"


check("采集台树：分类→策略表单 / 叶子→操作面板", tree_routing)


# ============================ 3. _render_receipt 渲染 + 分组计数 ============================

def render_receipt():
    r = _receipt(found=31, new=5, dup=3, suspect=2)
    params = {"journal": "J Thorac Oncol", "mode": "latest", "reldate_days": 30,
              "inc_ed": False, "inc_lt": False, "topic": None}
    harvest._render_receipt("J Thorac Oncol", r, params)
    app.processEvents()
    texts = _label_texts(harvest)
    # 三组分组标题都在，且条目数正确
    assert any("新增" in t and "5 篇" in t for t in texts), "新增组标题缺失"
    assert any("去重" in t and "3 篇" in t for t in texts), "去重组标题缺失"
    assert any("疑似" in t and "2 篇" in t for t in texts), "疑似组标题缺失"
    assert any("导入到 Zotero" in t for t in _button_texts(harvest)), "导入按钮缺失"


check("回执渲染：合成 found=31 分组条目数正确", render_receipt)


# ============================ 4. INV-11：found>=1000 告警 ============================

def retmax_warning():
    r = _receipt(found=1000, new=5, dup=3, suspect=2)
    harvest._render_receipt("J Thorac Oncol", r, None)
    app.processEvents()
    texts = _label_texts(harvest)
    assert any(("上限" in t or "截断" in t) for t in texts), \
        f"found=1000 未出现截断告警文案：{[t for t in texts if '截' in t or '上限' in t]}"


check("INV-11: found=1000 → 截断告警文案出现", retmax_warning)


# ============================ 5. INV-04：failed>0 重试按钮 ============================

def import_retry_button():
    # failed>0 → 重试按钮出现
    harvest._render_import_receipt(
        {"journal": "J Thorac Oncol", "mode": "latest", "reldate_days": 30},
        _import_receipt(imported=3, failed=2, dup=1))
    app.processEvents()
    assert any("重试" in t for t in _button_texts(harvest)), "failed>0 缺重试按钮"
    # failed=0 → 无重试按钮
    harvest._render_import_receipt(
        {"journal": "J Thorac Oncol", "mode": "latest", "reldate_days": 30},
        _import_receipt(imported=5, failed=0, dup=2))
    app.processEvents()
    assert not any("重试" in t for t in _button_texts(harvest)), "failed=0 不应有重试按钮"


check("INV-04: failed>0 出重试 / failed=0 无重试", import_retry_button)


# ============================ 6. INV-09：单飞——运行态互斥 ============================

def single_flight():
    # 先渲染一个回执，造出动作按钮（导入/复筛）
    harvest._render_receipt("J Thorac Oncol", _receipt(found=31), None)
    app.processEvents()
    action_btns = list(harvest._action_btns)
    assert action_btns, "前置：回执应有动作按钮"
    # 进入 running 态：检索按钮 disabled（config_panel 禁用级联）+ 动作按钮整体禁用
    harvest._running = True
    harvest._begin_running_ui("检索", "近 30 天")
    harvest._set_action_btns_enabled(False)
    app.processEvents()
    assert not harvest.search_btn.isEnabled(), "running 态检索按钮应禁用"
    assert all(not b.isEnabled() for b in action_btns), "动作按钮未整体禁用"
    assert not harvest.tree.isEnabled(), "期刊树应冻结"
    # 收尾：恢复 UI（避免污染后续测试）
    harvest._end_running_ui()
    harvest._running = False
    harvest._set_action_btns_enabled(True)


check("INV-09: running 态检索按钮+动作按钮禁用", single_flight)


def running_blocks_reentry():
    # _running=True 时：导入入口 / AI 复筛入口直接返回，不调引擎
    _eng.reset()
    harvest._running = True
    harvest._last_params = {"journal": "J Thorac Oncol", "mode": "latest",
                            "reldate_days": 30, "inc_ed": False, "inc_lt": False,
                            "topic": None}
    harvest._last_result = _receipt(found=31)
    # 导入入口直接返回（不弹确认框、不 spawn）
    orig_q = QMessageBox.question
    QMessageBox.question = lambda *a, **k: QMessageBox.Yes   # 即使误弹也 Yes，验证被拦
    try:
        harvest._on_import_clicked(_receipt(found=31))
    finally:
        QMessageBox.question = orig_q
    # AI 复筛入口直接返回
    harvest._start_ai_filter()
    app.processEvents()
    assert len(_eng.calls) == 0, f"running 态不应调引擎，实际 {_eng.calls}"
    harvest._running = False


check("INV-09: running 态导入/复筛入口直接返回（计数不增）", running_blocks_reentry)


# ============================ 7. INV-02：写库仅经确认触发 + 受控建 ============================
# 默认全开后空 strategy 下胸外 AI 默认开 → _on_import_clicked 会因 _ai_verdicts is None 弹
# information 锁死（offscreen 模态挂死）。本节用例测的是「纯导入确认流」（与 AI 无关），
# 先显式关胸外 DeepSeek 隔离 AI 门控；section 8b 的 6b-2 用例各自 _enable/_disable 覆盖。
strategy.save_category("胸部肿瘤与胸外科", {"editorial": False, "letter": False,
    "topicFilter": {"enabled": False, "terms": ""},
    "deepseek": {"enabled": False, "criteria": ""}})

def _patch_question(ans):
    orig = QMessageBox.question
    QMessageBox.question = lambda *a, **k: ans
    return orig


def import_no_confirm_no_call():
    # 确认框 No → 不调 run_import
    _eng.reset()
    harvest._running = False
    harvest._last_params = {"journal": "J Thorac Oncol", "mode": "latest",
                            "reldate_days": 30, "inc_ed": False, "inc_lt": False,
                            "topic": None}
    orig = _patch_question(QMessageBox.No)
    try:
        harvest._on_import_clicked(_receipt(found=31, exists=True))
        _drain(harvest, 3)
    finally:
        QMessageBox.question = orig
    assert len([c for c in _eng.calls if c[0] == "import"]) == 0, \
        f"未确认却调了 run_import：{_eng.calls}"


check("INV-02: 确认框 No → 不调 run_import", import_no_confirm_no_call)


def import_yes_calls_once():
    # 确认框 Yes + collection 已存在 → 调 1 次 run_import
    _eng.reset()
    harvest._running = False
    harvest._last_params = {"journal": "J Thorac Oncol", "mode": "latest",
                            "reldate_days": 30, "inc_ed": False, "inc_lt": False,
                            "topic": None}
    orig = _patch_question(QMessageBox.Yes)
    try:
        harvest._on_import_clicked(_receipt(found=31, exists=True))
        ok = _drain(harvest, 5)
    finally:
        QMessageBox.question = orig
    n = len([c for c in _eng.calls if c[0] == "import"])
    assert ok and n == 1, f"确认 Yes 应调 run_import 恰好 1 次（drain={ok}, n={n}）"
    harvest._running = False


check("INV-02: 确认框 Yes → 调 run_import 1 次", import_yes_calls_once)


def controlled_collection_cancel():
    # collection.exists=false + 受控建框取消 → 不调 zotero.create_collection、不导入
    calls = {"create": 0}

    def _fake_create(*a, **k):
        calls["create"] += 1
        return "NEWKEY"

    orig_create = zotero.create_collection
    orig_find = zotero.find_top_key
    zotero.create_collection = _fake_create
    zotero.find_top_key = lambda name: "PARENTKEY"   # 假装父 collection 找得到
    _eng.reset()
    harvest._running = False
    harvest._last_params = {"journal": "J Thorac Oncol", "mode": "latest",
                            "reldate_days": 30, "inc_ed": False, "inc_lt": False,
                            "topic": None}
    orig = _patch_question(QMessageBox.No)   # 受控建框取消
    try:
        harvest._on_import_clicked(_receipt(found=31, exists=False))
        _drain(harvest, 3)
    finally:
        QMessageBox.question = orig
        zotero.create_collection = orig_create
        zotero.find_top_key = orig_find
    assert calls["create"] == 0, "取消受控建不应 POST create_collection"
    assert len([c for c in _eng.calls if c[0] == "import"]) == 0, "取消后不应导入"


check("INV-02/VS-09: collection 不存在+受控建框取消 → 不 POST、不导入",
      controlled_collection_cancel)


# ============================ 8. VS-06：导入用锁定的 _last_params（防切刊错对象） ============================

def import_uses_locked_params():
    _eng.reset()
    harvest._running = False
    # 检索时锁定的刊 = J Thorac Oncol
    harvest._last_params = {"journal": "J Thorac Oncol", "mode": "latest",
                            "reldate_days": 30, "inc_ed": False, "inc_lt": False,
                            "topic": None}
    # 检索后切到另一本刊（操作面板 current_journal 变了）
    harvest._select_journal("Ann Thorac Surg")
    app.processEvents()
    assert harvest.current_journal() == "Ann Thorac Surg", "前置：应已切刊"
    # 触发导入（确认 Yes + collection 已存在，跳过受控建）
    orig = _patch_question(QMessageBox.Yes)
    try:
        harvest._on_import_clicked(_receipt(found=31, exists=True))
        ok = _drain(harvest, 5)
    finally:
        QMessageBox.question = orig
    imports = [c for c in _eng.calls if c[0] == "import"]
    assert ok and len(imports) == 1, f"应导入 1 次（drain={ok}）"
    # mock 收到的 journal 仍是检索时锁定的 J Thorac Oncol，不是当前选中的 Ann Thorac Surg
    assert imports[0][1] == "J Thorac Oncol", \
        f"导入用了错对象：期望 J Thorac Oncol，实际 {imports[0][1]}"
    harvest._running = False


check("VS-06: 检索后切刊，导入仍用锁定的 _last_params", import_uses_locked_params)


# ============================ 8b. 6b-2 真门控：锁死 / 排除 / 捞回 / AI-disabled ============================
# 每个用例临时启用「胸部肿瘤与胸外科」DeepSeek，用完还原空 strategy，避免污染后续用例。

_PARAMS = {"journal": "J Thorac Oncol", "mode": "latest", "reldate_days": 30,
           "inc_ed": False, "inc_lt": False, "topic": None}


def _enable_deepseek():
    """临时启用胸外分类 DeepSeek（返回还原用空 strategy 文本）。"""
    strategy.save_category("胸部肿瘤与胸外科", {"editorial": False, "letter": False,
        "topicFilter": {"enabled": False, "terms": ""},
        "deepseek": {"enabled": True, "criteria": "主体聚焦肺癌"}})


def _disable_deepseek():
    """显式关胸外分类 DeepSeek（默认全开后，测 AI-disabled 路径须显式关）。"""
    strategy.save_category("胸部肿瘤与胸外科", {"editorial": False, "letter": False,
        "topicFilter": {"enabled": False, "terms": ""},
        "deepseek": {"enabled": False, "criteria": ""}})


def _reset_strategy_empty():
    """还原 strategy.json 到空骨架（清除本组用例的 DeepSeek 启用）。"""
    _ST.write_text('{"version": 1, "categories": {}}', encoding="utf-8")


def _patch_information():
    """QMessageBox.information 是模态弹窗（offscreen 会阻塞）——换桩自动 Ok 并计数。"""
    state = {"n": 0}
    orig = QMessageBox.information
    QMessageBox.information = lambda *a, **k: (state.__setitem__("n", state["n"] + 1), QMessageBox.Ok)[1]
    return orig, state


# verdicts：pmid 10000/10001 判滤、10002/10003/10004 判留（与 _receipt(new=5) 的 pmid 对齐）
_VERDICTS = {
    "10000": {"keep": False, "reason": "不相关"}, "10001": {"keep": False, "reason": "不相关"},
    "10002": {"keep": True, "reason": "相关"}, "10003": {"keep": True, "reason": "相关"},
    "10004": {"keep": True, "reason": "相关"},
}


def ai_gate_blocks_import():
    # AI-enabled 刊 + 未跑 AI 就点导入 → 弹 information + run_import 零调用（锁死）
    _enable_deepseek()
    _eng.reset()
    harvest._running = False
    harvest._select_journal("J Thorac Oncol")
    app.processEvents()
    harvest._last_params = dict(_PARAMS)
    harvest._last_result = _receipt(found=31, new=5)
    harvest._ai_verdicts = None
    harvest._recovered = set()
    harvest._render_receipt("J Thorac Oncol", harvest._last_result, dict(_PARAMS))
    app.processEvents()
    orig_info, st = _patch_information()
    orig_q = _patch_question(QMessageBox.Yes)   # 即使误弹确认框也 Yes，验证被门控拦
    try:
        impbtns = [b for b in harvest._action_btns if "导入" in b.text()]
        assert impbtns, "前置：缺导入按钮"
        impbtns[0].click()
        _drain(harvest, 3)
    finally:
        QMessageBox.information = orig_info
        QMessageBox.question = orig_q
    n_import = len([c for c in _eng.calls if c[0] == "import"])
    assert st["n"] == 1, f"应弹 1 次门控提醒（实际 {st['n']}）"
    assert n_import == 0, f"AI 未跑就导入应锁死（run_import 调用 {n_import} 次）"
    _reset_strategy_empty()
    harvest._ai_verdicts = None


check("6b-2②: AI-enabled 刊未跑 AI → 弹提醒 + run_import 零调用（锁死）",
      ai_gate_blocks_import)


def ai_gating_excludes_filtered():
    # AI-enabled + 跑完 AI（verdicts 含 keep=False）+ 点导入 → exclude_pmids == 判滤且未捞回的 pmid
    _enable_deepseek()
    _eng.reset()
    harvest._running = False
    harvest._select_journal("J Thorac Oncol")
    app.processEvents()
    harvest._last_params = dict(_PARAMS)
    harvest._last_result = _receipt(found=31, new=5)
    harvest._ai_verdicts = dict(_VERDICTS)
    harvest._recovered = set()
    harvest._render_receipt("J Thorac Oncol", harvest._last_result, dict(_PARAMS))
    app.processEvents()
    orig_q = _patch_question(QMessageBox.Yes)
    try:
        impbtns = [b for b in harvest._action_btns if "导入" in b.text()]
        impbtns[0].click()
        ok = _drain(harvest, 5)
    finally:
        QMessageBox.question = orig_q
    imports = [c for c in _eng.calls if c[0] == "import"]
    assert ok and len(imports) == 1, f"应导入 1 次（drain={ok}, n={len(imports)}）"
    exclude = imports[0][2].get("exclude_pmids")
    assert exclude == {"10000", "10001"}, \
        f"exclude_pmids 应为判滤未捞回的 {{10000,10001}}，实际 {exclude}"
    _reset_strategy_empty()
    harvest._ai_verdicts = None
    harvest._recovered = set()
    harvest._running = False


check("6b-2①: 跑完 AI 点导入 → exclude_pmids == 判滤且未捞回的 PMID", ai_gating_excludes_filtered)


def ai_gating_recover_removes_from_exclude():
    # 捞回 pmid 10000 后再导入 → 该 pmid 不在 exclude_pmids（只剩 10001）
    _enable_deepseek()
    _eng.reset()
    harvest._running = False
    harvest._select_journal("J Thorac Oncol")
    app.processEvents()
    harvest._last_params = dict(_PARAMS)
    harvest._last_result = _receipt(found=31, new=5)
    harvest._ai_verdicts = dict(_VERDICTS)
    harvest._recovered = set()
    harvest._render_receipt("J Thorac Oncol", harvest._last_result, dict(_PARAMS))
    app.processEvents()
    harvest._toggle_recover("10000")          # 捞回 10000
    app.processEvents()
    assert "10000" in harvest._recovered
    orig_q = _patch_question(QMessageBox.Yes)
    try:
        impbtns = [b for b in harvest._action_btns if "导入" in b.text()]
        impbtns[0].click()
        ok = _drain(harvest, 5)
    finally:
        QMessageBox.question = orig_q
    imports = [c for c in _eng.calls if c[0] == "import"]
    assert ok and len(imports) == 1
    exclude = imports[0][2].get("exclude_pmids")
    assert exclude == {"10001"}, f"捞回 10000 后 exclude 应只剩 {{10001}}，实际 {exclude}"
    _reset_strategy_empty()
    harvest._ai_verdicts = None
    harvest._recovered = set()
    harvest._running = False


check("6b-2①: 捞回一条后导入 → 该 PMID 移出 exclude_pmids", ai_gating_recover_removes_from_exclude)


def ai_disabled_no_gate_full_import():
    # AI-disabled 刊（显式关胸外 DeepSeek）→ 不弹门控、直接可导、exclude_pmids 为空
    _disable_deepseek()                       # 默认全开后须显式关，才测 AI-disabled 路径
    _eng.reset()
    harvest._running = False
    harvest._select_journal("J Thorac Oncol")
    app.processEvents()
    harvest._last_params = dict(_PARAMS)
    harvest._last_result = _receipt(found=31, new=5)
    harvest._ai_verdicts = None               # 没跑 AI
    harvest._recovered = set()
    harvest._render_receipt("J Thorac Oncol", harvest._last_result, dict(_PARAMS))
    app.processEvents()
    orig_info, st = _patch_information()
    orig_q = _patch_question(QMessageBox.Yes)
    try:
        impbtns = [b for b in harvest._action_btns if "导入" in b.text()]
        impbtns[0].click()
        ok = _drain(harvest, 5)
    finally:
        QMessageBox.information = orig_info
        QMessageBox.question = orig_q
    imports = [c for c in _eng.calls if c[0] == "import"]
    assert ok and len(imports) == 1, f"AI-disabled 应直接导入（n={len(imports)}）"
    assert st["n"] == 0, f"AI-disabled 不应弹门控提醒（实际 {st['n']}）"
    exclude = imports[0][2].get("exclude_pmids")
    assert not exclude, f"AI-disabled exclude 应为空，实际 {exclude}"
    harvest._running = False


check("6b-2②: AI-disabled 刊 → 不弹窗、直接导、exclude 空（全导）",
      ai_disabled_no_gate_full_import)


def import_receipt_excluded_group():
    # 导入回执含 excluded 分组：AI 过滤的篇目显式成组、可见、不落「其他」
    params = dict(_PARAMS)
    ri = {"journal": "J Thorac Oncol", "mode": "latest",
          "counts": {"imported": 3, "failed": 0, "dup": 1, "suspect": 0, "excluded": 2},
          "items": (_item("imported", 3) + _item("dup", 1)
                    + [{"title": "excl-A", "status": "excluded", "pmid": 9001,
                        "doi": "x", "type": "Journal Article", "hasAbstract": True},
                       {"title": "excl-B", "status": "excluded", "pmid": 9002,
                        "doi": "x", "type": "Journal Article", "hasAbstract": True}]),
          "collection": {"exists": True, "key": "KEYXYZ"}}
    harvest._render_import_receipt(params, ri)
    app.processEvents()
    texts = _label_texts(harvest)
    assert any("AI 已过滤" in t and "2 篇" in t for t in texts), \
        f"缺 excluded 分组标题：{[t for t in texts if '过滤' in t]}"
    assert any("excl-A" in t for t in texts) and any("excl-B" in t for t in texts), \
        "excluded 文章标题不可见（静默丢）"
    # 「其他」卡不应出现（excluded 已有显式分组）
    assert not any("未识别状态" in t for t in texts), "excluded 误落进「其他」卡"


check("6b-2 receipt: excluded 分组显式渲染 + 文章可见（不静默丢）",
      import_receipt_excluded_group)


# ============================ 9. VS-07：反复渲染→清空不累积泄漏 ============================

def render_clear_no_leak():
    from PySide6.QtWidgets import QLabel, QPushButton, QFrame

    def _widget_count():
        return sum(1 for w in _walk(harvest.receipt_box)
                   if isinstance(w, (QLabel, QPushButton, QFrame)))

    params = {"journal": "J Thorac Oncol", "mode": "latest", "reldate_days": 30,
              "inc_ed": False, "inc_lt": False, "topic": None}
    r = _receipt(found=31)
    counts = []
    for _ in range(3):
        harvest._render_receipt("J Thorac Oncol", r, params)
        app.processEvents()
        counts.append(_widget_count())
        harvest._clear_receipt()
        app.processEvents()   # deleteLater 在事件循环里真正释放
    # 再渲染一次，控件数应与第一轮一致（无累积残留）
    harvest._render_receipt("J Thorac Oncol", r, params)
    app.processEvents()
    final = _widget_count()
    assert final == counts[0], \
        f"反复渲染后控件数漂移：首轮 {counts[0]}，末轮 {final}（中间 {counts}）"


check("VS-07: 渲染→清空 ×3 无累积残留", render_clear_no_leak)


# ============================ 10. 策略表单：落盘 + _loading 不写回 ============================

def strategy_form_persists():
    form = harvest.category_form
    # 载入分类（程序化，_loading 期间不应写盘）
    _ST.unlink(missing_ok=True)
    form.load("临床医学综合")
    app.processEvents()
    assert "临床医学综合" not in strategy.load().get("categories", {}), \
        "load 期间不应落盘该分类"
    # 用户改一个 checkbox → 落盘该分类
    form.cb_letter.setChecked(True)
    form._flush_save()
    form._save_timer.stop()   # 手动 flush 不停单次 timer；这里显式停，避免污染 _loading 判定
    saved = strategy.load()
    assert saved["categories"]["临床医学综合"]["letter"] is True, "改 checkbox 未落盘"
    # _loading=True 期间再改 → 不写回（timer 不启动、文件不变）
    before = strategy.load()
    form._loading = True
    form.cb_letter.setChecked(False)
    app.processEvents()
    assert not form._save_timer.isActive(), "_loading 期间不应启动存盘 timer"
    form._loading = False
    after = strategy.load()
    assert after == before, "_loading 期间不应写回 strategy.json"


check("策略表单: 改 checkbox 落盘 + _loading 期间不写回", strategy_form_persists)


# ============================ 11. per-journal AI 复筛覆写（chip + 三态 + 判据）============================
# 默认全开（CATEGORY_DEFAULT deepseek enabled=True）：空 strategy → 所有分类 AI 开。

def _reset_ov():
    _OV.unlink(missing_ok=True)
    _OV.write_text("{}", encoding="utf-8")


def _select_and_load(name):
    """选刊 + 强制 _load_journal（_select_journal 对已选刊是 no-op、不重载 UI）。"""
    harvest._select_journal(name)
    harvest._load_journal(name)
    app.processEvents()


def chip_ai_toggle_writes_override():
    # 默认 AI 全开 → chip 显「开」；点 chip → 强制关 → chip 显「关」+ override 写 enabled=False
    _reset_strategy_empty()
    _reset_ov()
    _select_and_load("J Thorac Oncol")
    assert "开" in harvest.chip_ai.text(), f"默认应开，chip={harvest.chip_ai.text()!r}"
    assert harvest.rb_ai_inherit.isChecked(), "默认应选 inherit"
    harvest.chip_ai.click()
    app.processEvents()
    assert "关" in harvest.chip_ai.text(), f"点后应关，chip={harvest.chip_ai.text()!r}"
    ov = overrides.load_all().get("J Thorac Oncol", {})
    assert (ov.get("deepseek") or {}).get("enabled") is False, f"override 未写 force-off：{ov}"
    assert harvest.rb_ai_off.isChecked(), "chip 关后 radio 应联动 force-off"
    assert strategy.resolve("J Thorac Oncol")["deepseek_enabled"] is False
    # 再点 → 强制开
    harvest.chip_ai.click()
    app.processEvents()
    assert "开" in harvest.chip_ai.text()
    ov2 = overrides.load_all().get("J Thorac Oncol", {})
    assert (ov2.get("deepseek") or {}).get("enabled") is True
    assert harvest.rb_ai_on.isChecked()


check("per-journal AI: 点 chip_ai 翻转 + 写 override + radio 联动 + resolve 生效",
      chip_ai_toggle_writes_override)


def ai_radio_three_state_writes():
    _reset_strategy_empty()
    _reset_ov()
    _select_and_load("J Thorac Oncol")
    assert harvest.rb_ai_inherit.isChecked() and "开" in harvest.chip_ai.text()
    # 选「本刊强制关」→ enabled=False + chip 关
    harvest.rb_ai_off.click()
    app.processEvents()
    ov = (overrides.load_all().get("J Thorac Oncol", {}).get("deepseek") or {})
    assert ov.get("enabled") is False, f"radio off 未写：{ov}"
    assert "关" in harvest.chip_ai.text()
    # 选「本刊强制开」→ enabled=True + chip 开
    harvest.rb_ai_on.click()
    app.processEvents()
    ov2 = (overrides.load_all().get("J Thorac Oncol", {}).get("deepseek") or {})
    assert ov2.get("enabled") is True
    assert "开" in harvest.chip_ai.text()
    # 选「跟随分类」→ 全默认 → 条目删除 + chip 开（分类默认开）
    harvest.rb_ai_inherit.click()
    app.processEvents()
    assert "J Thorac Oncol" not in overrides.load_all(), "inherit 应清 override（全默认）"
    assert "开" in harvest.chip_ai.text()


check("per-journal AI: 三态 radio 写 override + chip 联动 + inherit 清条目",
      ai_radio_three_state_writes)


def ai_criteria_writes_override():
    _reset_strategy_empty()
    _reset_ov()
    _select_and_load("J Thorac Oncol")
    assert "分类" in harvest.ai_effective_label.text()   # 留空 = 分类
    # 填判据 → 写 criteria + resolve 取本刊判据 + 生效提示显「本刊」
    harvest.ai_criteria_edit.setText("本刊肺癌判据")
    harvest._on_ai_criteria_changed()
    app.processEvents()
    ov = (overrides.load_all().get("J Thorac Oncol", {}).get("deepseek") or {})
    assert ov.get("criteria") == "本刊肺癌判据", f"criteria 未写：{ov}"
    assert strategy.resolve("J Thorac Oncol")["deepseek_criteria"] == "本刊肺癌判据"
    assert "本刊" in harvest.ai_effective_label.text(), \
        f"生效提示应显本刊：{harvest.ai_effective_label.text()!r}"
    # 清空判据 → criteria 继承分类（若 deepseek enabled 仍 None → 全默认 → 条目删）
    harvest.ai_criteria_edit.setText("")
    harvest._on_ai_criteria_changed()
    app.processEvents()
    assert "J Thorac Oncol" not in overrides.load_all(), "清空判据 + inherit → 全默认删条目"


check("per-journal AI: 判据框写 criteria + 生效提示显来源 + 清空回落", ai_criteria_writes_override)


def ai_switch_journal_reflect():
    # J Thorac Oncol：强制关 + 自定义判据；Ann Thorac Surg：无 override（继承）
    _reset_strategy_empty()
    _reset_ov()
    overrides.save("J Thorac Oncol", {"includeEditorial": False, "includeLetter": False,
                    "topicFilter": None, "deepseek": {"enabled": False, "criteria": "JTO判据"}})
    _select_and_load("J Thorac Oncol")
    assert harvest.rb_ai_off.isChecked() and harvest.ai_criteria_edit.text() == "JTO判据"
    assert "关" in harvest.chip_ai.text()
    # 切到 Ann Thorac Surg → 回显继承 + 空判据 + chip 开（默认全开）
    _select_and_load("Ann Thorac Surg")
    assert harvest.rb_ai_inherit.isChecked(), "ATS 应回显 inherit"
    assert harvest.ai_criteria_edit.text() == "", "ATS 判据框应空（继承）"
    assert "开" in harvest.chip_ai.text()
    # 切回 JTO → 仍 force-off + JTO判据（未被 ATS 污染）
    _select_and_load("J Thorac Oncol")
    assert harvest.rb_ai_off.isChecked() and harvest.ai_criteria_edit.text() == "JTO判据"


check("per-journal AI: 切刊正确回显（不污染他刊 override）", ai_switch_journal_reflect)


def ai_loading_no_spurious_write():
    _reset_strategy_empty()
    _reset_ov()
    _select_and_load("J Thorac Oncol")
    # 程序化载入不应落盘 override
    assert "J Thorac Oncol" not in overrides.load_all(), "载入不应落盘 override"
    # _loading=True 期间持久化 / chip 点击 → 直返不写
    before = overrides.load_all()
    harvest._loading = True
    harvest._persist_exception()
    harvest._on_chip_ai_clicked()
    harvest._loading = False
    assert overrides.load_all() == before, "_loading 期间不应写回"


check("per-journal AI: _loading 期间持久化/点击不误写", ai_loading_no_spurious_write)


# ============================ 收尾 ============================
import shutil  # noqa: E402

# 排空残留后台线程，避免 QThread 销毁报错
_drain(harvest, 3)
for p in win.pages:
    _drain(p, 2)
shutil.rmtree(_TMPDIR, ignore_errors=True)

if os.environ.get("TRACKEEP_CI") == "1":
    print(f"[CI] TRACKEEP_CI 联网检查跳过 {_CI_SKIPS['n']} 次")

print(f"\n{'=' * 40}\n{sum(checks)}/{len(checks)} 项通过")
sys.exit(0 if all(checks) else 1)
