"""Claude / OpenAI 风格的全局主题。

设计语言：暖白底色、大留白、圆角卡片、低饱和陶土色点缀。
"""

# 调色板
BG = "#FAF9F5"           # 窗口背景（暖米白）
SURFACE = "#FFFFFF"      # 卡片表面
BORDER = "#E5E2D9"       # 细边框
TEXT = "#1F1E1D"         # 主文本
MUTED = "#87837B"        # 次要文本
ACCENT = "#D97757"       # 主题色（陶土橘）
ACCENT_HOVER = "#C8663F"
ACCENT_PRESSED = "#B5532F"
ACCENT_SOFT = "#FBF0EB"  # 主题色浅底
DANGER = "#C2483B"
SUCCESS = "#5E7F5A"
LOG_BG = "#FFFFFF"
LOG_TEXT = "#3D3A34"

FONT_FAMILY = '"Segoe UI", "Microsoft YaHei UI", "PingFang SC", sans-serif'
MONO_FAMILY = '"Cascadia Mono", "Consolas", "Courier New", monospace'

STYLESHEET = f"""
* {{
    font-family: {FONT_FAMILY};
    font-size: 13px;
    color: {TEXT};
}}

QMainWindow, QWidget#root {{
    background: {BG};
}}

/* ---------- 自定义标题栏 ---------- */
QWidget#titleBar {{
    background: {BG};
    border-bottom: 1px solid {BORDER};
}}

QLabel#titleDot {{
    background: {ACCENT};
    border-radius: 5px;
    margin-right: 6px;
}}

QLabel#titleBarText {{
    font-size: 12px;
    font-weight: 600;
    color: {MUTED};
}}

QPushButton#windowBtn, QPushButton#windowCloseBtn {{
    background: transparent;
    border: none;
    border-radius: 6px;
    color: {MUTED};
    font-size: 12px;
    padding: 0;
}}

QPushButton#windowBtn:hover {{
    background: #EFEDE5;
    color: {TEXT};
}}

QPushButton#windowCloseBtn:hover {{
    background: {DANGER};
    color: #FFFFFF;
}}

/* ---------- 标题区 ---------- */
QLabel#appTitle {{
    font-size: 22px;
    font-weight: 600;
    letter-spacing: 0.5px;
}}

QLabel#appSubtitle {{
    font-size: 13px;
    color: {MUTED};
}}

/* ---------- 卡片 ---------- */
QFrame#card {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}

QLabel#cardTitle {{
    font-size: 14px;
    font-weight: 600;
}}

QLabel#cardHint {{
    font-size: 12px;
    color: {MUTED};
}}

QLabel#fieldLabel {{
    font-size: 12px;
    color: {MUTED};
}}

/* ---------- 状态徽标 ---------- */
QLabel#statusPill {{
    border-radius: 10px;
    padding: 3px 12px;
    font-size: 12px;
    font-weight: 600;
    background: {BG};
    color: {MUTED};
    border: 1px solid {BORDER};
}}

QLabel#statusPill[state="busy"] {{
    background: {ACCENT_SOFT};
    color: {ACCENT_PRESSED};
    border: 1px solid {ACCENT};
}}

QLabel#statusPill[state="ready"] {{
    background: #EEF3EC;
    color: {SUCCESS};
    border: 1px solid #C9D8C5;
}}

/* ---------- 按钮 ---------- */
QPushButton {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 500;
}}

QPushButton:hover {{
    background: {BG};
    border-color: #D6D2C6;
}}

QPushButton:pressed {{
    background: #F0EEE6;
}}

QPushButton:disabled {{
    color: #B8B4AB;
    background: #F4F2EC;
    border-color: {BORDER};
}}

QPushButton#primary {{
    background: {ACCENT};
    border: none;
    color: #FFFFFF;
    font-weight: 600;
}}

QPushButton#primary:hover {{
    background: {ACCENT_HOVER};
}}

QPushButton#primary:pressed {{
    background: {ACCENT_PRESSED};
}}

QPushButton#primary:disabled {{
    background: #EAC9BC;
    color: #FFFFFF;
}}

QPushButton#danger {{
    background: {SURFACE};
    border: 1px solid #E3C4BF;
    color: {DANGER};
}}

QPushButton#danger:hover {{
    background: #FAF0EF;
}}

QPushButton#danger:disabled {{
    color: #D8B5B0;
    background: #F8F5F2;
}}

QPushButton#ghost {{
    background: transparent;
    border: none;
    color: {MUTED};
    padding: 4px 10px;
}}

QPushButton#ghost:hover {{
    color: {TEXT};
}}

/* ---------- 输入控件 ---------- */
QLineEdit, QSpinBox {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 7px 10px;
    selection-background-color: {ACCENT_SOFT};
    selection-color: {TEXT};
}}

QLineEdit:focus, QSpinBox:focus {{
    border: 1px solid {ACCENT};
}}

QLineEdit:disabled, QSpinBox:disabled {{
    background: #F4F2EC;
    color: #B8B4AB;
}}

QLineEdit::placeholder {{
    color: #B8B4AB;
}}

QSpinBox::up-button, QSpinBox::down-button {{
    border: none;
    background: transparent;
    width: 18px;
}}

QSpinBox::up-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid {MUTED};
    width: 0;
    height: 0;
}}

QSpinBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {MUTED};
    width: 0;
    height: 0;
}}

/* ---------- 列表 ---------- */
QListWidget {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 4px;
    outline: none;
}}

QListWidget::item {{
    border-radius: 6px;
    padding: 7px 10px;
    margin: 1px 0;
}}

QListWidget::item:hover {{
    background: {BG};
}}

QListWidget::item:selected {{
    background: {ACCENT_SOFT};
    color: {ACCENT_PRESSED};
}}

/* ---------- 日志 ---------- */
QTextEdit#logView {{
    background: {LOG_BG};
    border: none;
    border-radius: 8px;
    padding: 6px;
    font-family: {MONO_FAMILY};
    font-size: 12px;
    color: {LOG_TEXT};
}}

/* ---------- 滚动条 ---------- */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background: #D6D2C6;
    border-radius: 4px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background: #C2BDAE;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}

QScrollBar::handle:horizontal {{
    background: #D6D2C6;
    border-radius: 4px;
    min-width: 30px;
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ---------- 消息框 ---------- */
QMessageBox {{
    background: {SURFACE};
}}
"""
