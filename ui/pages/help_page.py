# -*- coding: utf-8 -*-
"""使用说明页（Slice 4 更新：覆盖采集最新/回填/导入全流程 + 护栏 + 可逆提示）。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class HelpPage(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 22, 28, 18)
        lay.setSpacing(12)

        title = QLabel("📖  使用说明")
        title.setObjectName("pageTitle")
        lay.addWidget(title)

        body = QLabel(
            "采集台 · 五步\n"
            "① 左侧期刊树选一本刊（74 刊 · 5 分类）\n"
            "② 检索配置：勾文献类型（Article/Review/Editorial/Letter，至少一个）+"
            "「仅要有摘要」+ 可选主题过滤。Editorial/Letter/主题过滤按刊写回例外表。\n"
            "③ 选模式：「采集最新」（PubMed edat，窗口从台账自动算）或「回填历史」"
            "（选年/月回填历史文献）。\n"
            "④ 点「检索」→ dry-run 预览（约 30–60 秒）：命中/新增/去重/疑似 + 逐条标题与判重依据。\n"
            "⑤ 审计页点「导入到 Zotero」→ 确认 → 真实写库（新增 · 去重 · 可逆）。\n\n"
            "护栏\n"
            "· 后台线程检索/导入，不卡界面；运行中按钮禁用（单飞）。\n"
            "· 至少勾一个文献类型才能检索；Article/Review 都没勾时「仅要有摘要」灰掉。\n"
            "· 回填年份不超今年、当年月份非未来；违规禁检索。\n"
            "· 命中达 1000 上限提示改按月回填（避免截断）。\n"
            "· 导入用检索时锁定的参数（切刊/改配置后不会导入错对象）。\n"
            "· 判重顺序：DOI › PMID › 归一标题（命中 Zotero 库 + 台账）。\n\n"
            "可逆性\n"
            "· 真实导入可逆：误导入可在 Zotero 回收站恢复。\n"
            "· 导入幂等：失败可点「重试失败」，引擎台账只记成功、去重跳过已导入，重试只补失败项。\n"
            "· 导入后采集窗口自动前移（台账锚点更新）。"
        )
        body.setObjectName("muted")
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(body)
        lay.addStretch(1)
