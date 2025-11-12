# -*- coding: utf-8 -*-

import os
import sys
import json
import traceback
from pathlib import Path
from typing import Dict, Optional, Set, List, Tuple

# -------- Qt compat PyQt5/PyQt6 (+ HiDPI) --------
try:
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QComboBox,
        QCheckBox, QMessageBox, QApplication, QWidget, QGroupBox, QFrame, QPlainTextEdit,
        QFileDialog, QStyleFactory, QTabWidget, QToolButton, QStyle, QSizePolicy
    )
    from PyQt6.QtCore import Qt, QSize, QEasingCurve, QPropertyAnimation
    from PyQt6.QtGui import QPixmap, QPalette, QFont, QIcon
    _QT6 = True
except ImportError:
    from PyQt5.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QComboBox,
        QCheckBox, QMessageBox, QApplication, QWidget, QGroupBox, QFrame, QPlainTextEdit,
        QFileDialog, QStyleFactory, QTabWidget, QToolButton, QStyle, QSizePolicy
    )
    from PyQt5.QtCore import Qt, QSize, QEasingCurve, QPropertyAnimation
    from PyQt5.QtGui import QPixmap, QPalette, QFont, QIcon
    _QT6 = False

# HiDPI
try:
    if _QT6:
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    else:
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
except Exception:
    pass

import mobase  # fourni par MO2

# -------- Imports modulaires --------
from .Base.logging_sd import _LOG
from .Base.mo2_helpers import (
    mo2_root, mo2_mods_dir, mo2_profiles_dir, overwrite_dir,
    selected_profile_from_ini, read_mo2_style, apply_qt_style_from_name,
    modlist_path, read_modlist, write_modlist, set_mod_enabled_in_lines,
    apply_mod_sets, enabled_mod_names
)
from .Base.rules import (
    RULES_FILENAME, INMEMORY_DEFAULTS, CATEGORY_ALIASES,
    rules_path, load_rules_fresh
)
from .Base.dxdiag import _safe_float, dxdiag_max_wddm, is_dlss_capable, DxdiagWorkerFactory
from .Base.resolution import (
    RESOLUTIONS_BY_RATIO, bucket_from_resolution,
    detect_primary_resolution, normalize_ratio, nearest_in_list
)
from .Base.sdt_ini import compose_sdt_text_for, apply_resolution_to_sdt
from .Base.plugins import sync_new_plugins_incremental
from .Base.plugingroups import sync_plugingroups
from .Base.preview import resolve_preview_path, ScaledPreviewLabelFactory
from .Base.theme import build_app_stylesheet

# --------------------------- UI ---------------------------

