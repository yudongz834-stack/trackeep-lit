# -*- coding: utf-8 -*-
"""设置页（Slice 4）：只读展示关键路径与连通状态。

展示：版本 / 引擎路径（存在?）/ 例外表 / 台账 / Zotero 凭证（存在?，**不显 key 值**）/
期刊载入数。不做可编辑设置（本版）。路径状态用 ✓/✗ 标，凭证只显存在与否（红线：key 不外传）。
"""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget)

from lit import config, pubmed, journals, zotero

_OK = "#2F9E44"    # 存在：绿
_BAD = "#C92A2A"   # 缺失：红


class SettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 22, 28, 18)
        lay.setSpacing(12)

        title = QLabel("⚙️  设置")
        title.setObjectName("pageTitle")
        lay.addWidget(title)
        lay.addWidget(self._muted(
            "关键路径与连通状态（只读）。凭证仅显示存在与否，绝不显示 key 值。"))

        lay.addWidget(self._card("版本", [
            ("应用", "%s v%s" % (config.APP_NAME, config.VERSION)),
            ("Trackeep Literature 工程", str(config.ROOT)),
        ]))
        lay.addWidget(self._card("关键路径与连通", [
            ("导入引擎 zotero-import.ps1", _path_html(config.ENGINE_PATH)),
            ("共享批次与失败记录", _path_html(config.ROOT / '日志' / 'workflow-runs')),
            ("既有期刊来源表", _path_html(journals.JOURNAL_TABLE)),
            ("Zotero 凭证 zotero.env", _path_html(zotero.ENV_PATH)),
        ]))

        total = len(pubmed.journals())
        lay.addWidget(self._card("期刊载入", [
            ("已核实预置期刊", "%d 本；其他期刊可在采集台输入并核验" % total),
            ("检索口径", "按刊默认出版日期宽口径，电子上线及卷期日期均保留"),
        ]))

        lay.addStretch(1)

    # ---------- 小部件工厂 ----------

    def _card(self, title: str, rows: list[tuple[str, str]]) -> QFrame:
        f = QFrame()
        f.setObjectName("card")
        cl = QVBoxLayout(f)
        cl.setContentsMargins(18, 14, 18, 14)
        cl.setSpacing(8)
        hdr = QLabel(title)
        hdr.setObjectName("sectionTitle")
        cl.addWidget(hdr)
        for name, value in rows:
            r = QHBoxLayout()
            r.setSpacing(12)
            lb = QLabel(name)
            lb.setObjectName("muted")
            lb.setMinimumWidth(260)
            lb.setAlignment(Qt.AlignTop)
            r.addWidget(lb)
            v = QLabel(value)
            v.setWordWrap(True)
            v.setTextInteractionFlags(Qt.TextSelectableByMouse)
            v.setAlignment(Qt.AlignTop)
            r.addWidget(v, 1)
            cl.addLayout(r)
        return f

    @staticmethod
    def _muted(text: str) -> QLabel:
        lb = QLabel(text)
        lb.setObjectName("muted")
        lb.setWordWrap(True)
        return lb


def _path_html(path) -> str:
    """路径 + 存在性标记的富文本（✓ 绿 / ✗ 红 + 路径正文）。"""
    exists = Path(path).exists()
    color = _OK if exists else _BAD
    mark = "✓ 存在" if exists else "✗ 缺失"
    return '<span style="color:%s; font-weight:bold;">%s</span>　%s' % (color, mark, path)
