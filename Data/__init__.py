# -*- coding: utf-8 -*-

# Regroupe des ré-exportations pratiques si vous souhaitez importer depuis Base.*
from .logging_sd import _LOG
from .mo2_helpers import (
    mo2_root, mo2_mods_dir, mo2_profiles_dir, overwrite_dir,
    selected_profile_from_ini, read_mo2_style, apply_qt_style_from_name,
    modlist_path, read_modlist, write_modlist, set_mod_enabled_in_lines,
    apply_mod_sets, enabled_mod_names
)
from .rules import (
    RULES_FILENAME, INMEMORY_DEFAULTS, CATEGORY_ALIASES,
    rules_path, load_rules_fresh
)
from .dxdiag import _safe_float, dxdiag_max_wddm, is_dlss_capable, DxdiagWorkerFactory
from .resolution import (
    RESOLUTIONS_BY_RATIO, bucket_from_resolution,
    detect_primary_resolution, normalize_ratio, nearest_in_list
)
from .sdt_ini import compose_sdt_text_for, apply_resolution_to_sdt
from .plugins import sync_new_plugins_incremental
from .plugingroups import sync_plugingroups
from .preview import resolve_preview_path, ScaledPreviewLabelFactory
from .theme import build_app_stylesheet
