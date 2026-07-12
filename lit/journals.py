# -*- coding: utf-8 -*-
"""期刊来源表解析（只读）：从 Mecha-Memex 期刊登记表载全 74 刊，按 5 分类分组。

表格式（`期刊来源表.md`）：`| 来源分类 | 期刊全名 | PubMed缩写 | 推荐目录名 | 备注 |`，
`line.split('|')` 后 cells[1]=分类、cells[4]=推荐目录名（=检索用刊名）。跳过列数<5、
表头（cells[1] 含「来源分类」）、分隔行（cells[1] 全是 `-`）。其它表（分类映射 / 收录
统计）因列数<5 自然被跳过。

读不到 / 解析空 → 回退内嵌静态胸外 10（采集台不崩，Slice 1 行为）。
"""
import re

from lit import config

JOURNAL_TABLE = config.MECHA_CORE / "Mecha-Memex" / "00-系统" / "期刊来源表.md"

# 5 个来源分类 —— 顺序即左树分组顺序（对齐期刊来源表收录统计）
CATEGORIES = [
    "胸部肿瘤与胸外科",
    "流行病学与公共卫生",
    "临床医学综合",
    "医学AI与数字医学",
    "基础与转化医学",
]

DEFAULT_JOURNAL = "J Thorac Oncol"

# 解析失败的兜底：Slice 1 静态胸外 10 本（表读不到时保证采集台不崩）
_FALLBACK = {
    "胸部肿瘤与胸外科": [
        "J Thorac Oncol", "Ann Thorac Surg", "Eur J Cardiothorac Surg",
        "J Thorac Cardiovasc Surg", "Lung Cancer", "Chest", "Thorax",
        "Lancet Respir Med", "Eur Respir J", "Clin Lung Cancer",
    ],
}

_SEP_RE = re.compile(r"^-+$")


def load() -> dict[str, list[str]]:
    """读期刊表 → {分类: [刊名,...]}（仅含 5 分类里命中的）。读不到 / 解析空 → 回退静态 10。"""
    try:
        text = JOURNAL_TABLE.read_text(encoding="utf-8-sig")   # 兼容首行 BOM
    except OSError:
        return _fallback()

    result: dict[str, list[str]] = {}
    for ln in text.splitlines():
        cells = ln.split("|")
        if len(cells) < 5:
            continue                       # 非主表行（分类映射 / 收录统计表都 <5 列）
        cat = cells[1].strip()
        name = cells[4].strip()            # 推荐目录名 = 检索用刊名
        if not cat or not name:
            continue
        if "来源分类" in cat:               # 表头
            continue
        if _SEP_RE.match(cat):             # 分隔行 |---|
            continue
        result.setdefault(cat, []).append(name)

    return result if result else _fallback()


def _fallback() -> dict[str, list[str]]:
    return {k: list(v) for k, v in _FALLBACK.items()}


def all_journals(data: dict[str, list[str]] | None = None) -> list[str]:
    """所有刊名扁平化（按 CATEGORIES 顺序）。用于检索 / 校验。"""
    data = data if data is not None else load()
    out: list[str] = []
    for cat in CATEGORIES:
        out.extend(data.get(cat, []))
    return out


def category_of(journal: str, data: dict[str, list[str]] | None = None) -> str | None:
    """反查该刊所属分类（按 CATEGORIES 顺序，命中即返）。无 → None。

    Slice 3 受控建 collection 用：该刊 collection 不存在时，按其分类确定父 collection。
    """
    data = data if data is not None else load()
    for cat in CATEGORIES:
        if journal in data.get(cat, []):
            return cat
    return None