class StartupDialog(QDialog):
    PRESETS_DIR = Path(__file__).resolve().parent / "presets"

    def __init__(self, organizer: mobase.IOrganizer, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Startup Dashboard")
        self.setModal(True)
        self.organizer = organizer

        # Plugin settings
        self.hide_incompatible = bool(self._get_setting("HideIncompatibleOptions", False))
        self.auto_check_dlss   = bool(self._get_setting("AutoCheckDLSS", True))
        self.min_wddm          = _safe_float(self._get_setting("DLSSMinimumWDDM", "2.9"), 2.9)
        self.follow_theme      = bool(self._get_setting("FollowMO2Theme", True))
        self.force_dark        = bool(self._get_setting("ForceDarkTheme", False))

        # UI constants
        self._LABEL_W = 200

        # MO2 style
        mo2_style, mo2_is_dark = read_mo2_style()
        apply_qt_style_from_name(mo2_style)
        if self.follow_theme and not self.force_dark:
            self.force_dark = bool(mo2_is_dark)

        # Rules
        self.rules = load_rules_fresh()
        try:
            from PyQt6.QtCore import QFileSystemWatcher
        except Exception:
            from PyQt5.QtCore import QFileSystemWatcher
        try:
            self._watch = QFileSystemWatcher([str(rules_path())], self)
            self._watch.fileChanged.connect(self._on_rules_changed)
        except Exception:
            self._watch = None

        # Category visibility
        self.ui_visible: Dict[str, bool] = dict(self.rules.get("ui_visibility", {}))

        # Margins/spacings
        self.setContentsMargins(12, 12, 12, 12)

        # Root layout
        root = QVBoxLayout(self)
        root.setSpacing(10)

        # Toolbar
        toolbar = QHBoxLayout()
        self.btn_toggle_advanced = QPushButton("Advanced mode: ON", self)
        self.btn_toggle_advanced.setCheckable(True)
        self.btn_toggle_advanced.setChecked(True)

        self.btn_preset_save = QPushButton("Save preset…", self)
        self.btn_preset_load = QPushButton("Load preset…", self)
        self.btn_preview_ini = QPushButton("SDT .ini preview", self)

        toolbar.addWidget(self.btn_toggle_advanced)
        toolbar.addStretch(1)
        toolbar.addWidget(self.btn_preview_ini)
        toolbar.addWidget(self.btn_preset_save)
        toolbar.addWidget(self.btn_preset_load)
        root.addLayout(toolbar)

        main = QHBoxLayout()
        main.setSpacing(12)
        root.addLayout(main, 1)

        # -------- Left column --------
        left_col = QVBoxLayout()
        left_col.setSpacing(10)
        main.addLayout(left_col, 3)

        def _mk_label(text: str) -> QLabel:
            lab = QLabel(text, self)
            try:
                lab.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            except Exception:
                lab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            lab.setMinimumWidth(self._LABEL_W)
            return lab

        def _expand_h(widget: QWidget) -> QWidget:
            sp = widget.sizePolicy()
            try:
                sp.setHorizontalPolicy(QSizePolicy.Policy.Expanding)
            except Exception:
                sp.setHorizontalPolicy(QSizePolicy.Expanding)
            widget.setSizePolicy(sp)
            return widget

        def _wrap_with_info(widget: QWidget, info_btn: QToolButton) -> QWidget:
            w = QWidget(self)
            lay = QHBoxLayout(w)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(6)
            lay.addWidget(_expand_h(widget))
            lay.addWidget(info_btn, 0)
            return w

        # Groups
        sys_group = QGroupBox("Display & System", self)
        sys_layout = QGridLayout(sys_group)
        sys_layout.setHorizontalSpacing(10)
        sys_layout.setVerticalSpacing(8)
        sys_layout.setContentsMargins(10, 18, 10, 10)
        sys_layout.setColumnMinimumWidth(0, self._LABEL_W)
        sys_layout.setColumnStretch(1, 1)

        self.reso_combo = QComboBox(self); _expand_h(self.reso_combo)
        self._populate_resolution_combo()
        self._row_reso = (_mk_label("Resolution:"), self.reso_combo)
        sys_layout.addWidget(self._row_reso[0], 0, 0)
        sys_layout.addWidget(self._row_reso[1], 0, 1)

        self.framework_combo = QComboBox(self); _expand_h(self.framework_combo)
        for fw in self._order_with_default_first(list(self.rules.get("graphics_framework", {}).keys()) or ["ENB", "Community Shaders"]):
            self.framework_combo.addItem(fw)
        self._row_framework = (_mk_label("Graphics Framework:"), self.framework_combo)
        sys_layout.addWidget(self._row_framework[0], 1, 0)
        sys_layout.addWidget(self._row_framework[1], 1, 1)

        left_col.addWidget(sys_group)

        gp_group = QGroupBox("Gameplay & UI", self)
        gp_layout = QGridLayout(gp_group)
        gp_layout.setHorizontalSpacing(10)
        gp_layout.setVerticalSpacing(8)
        gp_layout.setContentsMargins(10, 18, 10, 10)
        gp_layout.setColumnMinimumWidth(0, self._LABEL_W)
        gp_layout.setColumnStretch(1, 1)

        self.diff_combo = QComboBox(self); _expand_h(self.diff_combo)
        for d in self._order_with_default_first(list(self.rules.get("difficulty", {}).keys()) or ["Novice", "Adept", "Expert", "Legendary"]):
            self.diff_combo.addItem(d)
        self._row_diff = (_mk_label("Difficulty:"), self.diff_combo)
        gp_layout.addWidget(self._row_diff[0], 0, 0)
        gp_layout.addWidget(self._row_diff[1], 0, 1)

        self.menu_combo = QComboBox(self); _expand_h(self.menu_combo)
        mm_labels = list(self.rules.get("main_menu", {}).keys()) or self._guess_main_menu_labels() or ["Vanilla", "Dark", "Fantasy"]
        for mm in self._order_with_default_first(mm_labels):
            self.menu_combo.addItem(mm)
        self._row_menu = (_mk_label("Main Menu:"), self.menu_combo)
        gp_layout.addWidget(self._row_menu[0], 1, 0)
        gp_layout.addWidget(self._row_menu[1], 1, 1)

        self.ui_combo = QComboBox(self); _expand_h(self.ui_combo)
        for u in self._order_with_default_first(list(self.rules.get("ui_mod", {}).keys()) or ["Edge UI Explorer", "Oathvein UI"]):
            self.ui_combo.addItem(u)
        self._row_ui = (_mk_label("UI Mod:"), self.ui_combo)
        gp_layout.addWidget(self._row_ui[0], 2, 0)
        gp_layout.addWidget(self._row_ui[1], 2, 1)

        left_col.addWidget(gp_group)

        adv_group = QGroupBox("Advanced Graphics Options", self)
        adv_layout = QGridLayout(adv_group)
        adv_layout.setHorizontalSpacing(10)
        adv_layout.setVerticalSpacing(8)
        adv_layout.setContentsMargins(10, 18, 10, 10)
        adv_layout.setColumnMinimumWidth(0, self._LABEL_W)
        adv_layout.setColumnStretch(1, 1)

        self.enb_combo = QComboBox(self); _expand_h(self.enb_combo)
        for e in self._order_with_default_first(list(self.rules.get("enb_preset", {}).keys()) or ["Rudy ENB", "PI-CHO ENB", "Silent Horizons"]):
            self.enb_combo.addItem(e)
        self._row_enb = (_mk_label("ENB Preset:"), self.enb_combo)
        adv_layout.addWidget(self._row_enb[0], 0, 0)
        adv_layout.addWidget(self._row_enb[1], 0, 1)

        self.aa_combo = QComboBox(self); _expand_h(self.aa_combo)
        for a in self._order_with_default_first(list(self.rules.get("anti_aliasing", {}).keys()) or ["FSR", "DLAA"]):
            self.aa_combo.addItem(a)

        dlss_info_btn = self._make_info_button(
            "DLSS / Frame Generation",
            ("DLSS: NVIDIA upscaler (RTX).\n"
             "Frame Generation: interpolation d'images.\n"
             "Désactivé si 'Community Shaders' est sélectionné.")
        )
        aa_info_btn = self._make_info_button(
            "Anti-aliasing",
            ("DLAA: qualité supérieure, coût GPU plus élevé, NVIDIA.\n"
             "FSR AA: plus universel, coût moindre.")
        )

        aa_wrap = _wrap_with_info(self.aa_combo, aa_info_btn)
        self._row_aa = (_mk_label("Anti-aliasing:"), aa_wrap)
        adv_layout.addWidget(self._row_aa[0], 1, 0)
        adv_layout.addWidget(self._row_aa[1], 1, 1)

        self.ini_base_combo = QComboBox(self); _expand_h(self.ini_base_combo)
        for s in self._order_with_default_first(list(self.rules.get("ini_base", {}).keys()) or ["Low", "Medium", "High"]):
            self.ini_base_combo.addItem(s)
        self._row_ini = (_mk_label("Base INI Preset:"), self.ini_base_combo)
        adv_layout.addWidget(self._row_ini[0], 2, 0)
        adv_layout.addWidget(self._row_ini[1], 2, 1)

        left_col.addWidget(adv_group)

        quick_group = QGroupBox("Quick Options", self)
        quick_layout = QGridLayout(quick_group)
        quick_layout.setHorizontalSpacing(10)
        quick_layout.setVerticalSpacing(6)
        quick_layout.setContentsMargins(10, 18, 10, 10)
        quick_layout.setColumnMinimumWidth(0, self._LABEL_W)
        quick_layout.setColumnStretch(1, 1)

        self.dlss_check   = QCheckBox("Enable DLSS / Frame Generation", self)
        self.nsfw_check   = QCheckBox("NSFW Content", self)
        self.gamepad_check= QCheckBox("Gamepad (UI & tweaks)", self)
        self.poise_check  = QCheckBox("Enable Poise System", self)
        self.npcres_check = QCheckBox("Enable NPC Resistances", self)

        self.dlss_check.setChecked(False)
        self.nsfw_check.setChecked(False)
        self.gamepad_check.setChecked(False)
        self.poise_check.setChecked(True)
        self.npcres_check.setChecked(True)

        self._dlss_wrapper = _wrap_with_info(self.dlss_check, dlss_info_btn)
        quick_layout.addWidget(self._dlss_wrapper, 0, 0, 1, 2)

        quick_layout.addWidget(self.nsfw_check,    0, 2)
        quick_layout.addWidget(self.gamepad_check, 1, 0)
        quick_layout.addWidget(self.poise_check,   1, 1)
        quick_layout.addWidget(self.npcres_check,  2, 0)

        left_col.addWidget(quick_group)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.btn_reset  = QPushButton("Reset (show again next launch)", self)
        self.btn_cancel = QPushButton("Cancel", self)
        self.btn_apply  = QPushButton("Apply", self)
        for b in (self.btn_reset, self.btn_cancel, self.btn_apply):
            b.setMinimumWidth(140)
        btn_row.addWidget(self.btn_reset)
        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_apply)
        left_col.addLayout(btn_row)

        # -------- Right column --------
        right_col = QVBoxLayout()
        right_col.setSpacing(8)
        main.addLayout(right_col, 2)

        self.preview_enable_check = QCheckBox("Show preview", self)
        self.preview_enable_check.setChecked(True)
        right_col.addWidget(self.preview_enable_check)

        self.preview_label = ScaledPreviewLabelFactory(self)
        right_col.addWidget(self.preview_label, 1)

        # Status bar
        self.status = QLabel("", self)
        root.addWidget(self.status)

        # Preview mapping
        self.preview_map: Dict[str, Dict[str, str]] = self.rules.get("previews", {}) or {}
        self._active_preview_category: Optional[str] = None

        # Signals
        try:
            self.framework_combo.currentTextChanged.connect(self._update_framework_compat_ui)
        except Exception:
            self.framework_combo.currentIndexChanged.connect(lambda _i: self._update_framework_compat_ui)

        self._connect_preview_signal("graphics_framework", self.framework_combo)
        self._connect_preview_signal("enb_preset",         self.enb_combo)
        self._connect_preview_signal("ui_mod",             self.ui_combo)
        self._connect_preview_signal("main_menu",          self.menu_combo)
        self._connect_preview_signal("resolution",         self.reso_combo)

        self._connect_preview_checkbox("dlss",            self.dlss_check)
        self._connect_preview_checkbox("nsfw",            self.nsfw_check)
        self._connect_preview_checkbox("gamepad",         self.gamepad_check)
        self._connect_preview_checkbox("poise",           self.poise_check)
        self._connect_preview_checkbox("npc_resistances", self.npcres_check)

        self.preview_enable_check.toggled.connect(lambda _b: self._update_preview())
        self.btn_apply.clicked.connect(self.on_apply)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_reset.clicked.connect(self.on_reset)

        self.btn_toggle_advanced.toggled.connect(self._set_advanced_visible)
        self.btn_preset_save.clicked.connect(self._save_preset_dialog)
        self.btn_preset_load.clicked.connect(self._load_preset_dialog)
        self.btn_preview_ini.clicked.connect(self._show_sdt_preview)

        # Theme
        pal = QApplication.instance().palette()
        qss = build_app_stylesheet(pal, dark_override=self.force_dark)
        try:
            self.setStyleSheet(qss)
        except Exception:
            pass

        # Sélectionne les valeurs par défaut du JSON, sans réordonner les listes
        self._apply_json_defaults()

        # Initial state
        self._apply_ui_visibility()
        self._update_framework_compat_ui()
        self._init_first_preview()
        self._update_status_line()
        self._start_dxdiag_worker_if_needed()
        self._set_advanced_visible(True)

        self.resize(1120, 0)

    # ---------- Helpers ----------

    def _on_rules_changed(self, _path: str):
        self.rules = load_rules_fresh()
        self.ui_visible = dict(self.rules.get("ui_visibility", {}))
        _LOG.info("Rules reloaded (file change detected).")
        self._apply_ui_visibility()
        self._update_framework_compat_ui()
        self._update_status_line()
        self._init_first_preview()

    def _get_setting(self, key: str, default):
        try:
            return self.organizer.pluginSetting("StartupDashboard", key)
        except Exception:
            return default

    def _is_visible(self, category: str) -> bool:
        return bool(self.ui_visible.get(category, True))

    def _update_status_line(self):
        profile = selected_profile_from_ini()
        pw, ph = detect_primary_resolution()
        ratio = normalize_ratio(pw, ph)
        base = f"Profile: {profile}   |   Primary: {pw}x{ph} ({ratio})"
        if self._is_visible("dlss"):
            wddm = dxdiag_max_wddm()
            capable = "Yes" if (wddm >= self.min_wddm) else "No"
            base += f"   |   DLSS-capable (WDDM≥{self.min_wddm}): {capable}"
        self.status.setText(base)

    def _is_default_label(self, label: str) -> bool:
        if not label:
            return False
        low = label.strip().lower()
        return "(default" in low or low == "default"

    def _order_with_default_first(self, labels: List[str]) -> List[str]:
        """
        Ne réordonne pas. Conserve l'ordre tel que fourni par le JSON.
        La sélection par défaut est gérée séparément via _apply_json_defaults().
        """
        return labels


    def _apply_json_defaults(self, skip_keys: Set[str] = frozenset()):
        defaults = self.rules.get("defaults") or {}
        if not isinstance(defaults, dict):
            return
        combos = {
            "resolution":          self.reso_combo,
            "difficulty":          self.diff_combo,
            "main_menu":           self.menu_combo,
            "graphics_framework":  self.framework_combo,
            "enb_preset":          self.enb_combo,
            "ini_base":            self.ini_base_combo,
            "anti_aliasing":       self.aa_combo,
            "ui_mod":              self.ui_combo,
        }
        for cat, combo in combos.items():
            if cat in skip_keys or not self._is_visible(cat):
                continue
            wanted = defaults.get(cat)
            if not wanted:
                continue
            try:
                idx = combo.findText(wanted, Qt.MatchFlag.MatchFixedString)
            except Exception:
                idx = combo.findText(wanted)
            if idx < 0:
                for i in range(combo.count()):
                    if combo.itemText(i).strip().lower() == str(wanted).strip().lower():
                        idx = i
                        break
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                _LOG.warning(f"defaults[{cat!r}] unknown value: {wanted!r}")

    def _guess_main_menu_labels(self) -> List[str]:
        labels = set()
        try:
            for mod in os.listdir(mo2_mods_dir()):
                low = mod.lower()
                if low.startswith("main menu - "):
                    labels.add(mod[len("Main Menu - "):])
        except Exception as e:
            _LOG.warning(f"Main menu guess failed: {e}")
        return sorted(labels)

    def _is_community_shaders(self, text: str) -> bool:
        t = (text or "").strip().lower()
        return t == "community shaders" or t.startswith("community")

    # ---------- UI visibility from JSON ----------

    def _apply_ui_visibility(self):
        for cat, row in [
            ("resolution", self._row_reso),
            ("graphics_framework", self._row_framework),
            ("difficulty", self._row_diff),
            ("main_menu", self._row_menu),
            ("ui_mod", self._row_ui),
            ("enb_preset", self._row_enb),
            ("anti_aliasing", self._row_aa),
            ("ini_base", self._row_ini),
        ]:
            vis = self._is_visible(cat)
            for w in (row if isinstance(row, tuple) else (row,)):
                if isinstance(w, tuple):
                    for ww in w:
                        ww.setVisible(vis)
                        ww.setEnabled(vis)
                else:
                    w.setVisible(vis)
                    w.setEnabled(vis)

        cb_map = {
            "dlss": self._dlss_wrapper,
            "nsfw": self.nsfw_check,
            "gamepad": self.gamepad_check,
            "poise": self.poise_check,
            "npc_resistances": self.npcres_check,
        }
        for cat, w in cb_map.items():
            vis = self._is_visible(cat)
            w.setVisible(vis)
            try:
                w.setEnabled(vis)
            except Exception:
                pass

    # ---------- Info button ----------

    def _make_info_button(self, title: str, text: str) -> QToolButton:
        btn = QToolButton(self)
        btn.setObjectName("infoButton")
        btn.setAutoRaise(True)
        try:
            icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation)
        except Exception:
            icon = QApplication.style().standardIcon(QStyle.SP_MessageBoxInformation)
        btn.setIcon(icon)
        btn.setToolTip(title)
        try:
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
        except Exception:
            btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedSize(20, 20)
        def _show():
            QMessageBox.information(self, title, text)
        btn.clicked.connect(_show)
        return btn

    # ---------- Compact/Advanced ----------

    def _set_advanced_visible(self, visible: bool):
        self.btn_toggle_advanced.setText(f"Advanced mode: {'ON' if visible else 'OFF'}")
        for lbl, wid in (self._row_enb, self._row_aa, self._row_ini, self._row_ui):
            show = visible and self._is_visible({
                self._row_enb: "enb_preset",
                self._row_aa:  "anti_aliasing",
                self._row_ini: "ini_base",
                self._row_ui:  "ui_mod",
            }[(lbl, wid)])
            for w in (lbl, wid):
                w.setVisible(show)
                w.setEnabled(show)
        for cat, w in [("nsfw", self.nsfw_check), ("poise", self.poise_check)]:
            show = visible and self._is_visible(cat)
            w.setVisible(show)
            w.setEnabled(show)
        self.npcres_check.setVisible(self._is_visible("npc_resistances"))
        self.npcres_check.setEnabled(self._is_visible("npc_resistances"))
        self.gamepad_check.setVisible(self._is_visible("gamepad"))
        self.gamepad_check.setEnabled(self._is_visible("gamepad"))
        if hasattr(self, "_dlss_wrapper"):
            self._dlss_wrapper.setVisible(self._is_visible("dlss"))
            try:
                self._dlss_wrapper.setEnabled(self._is_visible("dlss"))
            except Exception:
                pass
        self._update_framework_compat_ui()

    # ---------- Framework compatibility ----------

    def _update_framework_compat_ui(self):
        fw = self.framework_combo.currentText()
        cs = self._is_community_shaders(fw)

        msg = "Not applicable with Community Shaders."
        if self._is_visible("enb_preset"):
            self.enb_combo.setToolTip(msg if cs else "")
        if self._is_visible("anti_aliasing"):
            self.aa_combo.setToolTip(msg if cs else "")
        if self._is_visible("dlss"):
            self.dlss_check.setToolTip(msg if cs else "Preset can be auto-checked if capable (WDDM).")

        if self.hide_incompatible:
            allow = (not cs) and self.btn_toggle_advanced.isChecked() and self._is_visible("enb_preset")
            self.enb_combo.setVisible(allow); self._row_enb[0].setVisible(allow)
            allow_aa = (not cs) and self.btn_toggle_advanced.isChecked() and self._is_visible("anti_aliasing")
            self._row_aa[1].setVisible(allow_aa); self._row_aa[0].setVisible(allow_aa)
            if hasattr(self, "_dlss_wrapper"):
                self._dlss_wrapper.setVisible(self._is_visible("dlss") and not cs)
        else:
            self.enb_combo.setEnabled((not cs) and self._is_visible("enb_preset"))
            self.aa_combo.setEnabled((not cs) and self._is_visible("anti_aliasing"))
            if self._is_visible("dlss"):
                self.dlss_check.setEnabled(not cs)
            if cs and self.dlss_check.isChecked():
                self.dlss_check.setChecked(False)

        try:
            color_warn = "#d08a00"
            color_norm = ""
            if self._is_visible("enb_preset"):
                self._row_enb[0].setStyleSheet(f"color: {color_warn};" if cs else color_norm)
            if self._is_visible("anti_aliasing"):
                self._row_aa[0].setStyleSheet(f"color: {color_warn};" if cs else color_norm)
        except Exception:
            pass

        if getattr(self, "_active_preview_category", None) == "graphics_framework":
            self._update_preview("graphics_framework")

    # ---------- Resolution UI ----------

    def _populate_resolution_combo(self):
        pw, ph = detect_primary_resolution()
        ratio_key = normalize_ratio(pw, ph)
        options = RESOLUTIONS_BY_RATIO.get(ratio_key) or RESOLUTIONS_BY_RATIO["16:9"]

        self.reso_combo.clear()
        for r in options:
            self.reso_combo.addItem(r)

        nearest = nearest_in_list((pw, ph), options)
        if nearest is not None:
            idx = self.reso_combo.findText(nearest)
            if idx >= 0:
                self.reso_combo.setCurrentIndex(idx)

    def _resolution_bucket_from_choice(self) -> str:
        return bucket_from_resolution(self.reso_combo.currentText())

    # ---------- DLSS auto-check ----------

    def _start_dxdiag_worker_if_needed(self):
        if not self._is_visible("dlss"):
            _LOG.info("DLSS UI hidden by ui_visibility → skipping DLSS auto-check.")
            return
        if not self.auto_check_dlss:
            _LOG.info("AutoCheckDLSS is disabled in settings.")
            return
        if self._is_community_shaders(self.framework_combo.currentText()):
            _LOG.info("Framework is Community Shaders → skipping DLSS auto-check.")
            return
        self._dxw = DxdiagWorkerFactory(self.min_wddm)
        self._dxw.done.connect(self._on_wddm_ready)
        self._dxw.start()

    def _on_wddm_ready(self, wddm: float):
        capable = (wddm >= self.min_wddm)
        if self._is_visible("dlss"):
            self.dlss_check.setChecked(capable)
        self._update_status_line()

    # ---------- Preview ----------

    def _connect_preview_signal(self, category: str, combo: QComboBox):
        if category not in (self.rules.get("previews") or {}):
            return
        try:
            combo.currentTextChanged.connect(lambda _t: self._on_combo_preview(category))
        except Exception:
            combo.currentIndexChanged.connect(lambda _i: self._on_combo_preview(category))

    def _connect_preview_checkbox(self, category: str, checkbox: QCheckBox):
        if category not in (self.rules.get("previews") or {}):
            return
        checkbox.toggled.connect(lambda _b: self._on_combo_preview(category))

    def _init_first_preview(self):
        preview_map = self.rules.get("previews") or {}
        for cat in preview_map.keys():
            if self._is_visible(cat):
                self._active_preview_category = cat
                self._update_preview(cat)
                break

    def _on_combo_preview(self, category: str):
        if not self._is_visible(category):
            return
        self._active_preview_category = category
        self._update_preview(category)

    def _get_combo_for_category(self, category: str) -> Optional[QComboBox]:
        mapping = {
            "resolution":         self.reso_combo,
            "difficulty":         self.diff_combo,
            "main_menu":          self.menu_combo,
            "graphics_framework": self.framework_combo,
            "enb_preset":         self.enb_combo,
            "ini_base":           self.ini_base_combo,
            "anti_aliasing":      self.aa_combo,
            "ui_mod":             self.ui_combo,
        }
        return mapping.get(category)

    def _get_value_for_category(self, category: str) -> Optional[str]:
        if not self._is_visible(category):
            return None
        combo = self._get_combo_for_category(category)
        if combo is not None:
            return combo.currentText()
        cb_map = {
            "dlss":            self.dlss_check,
            "nsfw":            self.nsfw_check,
            "gamepad":         self.gamepad_check,
            "poise":           self.poise_check,
            "npc_resistances": self.npcres_check,
        }
        cb = cb_map.get(category)
        if cb is not None:
            return "On" if cb.isChecked() else "Off"
        return None

    def _normalize_key(self, s: str) -> str:
        import re
        txt = (s or "").strip().lower()
        txt = re.sub(r"\(\s*default\s*\)", "", txt, flags=re.IGNORECASE)
        txt = re.sub(r"\s+", " ", txt).strip()
        return txt

    def _lookup_preview_path(self, category: str, value: str) -> Optional[Path]:
        if not self._is_visible(category):
            return None
        cat_map = (self.rules.get("previews") or {}).get(category) or {}
        by_norm = {self._normalize_key(k): v for k, v in cat_map.items()}
        rel = by_norm.get(self._normalize_key(value))
        if not rel:
            raw = (value or "")
            import re
            if "(Default" in raw or "(default" in raw:
                stripped = re.sub(r"\(\s*default\s*\)", "", raw, flags=re.IGNORECASE)
                rel = by_norm.get(self._normalize_key(stripped))
        if not rel:
            return None
        return resolve_preview_path(rel)

    def _update_preview(self, category: Optional[str] = None):
        if not self.preview_enable_check.isChecked():
            self.preview_label.set_source_pixmap(None)
            return
        cat = category or self._active_preview_category
        if not cat or not self._is_visible(cat):
            self.preview_label.set_source_pixmap(None)
            return

        value = self._get_value_for_category(cat)
        if value is None:
            self.preview_label.set_source_pixmap(None)
            return

        path = self._lookup_preview_path(cat, value)
        if path and path.exists():
            try:
                pm = QPixmap(str(path))
                if not pm.isNull():
                    self.preview_label.set_source_pixmap(pm)
                    return
            except Exception as e:
                _LOG.warning(f"Preview load failed: {e}")
        self.preview_label.set_source_pixmap(None)

    # ---------- Presets ----------

    def _collect_state(self) -> Dict:
        return {
            "resolution": self.reso_combo.currentText(),
            "difficulty": self.diff_combo.currentText(),
            "main_menu":  self.menu_combo.currentText(),
            "graphics_framework":  self.framework_combo.currentText(),
            "enb_preset": self.enb_combo.currentText(),
            "anti_aliasing": self.aa_combo.currentText(),
            "ini_base": self.ini_base_combo.currentText(),
            "ui_mod": self.ui_combo.currentText(),
            "dlss": self.dlss_check.isChecked(),
            "nsfw": self.nsfw_check.isChecked(),
            "gamepad": self.gamepad_check.isChecked(),
            "poise": self.poise_check.isChecked(),
            "npc_resistances": self.npcres_check.isChecked(),
            "advanced": self.btn_toggle_advanced.isChecked(),
        }

    def _apply_state(self, data: Dict):
        def set_combo(combo: QComboBox, value: str):
            if value is None:
                return
            idx = -1
            try:
                idx = combo.findText(value, Qt.MatchFlag.MatchFixedString)
            except Exception:
                idx = combo.findText(value)
            if idx < 0:
                val_low = str(value).strip().lower()
                for i in range(combo.count()):
                    if combo.itemText(i).strip().lower() == val_low:
                        idx = i
                        break
            if idx >= 0:
                combo.setCurrentIndex(idx)

        for cat, combo in [
            ("resolution", self.reso_combo),
            ("difficulty", self.diff_combo),
            ("main_menu", self.menu_combo),
            ("graphics_framework", self.framework_combo),
            ("enb_preset", self.enb_combo),
            ("anti_aliasing", self.aa_combo),
            ("ini_base", self.ini_base_combo),
            ("ui_mod", self.ui_combo),
        ]:
            if self._is_visible(cat):
                set_combo(combo, data.get(cat))

        for cb, key in [(self.dlss_check, "dlss"), (self.nsfw_check, "nsfw"),
                        (self.gamepad_check, "gamepad"), (self.poise_check, "poise"),
                        (self.npcres_check, "npc_resistances")]:
            if key in data and self._is_visible(key):
                cb.setChecked(bool(data[key]))

        adv = data.get("advanced")
        if adv is not None:
            self.btn_toggle_advanced.setChecked(bool(adv))
            self._set_advanced_visible(bool(adv))

    def _save_preset_dialog(self):
        try:
            self.PRESETS_DIR.mkdir(parents=True, exist_ok=True)
            path, _ = QFileDialog.getSaveFileName(self, "Save preset", str(self.PRESETS_DIR / "preset.json"), "JSON (*.json)")
            if not path:
                return
            state = self._collect_state()
            Path(path).write_text(json.dumps(state, indent=2), encoding="utf-8")
            QMessageBox.information(self, "Startup Dashboard", "Preset saved.")
        except Exception as e:
            QMessageBox.warning(self, "Startup Dashboard", f"Saving failed: {e}")

    def _load_preset_dialog(self):
        try:
            self.PRESETS_DIR.mkdir(parents=True, exist_ok=True)
            path, _ = QFileDialog.getOpenFileName(self, "Load preset", str(self.PRESETS_DIR), "JSON (*.json)")
            if not path:
                return
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("Invalid preset file.")
            self._apply_state(data)
            self._update_preview()
            QMessageBox.information(self, "Startup Dashboard", "Preset loaded.")
        except Exception as e:
            QMessageBox.warning(self, "Startup Dashboard", f"Loading failed: {e}")

    # ---------- SDT .ini preview ----------

    def _show_sdt_preview(self):
        try:
            profile = selected_profile_from_ini()
            reso_text = self.reso_combo.currentText()
            final_text, base_text = compose_sdt_text_for(reso_text, profile)

            dlg = QDialog(self)
            dlg.setWindowTitle("Preview — SSEDisplayTweaks.ini (Overwrite)")
            lay = QVBoxLayout(dlg)

            tabs = QTabWidget(dlg)

            edit_final = QPlainTextEdit(dlg)
            edit_final.setReadOnly(True)
            edit_final.setPlainText(final_text)
            tabs.addTab(edit_final, "Final file")

            if base_text is not None:
                import difflib
                diff = difflib.unified_diff(
                    base_text.splitlines(),
                    final_text.splitlines(),
                    fromfile="base (enabled mod)",
                    tofile="final (Overwrite)",
                    lineterm=""
                )
                edit_diff = QPlainTextEdit(dlg)
                edit_diff.setReadOnly(True)
                edit_diff.setPlainText("\n".join(diff))
                tabs.addTab(edit_diff, "Diff (base → final)")

            lay.addWidget(tabs, 1)
            btn = QPushButton("Close", dlg)
            btn.clicked.connect(dlg.accept)
            lay.addWidget(btn)

            pal = QApplication.instance().palette()
            dlg.setStyleSheet(build_app_stylesheet(pal, dark_override=self.force_dark))
            dlg.resize(800, 560)
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(self, "Startup Dashboard", f"Unable to display the preview: {e}")

    # ---------- Actions ----------

    def _merge_rules_key(self, category: str, key: str, mods_enable: Set[str], mods_disable: Set[str]):
        data = self.rules.get(category, {}).get(key, {})
        for m in data.get("enable", []):
            mods_enable.add(m); mods_disable.discard(m)
        for m in data.get("disable", []):
            mods_disable.add(m); mods_enable.discard(m)

    def _merge_resolution_selection(self, mods_enable: Set[str], mods_disable: Set[str]):
        bucket = self._resolution_bucket_from_choice()
        self._merge_rules_key("resolution", bucket, mods_enable, mods_disable)

    def on_reset(self):
        try:
            flag = Path(__file__).resolve().parent / "first_run.flag"
            if flag.exists():
                flag.unlink()
            QMessageBox.information(self, "Startup Dashboard", "The dashboard will reappear on next launch.")
        except Exception as e:
            QMessageBox.warning(self, "Startup Dashboard", f"Reset failed: {e}")

    def on_apply(self):
        self.rules = load_rules_fresh()
        self.ui_visible = dict(self.rules.get("ui_visibility", {}))

        profile     = selected_profile_from_ini()

        reso_text   = self.reso_combo.currentText()
        reso_bucket = self._resolution_bucket_from_choice()
        diff        = self.diff_combo.currentText()
        menu        = self.menu_combo.currentText()
        framework   = self.framework_combo.currentText()
        framework_is_cs = self._is_community_shaders(framework)

        nsfw_on     = self.nsfw_check.isChecked()
        gamepad_on  = self.gamepad_check.isChecked()
        poise_on    = self.poise_check.isChecked()
        npcres_on   = self.npcres_check.isChecked()

        enb_preset  = self.enb_combo.currentText()
        ini_base    = self.ini_base_combo.currentText()
        aa_choice   = self.aa_combo.currentText()
        dlss_on     = self.dlss_check.isChecked()

        mods_enable: Set[str] = set()
        mods_disable: Set[str] = set()

        if self._is_visible("resolution"):
            self._merge_resolution_selection(mods_enable, mods_disable)
        if self._is_visible("difficulty"):
            self._merge_rules_key("difficulty", diff, mods_enable, mods_disable)
        if self._is_visible("main_menu"):
            self._merge_rules_key("main_menu", menu, mods_enable, mods_disable)
        if self._is_visible("nsfw"):
            self._merge_rules_key("nsfw", "On" if nsfw_on else "Off", mods_enable, mods_disable)
        if self._is_visible("gamepad"):
            self._merge_rules_key("gamepad", "On" if gamepad_on else "Off", mods_enable, mods_disable)
        if self._is_visible("graphics_framework"):
            self._merge_rules_key("graphics_framework", framework, mods_enable, mods_disable)
        if self._is_visible("poise"):
            self._merge_rules_key("poise", "On" if poise_on else "Off", mods_enable, mods_disable)
        if self._is_visible("ini_base"):
            self._merge_rules_key("ini_base", ini_base, mods_enable, mods_disable)
        if self._is_visible("npc_resistances"):
            self._merge_rules_key("npc_resistances", "On" if npcres_on else "Off", mods_enable, mods_disable)
        if self._is_visible("ui_mod"):
            self._merge_rules_key("ui_mod", self.ui_combo.currentText(), mods_enable, mods_disable)

        if not framework_is_cs:
            if self._is_visible("enb_preset"):
                self._merge_rules_key("enb_preset", enb_preset, mods_enable, mods_disable)
            if self._is_visible("anti_aliasing"):
                self._merge_rules_key("anti_aliasing", aa_choice, mods_enable, mods_disable)
            if self._is_visible("dlss"):
                self._merge_rules_key("dlss", "On" if dlss_on else "Off", mods_enable, mods_disable)

        prof_over = self.rules.get("profile_overrides", {}).get(profile, {})
        for m in prof_over.get("enable", []):
            mods_enable.add(m); mods_disable.discard(m)
        for m in prof_over.get("disable", []):
            mods_disable.add(m); mods_enable.discard(m)

        # 1) Mods
        try:
            self.btn_apply.setEnabled(False)
            apply_mod_sets(profile, mods_enable, mods_disable)
        except Exception as e:
            _LOG.error(f"Apply mod sets failed: {e}\n{traceback.format_exc()}")
        finally:
            self.btn_apply.setEnabled(True)

        # 2) loadorder.txt + plugins.txt
        try:
            sync_new_plugins_incremental(profile, mods_enable, self.rules.get("plugin_rules", {}))
        except Exception as e:
            _LOG.error(f"Incremental loadorder sync failed: {e}\n{traceback.format_exc()}")

        # 2b) plugingroups.txt
        try:
            sync_plugingroups(profile, self.rules)
        except Exception as e:
            _LOG.error(f"plugingroups.txt sync failed: {e}\n{traceback.format_exc()}")

        # 3) SDT INI
        try:
            if self._is_visible("resolution"):
                sdt_path = apply_resolution_to_sdt(reso_text, profile)
                _LOG.info(f"SSE Display Tweaks resolution set to {reso_text} at {sdt_path}")
        except Exception as e:
            _LOG.error(f"Failed to write SSEDisplayTweaks.ini: {e}\n{traceback.format_exc()}")

        # 4) Flag + feedback
        try:
            (Path(__file__).resolve().parent / "first_run.flag").write_text("run", encoding="utf-8")
            QMessageBox.information(
                self,
                "Startup Dashboard",
                (f"Profile (active): {profile}\n"
                 f"Resolution: {(reso_text + '  (bucket: ' + reso_bucket + ')') if self._is_visible('resolution') else '(hidden)'}\n"
                 f"Difficulty: {diff if self._is_visible('difficulty') else '(hidden)'}\n"
                 f"Main Menu: {menu if self._is_visible('main_menu') else '(hidden)'}\n"
                 f"Framework: {framework if self._is_visible('graphics_framework') else '(hidden)'}\n"
                 f"ENB Preset: {enb_preset if (self._is_visible('enb_preset') and not framework_is_cs) else '(n/a)'}\n"
                 f"Base INI: {ini_base if self._is_visible('ini_base') else '(hidden)'}\n"
                 f"Anti-aliasing: {aa_choice if (self._is_visible('anti_aliasing') and not framework_is_cs) else '(n/a)'}\n"
                 f"NSFW: {('On' if nsfw_on else 'Off') if self._is_visible('nsfw') else '(hidden)'}\n"
                 f"Gamepad: {('On' if gamepad_on else 'Off') if self._is_visible('gamepad') else '(hidden)'}\n"
                 f"Poise: {('On' if poise_on else 'Off') if self._is_visible('poise') else '(hidden)'}\n"
                 f"NPC Resistances: {('On' if npcres_on else 'Off') if self._is_visible('npc_resistances') else '(hidden)'}\n"
                 f"UI: {self.ui_combo.currentText() if self._is_visible('ui_mod') else '(hidden)'}\n"
                 f"DLSS/FrameGen: {('On' if dlss_on else 'Off') if (self._is_visible('dlss') and not framework_is_cs) else '(n/a)'}\n\n"
                 f"Load order: updated incrementally in loadorder.txt with auto-activation in plugins.txt\n"
                 f"Mods enabled: {len(mods_enable)} / Mods disabled: {len(mods_disable)}")
            )
            self.accept()
        except Exception as e:
            _LOG.error(f"Finalize failed: {e}\n{traceback.format_exc()}")
            QMessageBox.critical(self, "Startup Dashboard", f"Failed to finalize:\n{e}")


