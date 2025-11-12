# -*- coding: utf-8 -*-
def _palette_color(pal, role_attr: str, fallback_hex: str) -> str:
    try:
        # Qt6
        from PyQt6.QtGui import QPalette
        role = getattr(QPalette.ColorRole, role_attr)
        return pal.color(role).name()
    except Exception:
        try:
            # Qt5
            from PyQt5.QtGui import QPalette
            role = getattr(QPalette, role_attr, None)
            if role is None:
                return fallback_hex
            return pal.color(role).name()
        except Exception:
            return fallback_hex

def build_app_stylesheet(pal, dark_override: bool = False) -> str:
    if dark_override:
        bg        = "#2b2b2b"
        fg        = "#dddddd"
        base      = "#1e1e1e"
        alt       = "#252525"
        button    = "#333333"
        btn_text  = "#dddddd"
        hilite    = "#3d6af2"
        mid       = "#555555"
        tooltip_bg= "#2f2f30"
        tooltip_fg= "#efefef"
        title_bg  = "#3a3a3a"
    else:
        bg        = _palette_color(pal, "Window",        "#2b2b2b")
        fg        = _palette_color(pal, "WindowText",    "#dddddd")
        base      = _palette_color(pal, "Base",          "#1e1e1e")
        alt       = _palette_color(pal, "AlternateBase", "#252525")
        button    = _palette_color(pal, "Button",        "#333333")
        btn_text  = _palette_color(pal, "ButtonText",    "#dddddd")
        hilite    = _palette_color(pal, "Highlight",     "#3d6af2")
        mid       = _palette_color(pal, "Mid",           "#555555")
        tooltip_bg= "#2f2f30"
        tooltip_fg= "#efefef"
        title_bg  = _palette_color(pal, "AlternateBase", "#3a3a3a")

    return f"""
    QDialog, QWidget {{
        background: {bg};
        color: {fg};
        font-size: 10pt;
    }}
    QLabel, QCheckBox {{
        color: {fg};
    }}
    QToolTip {{
        background: {tooltip_bg};
        color: {tooltip_fg};
        border: 1px solid {mid};
    }}
    QComboBox, QLineEdit, QPlainTextEdit, QTextEdit {{
        background: {base};
        color: {fg};
        selection-background-color: {hilite};
        border: 1px solid {mid};
        padding: 2px 6px;
    }}
    QComboBox QAbstractItemView {{
        background: {alt};
        color: {fg};
        selection-background-color: {hilite};
        border: 1px solid {mid};
    }}
    QListView, QTreeView, QTableView {{
        background: {alt};
        color: {fg};
        selection-background-color: {hilite};
        border: 1px solid {mid};
    }}
    QPushButton {{
        background: {button};
        color: {btn_text};
        border: 1px solid {mid};
        padding: 5px 12px;
        min-height: 26px;
    }}
    QPushButton:hover {{
        border: 1px solid {hilite};
    }}
    QToolButton#infoButton {{
        border: 1px solid {mid};
        border-radius: 10px;
        padding: 0px;
        min-width: 20px;
        max-width: 20px;
        min-height: 20px;
        max-height: 20px;
        background: {base};
    }}
    QToolButton#infoButton:hover {{
        border: 1px solid {hilite};
    }}
    QGroupBox {{
        border: 1px solid {mid};
        border-radius: 6px;
        margin-top: 26px;
        padding-top: 18px;
        padding-left: 10px;
        padding-right: 10px;
        padding-bottom: 10px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 3px 10px;
        margin-left: 8px;
        background: {title_bg};
        border: 1px solid {mid};
        border-radius: 4px;
        color: {fg};
        font-weight: 700;
        font-size: 12pt;
    }}
    QFrame[frameShape="4"] {{
        background: {mid};
        min-height: 1px;
        max-height: 1px;
    }}
    """
