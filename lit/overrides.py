# -*- coding: utf-8 -*-
"""检索配置例外表读写：`journal-overrides.json`（App 的配置，可写；引擎也读）。

只存「与默认不同」的字段；与默认相同则删除该刊条目。原子写（temp + rename），
保留其它刊已有条目（现有 `J Thorac Oncol` 条目不会被误删）。

默认（无条目）= Article+Review+有摘要、无 editorial/letter、无 topicFilter；
Article/Review/有摘要 是引擎查询的不可去基底（恒含），不进例外表 —— 所以例外表只可能
落 `includeEditorial` / `includeLetter` / `topicFilter` 三字段。
"""
import json
import os
import tempfile

from lit import config

OVERRIDES_PATH = config.MECHA_CORE / ".mecha" / "journal-overrides.json"

# 默认（无条目时的检索配置基线）—— 例外表只存与这三字段不同的值
DEFAULT = {
    "includeEditorial": False,
    "includeLetter": False,
    "topicFilter": None,
}


def load_all() -> dict:
    """读整个例外表 {刊名: {字段: 值}}。读不到 / 解析失败 → 空 dict（按全默认）。"""
    try:
        text = OVERRIDES_PATH.read_text(encoding="utf-8-sig")   # 兼容 BOM（引擎 / 手编都可能带）
    except OSError:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def get(journal: str) -> dict:
    """读该刊的完整检索配置（默认 + 该刊例外覆盖）。返回三字段 dict。"""
    cfg = dict(DEFAULT)
    entry = load_all().get(journal)
    if isinstance(entry, dict):
        for k in DEFAULT:
            if k in entry:
                cfg[k] = entry[k]
    return cfg


def is_exception(journal: str) -> bool:
    """该刊在例外表里有非空条目（与默认不同）→ 配置区显示「例外」小标用。"""
    entry = load_all().get(journal)
    return isinstance(entry, dict) and len(entry) > 0


def save(journal: str, cfg: dict) -> None:
    """写该刊配置：与默认不同的字段落条目，全默认则删条目。原子写，保留其它刊。

    cfg 含 includeEditorial / includeLetter / topicFilter；topicFilter 空串视同 None。
    """
    all_data = load_all()
    diff = _diff_from_default(cfg)
    if diff:
        all_data[journal] = diff
    else:
        all_data.pop(journal, None)
    _atomic_write(all_data)


def _diff_from_default(cfg: dict) -> dict:
    """挑出与默认不同的字段（topicFilter 空串/None 视同默认 None）。"""
    diff = {}
    for k, default_val in DEFAULT.items():
        val = cfg.get(k, default_val)
        if k == "topicFilter":
            val = val.strip() if isinstance(val, str) else val
            val = val or None
        if val != default_val:
            diff[k] = val
    return diff


def _atomic_write(data: dict) -> None:
    """原子写：临时文件 + os.replace，避免半写损坏其它刊条目。"""
    OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(
        prefix=".journal-overrides-", suffix=".tmp",
        dir=str(OVERRIDES_PATH.parent))
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp_path, OVERRIDES_PATH)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
