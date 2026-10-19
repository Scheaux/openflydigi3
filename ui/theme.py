"""Application theme (dark Material-inspired stylesheet)."""

ACCENT = "#ff5722"
ACCENT_DARK = "#e64a19"
BG = "#1b1d21"
BG_ALT = "#232629"
SURFACE = "#2a2e33"
SURFACE_HOVER = "#33383e"
BORDER = "#3a3f45"
TEXT = "#e8eaed"
TEXT_DIM = "#9aa0a6"
OK = "#4caf50"
WARN = "#ffb300"
ERR = "#ef5350"

STYLESHEET = f"""
/* Leaf widgets stay transparent so cards/pages show through; only real
   containers (window, cards, sidebars) paint a background. */
QWidget {{
    background-color: transparent;
    color: {TEXT};
    font-family: 'Segoe UI', 'Inter', 'Cantarell', 'Noto Sans', sans-serif;
    font-size: 13px;
}}

QMainWindow, QDialog {{
    background-color: {BG};
}}

/* ---- Sidebar ---- */
#Sidebar {{
    background-color: {BG_ALT};
    border-right: 1px solid {BORDER};
}}
#Logo {{
    color: {ACCENT};
    font-size: 18px;
    font-weight: 700;
    padding: 18px 16px 8px 16px;
}}
#LogoSub {{
    color: {TEXT_DIM};
    font-size: 11px;
    padding: 0 16px 14px 16px;
}}
QListWidget#NavList {{
    background-color: transparent;
    border: none;
    outline: none;
}}
QListWidget#NavList::item {{
    padding: 11px 16px;
    border-radius: 6px;
    margin: 2px 8px;
    color: {TEXT_DIM};
}}
QListWidget#NavList::item:selected {{
    background-color: {ACCENT};
    color: white;
}}
QListWidget#NavList::item:hover:!selected {{
    background-color: {SURFACE_HOVER};
    color: {TEXT};
}}

/* ---- Headers ---- */
#PageTitle {{
    font-size: 22px;
    font-weight: 600;
}}
#PageSubtitle {{
    color: {TEXT_DIM};
    font-size: 12px;
}}
#Card {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
#CardTitle {{
    font-size: 15px;
    font-weight: 600;
}}
#Dim {{
    color: {TEXT_DIM};
}}

/* ---- Buttons ---- */
QPushButton {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 7px 14px;
    color: {TEXT};
}}
QPushButton:hover {{
    background-color: {SURFACE_HOVER};
}}
QPushButton:disabled {{
    color: {TEXT_DIM};
    background-color: {BG_ALT};
}}
QPushButton#Primary {{
    background-color: {ACCENT};
    border: none;
    color: white;
    font-weight: 600;
}}
QPushButton#Primary:hover {{
    background-color: {ACCENT_DARK};
}}
QPushButton#Danger {{
    background-color: transparent;
    border: 1px solid {ERR};
    color: {ERR};
}}

/* ---- Inputs ---- */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit, QListView {{
    background-color: {BG_ALT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 8px;
    selection-background-color: {ACCENT};
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
}}

/* ---- Check / radio boxes ---- */
QCheckBox, QRadioButton {{
    spacing: 8px;
    background: transparent;
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {BORDER};
    border-radius: 3px;
    background-color: {BG_ALT};
}}
QRadioButton::indicator {{ border-radius: 8px; }}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
}}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border-color: {ACCENT};
}}

/* ---- Sliders / progress ---- */
QSlider::groove:horizontal {{
    height: 4px; background: {BORDER}; border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT}; border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {TEXT}; width: 14px; margin: -6px 0; border-radius: 7px;
}}
QProgressBar {{
    background-color: {BG_ALT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    text-align: center;
    height: 20px;
}}
QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 5px;
}}

/* ---- Tables / lists ---- */
QTableWidget, QTreeWidget {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    gridline-color: {BORDER};
    outline: none;
}}
QHeaderView::section {{
    background-color: {BG_ALT};
    padding: 6px;
    border: none;
    border-bottom: 1px solid {BORDER};
    color: {TEXT_DIM};
}}
QTableWidget::item:selected, QTreeWidget::item:selected {{
    background-color: {ACCENT};
    color: white;
}}

/* ---- Scrollbars ---- */
QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER}; border-radius: 5px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {TEXT_DIM}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{
    background: transparent; height: 10px; margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER}; border-radius: 5px; min-width: 24px;
}}

/* ---- Misc ---- */
QToolTip {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 4px;
}}
QStatusBar {{
    background-color: {BG_ALT};
    border-top: 1px solid {BORDER};
    color: {TEXT_DIM};
}}
QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 8px; }}
QTabBar::tab {{
    background: transparent; padding: 8px 14px; color: {TEXT_DIM};
}}
QTabBar::tab:selected {{ color: {ACCENT}; border-bottom: 2px solid {ACCENT}; }}
"""
