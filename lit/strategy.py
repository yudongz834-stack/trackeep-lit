# -*- coding: utf-8 -*-
"""采集策略表读写：`.trackeep/strategy.json`（按 5 分类的采集策略总控）。

按分类（与 `journals.CATEGORIES` 逐字一致）分别配 pubtype 基底开关（Editorial/Letter）、
PubMed 主题检索式（topicFilter）、DeepSeek 语义复筛判据（deepseek）。DeepSeek 本片只存
判据字符串、不执行（执行属 6b）。

存盘风格仿 `overrides.py`：utf-8-sig 读（兼容 BOM，见 memory mecha-core-json-utf8-bom）、
原子写（mkstemp + os.replace）、保留 `version` 与其它分类条目（改一个分类不丢其余四个）。

`resolve(journal)` 是 6b 用的合并契约：分类默认 ⊕ 单刊例外（单刊显式字段优先）。
"""
import copy
import json
import os
import tempfile

from lit import config, journals, overrides

STRATEGY_PATH = config.MECHA_CORE / ".trackeep" / "strategy.json"

# 单分类的策略默认（无 strategy.json 或该分类缺失时的基线）
CATEGORY_DEFAULT = {
    "editorial": False,
    "letter": False,
    "topicFilter": {"enabled": False, "terms": ""},
    "deepseek": {"enabled": True, "criteria": ""},   # 默认全开：未配的分类 AI 复筛也默认开
}


def load() -> dict:
    """读整个策略表 {version, categories: {分类: {...}}}。

    读不到 / 解析失败 → 返回空骨架（调用方用 get_category 兜 CATEGORY_DEFAULT）。
    """
    try:
        text = STRATEGY_PATH.read_text(encoding="utf-8-sig")   # 兼容 BOM（引擎 / 手编都可能带）
    except OSError:
        return {"version": 1, "categories": {}}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {"version": 1, "categories": {}}
    if not isinstance(data, dict):
        return {"version": 1, "categories": {}}
    if not isinstance(data.get("categories"), dict):
        data["categories"] = {}
    return data


def get_category(cat: str) -> dict:
    """返回该分类的策略：深拷 CATEGORY_DEFAULT 再覆盖已存字段。

    topicFilter / deepseek 子字典逐字段兜默认，防半缺（如只有 enabled 没 terms）。
    """
    policy = copy.deepcopy(CATEGORY_DEFAULT)
    entry = load()["categories"].get(cat)
    if isinstance(entry, dict):
        for k in ("editorial", "letter"):
            if k in entry:
                policy[k] = bool(entry[k])
        for sub in ("topicFilter", "deepseek"):
            sub_entry = entry.get(sub)
            if isinstance(sub_entry, dict):
                for fk in policy[sub]:
                    if fk in sub_entry:
                        policy[sub][fk] = sub_entry[fk]
    return policy


def save_category(cat: str, policy: dict) -> None:
    """原子写该分类策略：读现有 → 覆盖该分类 → 保留 version 与其它分类 → 写回。

    policy 结构同 CATEGORY_DEFAULT（editorial/letter/topicFilter{enabled,terms}/
    deepseek{enabled,criteria}）；缺字段按默认兜，写出的总是一个完整分类条目。
    """
    data = load()
    data.setdefault("version", 1)
    tf = policy.get("topicFilter") or {}
    ds = policy.get("deepseek") or {}
    data["categories"][cat] = {
        "editorial": bool(policy.get("editorial", False)),
        "letter": bool(policy.get("letter", False)),
        "topicFilter": {
            "enabled": bool(tf.get("enabled", False)),
            "terms": tf.get("terms", "") or "",
        },
        "deepseek": {
            "enabled": bool(ds.get("enabled", False)),
            "criteria": ds.get("criteria", "") or "",
        },
    }
    _atomic_write(data)


def resolve(journal: str) -> dict:
    """6b 用的合并契约：分类默认 ⊕ 单刊例外（单刊显式字段优先）。

    返回 {editorial, letter, topic, deepseek_enabled, deepseek_criteria}：
      - editorial/letter：单刊 journal-overrides 显式字段优先，否则分类默认
      - topic：单刊显式 topicFilter（非空）优先；否则分类的（仅当 enabled 且 terms 非空）
      - deepseek_enabled：单刊 `deepseek.enabled` 显式 bool 时用它，否则分类默认
      - deepseek_criteria：单刊 `deepseek.criteria`（非空 str）优先，否则分类判据

    对畸形单刊 deepseek override 健壮（非 dict / enabled 非 bool / criteria 非 str
    一律安全回落分类，不抛）。
    """
    cat = journals.category_of(journal)
    base = get_category(cat) if cat else copy.deepcopy(CATEGORY_DEFAULT)
    raw = overrides.load_all().get(journal) or {}        # 只含该刊"显式"字段
    editorial = raw["includeEditorial"] if "includeEditorial" in raw else base["editorial"]
    letter = raw["includeLetter"] if "includeLetter" in raw else base["letter"]
    # topic：单刊显式 topicFilter（非空）优先，否则用分类的（仅当 enabled）
    if raw.get("topicFilter"):
        topic = raw["topicFilter"]
    elif base["topicFilter"]["enabled"] and base["topicFilter"]["terms"].strip():
        topic = base["topicFilter"]["terms"].strip()
    else:
        topic = None
    # deepseek：单刊 override 优先（enabled 显式 bool / criteria 非空 str），否则分类；
    # 非 dict / 非 bool / 非 str 一律 isinstance 守卫回落分类（不抛）
    ds_enabled = bool(base["deepseek"]["enabled"])
    ds_criteria = base["deepseek"]["criteria"] or ""
    ds_override = raw.get("deepseek")
    if isinstance(ds_override, dict):
        ov_enabled = ds_override.get("enabled")
        if isinstance(ov_enabled, bool):
            ds_enabled = ov_enabled
        ov_criteria = ds_override.get("criteria")
        if isinstance(ov_criteria, str) and ov_criteria.strip():
            ds_criteria = ov_criteria.strip()
    return {"editorial": bool(editorial), "letter": bool(letter), "topic": topic,
            "deepseek_enabled": ds_enabled,
            "deepseek_criteria": ds_criteria}


def _atomic_write(data: dict) -> None:
    """原子写：临时文件 + os.replace，避免半写损坏其它分类 / version。"""
    STRATEGY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(
        prefix=".strategy-", suffix=".tmp",
        dir=str(STRATEGY_PATH.parent))
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:   # utf-8 不加 BOM（见 memory）
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp_path, STRATEGY_PATH)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
