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
            "① 选择期刊与年月、中文主题或 PMID，点击生成计划。其他期刊可直接输入名称核验。\n"
            "② 阅读计划后点核验并检索。按刊默认使用出版日期宽口径；近期与历史均保留电子及卷期日期。\n"
            "③ 读取并选择已有集合，先核重预览，再确认存入 Zotero。导入沿用锁定批次。\n"
            "④ 双击题录阅读摘要，逐篇填写保留、排除或待核与理由；也可填写中文要求运行 AI 复核。\n"
            "⑤ 保存复核后获取全文。仅保留项进入原生查找全文及官方来源补充，按本机实际文件验收。\n\n"
            "结果与重跑\n"
            "· 批次会保存，可在上方恢复后刷新或重试；错误、部分完成和待核不会显示成全部成功。\n"
            "· 缺摘要、模型未配置或判决失败均留待核，不会自动排除。\n"
            "· 同 PMID 跨月按已见或元数据变化处理；身份冲突待核，不凭标题自动合并。\n"
            "· 排除是有效候选名单的决定；保存复核不会永久删除 Zotero 内容。\n"
            "· 原生添加同文件会产生重复；本流程会先检查已有附件，核验通过则跳过。\n"
            "· 中文主题计划与 AI 复核使用现有 DeepSeek 配置；按刊与 PMID 无需模型。"
        )
        body.setObjectName("muted")
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(body)
        lay.addStretch(1)
