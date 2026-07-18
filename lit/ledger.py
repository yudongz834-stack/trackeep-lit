# -*- coding: utf-8 -*-
"""采集窗口从台账算（真自适应）：该刊上次采集时间 → (今天-那天)+30，夹 [7,400]。

台账 `zotero-import-ledger.json` 是引擎写的（Slice 2 只读，不写）。读不到 / 该刊无批次
→ 首次采集，返回 60 天。替代 Slice 1 硬编码的 60。
"""
import json
from datetime import date, datetime

from lit import config

LEDGER_PATH = config.MECHA_CORE / ".trackeep" / "zotero-import-ledger.json"

DEFAULT_DAYS = 60        # 首次采集 / 读不到台账
MIN_DAYS = 7
MAX_DAYS = 400
BUFFER_DAYS = 30         # 上次采集后的安全缓冲（多采一个月，容错漏采）


def _load_batches() -> list:
    try:
        text = LEDGER_PATH.read_text(encoding="utf-8-sig")   # 台账是 PowerShell 写的，带 UTF-8 BOM
    except OSError:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    batches = data.get("batches") if isinstance(data, dict) else None
    return batches if isinstance(batches, list) else []


def last_date(journal: str) -> date | None:
    """该刊最近一次采集的日期（取 batches 里 batch.journal==刊名 的最大 time）。无 → None。"""
    best = None
    for b in _load_batches():
        if not isinstance(b, dict) or b.get("journal") != journal:
            continue
        t = b.get("time")
        if not t:
            continue
        try:
            d = datetime.fromisoformat(str(t)).date()
        except ValueError:
            continue
        if best is None or d > best:
            best = d
    return best


def reldate_for(journal: str) -> tuple[int, date | None]:
    """该刊采集窗口天数 + 上次采集日期。

    有历史 → (今天-那天).days + BUFFER_DAYS，夹 [MIN_DAYS, MAX_DAYS]；
    首次（无批次）→ (DEFAULT_DAYS, None)。返回 (days, last_date)。
    """
    last = last_date(journal)
    if last is None:
        return DEFAULT_DAYS, None
    gap = (date.today() - last).days
    days = max(MIN_DAYS, min(MAX_DAYS, gap + BUFFER_DAYS))
    return days, last
