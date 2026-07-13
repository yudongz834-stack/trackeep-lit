# -*- coding: utf-8 -*-
"""全局视觉样式：颜色常量 + QSS 主题。

v1.9（S9）换装 Anthropic 风格：暖象牙底（#F0EEE6）+ 米白卡片 + 珊瑚主色（#D97757），
大圆角、细边框、克制的强调色。**红涨绿跌是 A 股语义色，与主色分工不同，永不改**；
危险红/警示橙两个内联常量同理保留原值（各页引用的是常量名，改值即全局生效）。
"""

UP = "#E03131"        # 涨 / 盈利（A 股习惯红色——语义色，不随主题走）
DOWN = "#2F9E44"      # 跌 / 亏损
ACCENT = "#D97757"        # 主色：珊瑚陶土（Anthropic 品牌感）
ACCENT_DARK = "#BC5F3F"   # 主色按下/悬停
ACCENT_SOFT = "#F5E8E1"   # 主色浅底（选中态/悬停底）
TEXT = "#1F1E1D"      # 正文（暖近黑）
MUTED = "#7A7568"     # 次要文字（暖灰）
BORDER = "#DFDACB"    # 边框（暖米灰）
BG = "#F0EEE6"        # 窗口底色（暖象牙）
CARD_BG = "#FAF9F5"   # 卡片底色（米白）

# 内联样式常量（多页复用，避免同一串硬编码各处抄）
DANGER_TEXT = "color:#C92A2A; font-weight:bold;"   # 危险/拦截红字（风控警告、超限提示）
WARN_TEXT = "color:#E8590C; font-weight:bold;"     # 警示橙字（数据过时、信号翻转）

QSS = f"""
* {{
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
    font-size: 10.5pt;
    color: {TEXT};
}}
QMainWindow, QDialog {{ background: {BG}; }}

/* ---- 左侧导航 ---- */
QListWidget#nav {{
    background: #F7F5EE;
    border: none;
    border-right: 1px solid {BORDER};
    outline: none;
    padding-top: 6px;
}}
QListWidget#nav::item {{
    height: 44px;
    padding-left: 14px;
    border-left: 3px solid transparent;
    color: #55514A;
}}
QListWidget#nav::item:hover {{ background: {ACCENT_SOFT}; }}
QListWidget#nav::item:selected {{
    background: {ACCENT_SOFT};
    border-left: 3px solid {ACCENT};
    color: {ACCENT_DARK};
    font-weight: bold;
}}

/* ---- 采集台左树：选中态贴主题（珊瑚）不用默认蓝 ---- */
QTreeWidget {{
    background: {CARD_BG};
    border: none;
    outline: none;
}}
QTreeWidget::item {{ padding: 4px 2px; }}
QTreeWidget::item:hover {{ background: #F0EDE3; }}
QTreeWidget::item:selected {{
    background: {ACCENT_SOFT};
    color: {ACCENT_DARK};
}}

/* ---- 卡片 ---- */
QFrame#card {{
    background: {CARD_BG};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QLabel#cardTitle {{ color: {MUTED}; font-size: 9.5pt; }}
QLabel#cardValue {{ font-size: 16pt; font-weight: bold; }}
QLabel#pageTitle {{ font-size: 16pt; font-weight: bold; }}
QLabel#muted {{ color: {MUTED}; font-size: 9.5pt; }}
QLabel#sectionTitle {{ font-size: 12pt; font-weight: bold; padding-top: 4px; }}

/* ---- 按钮 ---- */
QPushButton {{
    background: #FFFFFF;
    border: 1px solid #D6D0C2;
    border-radius: 8px;
    padding: 7px 16px;
}}
QPushButton:hover {{ border-color: {ACCENT}; color: {ACCENT_DARK}; }}
QPushButton:disabled {{ color: #B3AEA2; border-color: {BORDER}; }}
QPushButton#primary {{
    background: {ACCENT};
    color: white;
    border: none;
    font-weight: bold;
}}
QPushButton#primary:hover {{ background: {ACCENT_DARK}; }}
QPushButton#primary:disabled {{ background: #EDCDBE; }}

/* ---- 标签页（设置/参数实验室等） ---- */
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{
    background: transparent;
    padding: 8px 18px;
    color: {MUTED};
    border: none;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:hover {{ color: {TEXT}; }}
QTabBar::tab:selected {{
    color: {ACCENT_DARK};
    font-weight: bold;
    border-bottom: 2px solid {ACCENT};
}}

/* ---- 表格 ---- */
QTableWidget {{
    background: {CARD_BG};
    border: 1px solid {BORDER};
    border-radius: 8px;
    gridline-color: #EEEBE0;
    alternate-background-color: #F4F2EA;
}}
QHeaderView::section {{
    background: #F1EEE4;
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 7px;
    font-weight: bold;
}}
QTableWidget::item {{ padding: 5px; }}
QTableWidget::item:selected {{ background: {ACCENT_SOFT}; color: {TEXT}; }}

/* ---- 输入控件 ---- */
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {{
    background: #FFFFFF;
    border: 1px solid #D6D0C2;
    border-radius: 8px;
    padding: 5px 9px;
    min-height: 20px;
}}
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus {{
    border-color: {ACCENT};
}}
QComboBox QAbstractItemView {{
    background: {CARD_BG};
    selection-background-color: {ACCENT_SOFT};
    selection-color: {ACCENT_DARK};
}}

/* ---- 进度条 ---- */
QProgressBar {{
    background: {BORDER};
    border: none;
    border-radius: 7px;
    height: 14px;
    text-align: center;
    font-size: 8.5pt;
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 7px; }}

/* ---- 滚动条（细圆角，贴主题） ---- */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{
    background: #CFC9BA; border-radius: 5px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: #B5AE9C; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
QScrollBar::handle:horizontal {{
    background: #CFC9BA; border-radius: 5px; min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{ background: #B5AE9C; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ---- 其他 ---- */
QScrollArea {{ border: none; background: transparent; }}
QStatusBar {{ background: #F7F5EE; border-top: 1px solid {BORDER}; color: {MUTED}; }}
QTextBrowser {{ background: {CARD_BG}; border: 1px solid {BORDER}; border-radius: 12px; padding: 18px; }}
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 10px;
    margin-top: 10px;
    padding-top: 6px;
    background: {CARD_BG};
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {MUTED}; }}
"""