# --------------------------- MO2 Plugin (IPlugin + IPluginTool) ---------------------------

def _run_dashboard(organizer: mobase.IOrganizer, parent: Optional[QWidget] = None) -> None:
    dlg = StartupDialog(organizer, parent)
    result = dlg.exec()
    _LOG.info(f"StartupDashboard dialog result: {result}")


class StartupDashboard(mobase.IPlugin, mobase.IPluginTool):
    def __init__(self):
        mobase.IPlugin.__init__(self)
        mobase.IPluginTool.__init__(self)
        self._organizer: Optional[mobase.IOrganizer] = None
        self._parent: Optional[QWidget] = None
        self._plugin_path: str = str(Path(__file__).resolve().parent)
        self._icon_cache: Optional[QIcon] = None
        self._plugin_path = self._plugin_path

    # ---------- IPlugin ----------
    def init(self, organizer: mobase.IOrganizer) -> bool:
        self._organizer = organizer
        self._icon_cache = None
        try:
            first_run_only = organizer.pluginSetting(self.name(), "ShowOnFirstRunOnly")
        except Exception:
            first_run_only = True

        # s'assure que le fichier de règles existe
        try:
            _ = load_rules_fresh()
        except Exception:
            pass

        flag = Path(__file__).resolve().parent / "first_run.flag"
        if not first_run_only or not flag.exists():
            try:
                _run_dashboard(organizer, self._parent)
            except Exception as e:
                _LOG.error(f"Dialog failed: {e}\n{traceback.format_exc()}")

        return True

    def name(self) -> str:
        return "StartupDashboard"

    def author(self) -> str:
        return "Alaxouche"

    def description(self) -> str:
        return ("Startup dashboard with ratio-based UI, DLSS auto-check, presets, preview panel, "
                "MO2 theme following, SDT resolution write, "
                "incremental loadorder.txt placement with auto-activation in plugins.txt, "
                "Tool button relaunch, and JSON-driven UI visibility per category.")

    def version(self) -> mobase.VersionInfo:
        return mobase.VersionInfo(2, 9, 0)

    def settings(self):
        return [
            mobase.PluginSetting("ShowOnFirstRunOnly", "Show the dashboard only on first launch.", True),
            mobase.PluginSetting("HideIncompatibleOptions", "Hide ENB-only options when Community Shaders is selected.", False),
            mobase.PluginSetting("AutoCheckDLSS", "Auto-check DLSS/FrameGen capability.", True),
            mobase.PluginSetting("DLSSMinimumWDDM", "Minimum WDDM required, e.g. 2.9.", "2.9"),
            mobase.PluginSetting("FollowMO2Theme", "Apply MO2 theme style/palette when possible.", True),
            mobase.PluginSetting("ForceDarkTheme", "Force a built-in dark stylesheet.", False),
        ]

    # ---------- IPluginTool ----------
    def displayName(self) -> str:
        return "Startup Dashboard"

    def tooltip(self) -> str:
        return "Configure the profile and synchronize loadorder.txt + auto-activation (Skyrim)"

    def _is_theme_dark_from_mo2(self) -> Optional[bool]:
        try:
            style_name, is_dark = read_mo2_style()
            if style_name is not None:
                return bool(is_dark)
        except Exception:
            pass
        try:
            if not self._organizer:
                return None
            import configparser, os
            cfg = configparser.ConfigParser()
            ini = os.path.abspath(os.path.join(self._organizer.pluginDataPath(), "..", "ModOrganizer.ini"))
            if os.path.exists(ini):
                cfg.read(ini, encoding="utf-8")
                style = cfg.get("Settings", "style", fallback="")
                return True if "dark" in style.lower() else False
        except Exception:
            pass
        return None

    def icon(self) -> QIcon:
        if self._icon_cache is not None:
            return self._icon_cache

        plugin_dir = Path(self._plugin_path)
        is_dark = self._is_theme_dark_from_mo2()
        icon_name = "iconDark.png" if is_dark is True else "iconWhite.png"

        candidate = plugin_dir / icon_name
        if candidate.exists():
            self._icon_cache = QIcon(str(candidate))
            return self._icon_cache

        alt = plugin_dir / ("iconWhite.png" if icon_name == "iconDark.png" else "iconDark.png")
        if alt.exists():
            self._icon_cache = QIcon(str(alt))
            return self._icon_cache

        try:
            qrc_candidate = QIcon(f":/{icon_name}")
            if not qrc_candidate.isNull():
                self._icon_cache = qrc_candidate
                return self._icon_cache
        except Exception:
            pass

        self._icon_cache = QIcon()
        return self._icon_cache

    def setParentWidget(self, widget: QWidget):
        self._parent = widget

    def display(self):
        if self._organizer is None:
            _LOG.error("Organizer not set; cannot open dashboard.")
            return
        try:
            _run_dashboard(self._organizer, self._parent)
        except Exception as e:
            _LOG.error(f"display() failed: {e}\n{traceback.format_exc()}")
