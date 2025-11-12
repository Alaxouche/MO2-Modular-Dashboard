# -*- coding: utf-8 -*-
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .logging_sd import _LOG
from .regex_cache import rules_cache
from .files import read_text

RULES_FILENAME = "StartupDashboard.rules.json"

INMEMORY_DEFAULTS: Dict = {
    "resolution": {
        "720p":   {"enable": [], "disable": []},
        "900p":   {"enable": [], "disable": []},
        "1080p":  {"enable": [], "disable": ["4K Texture Pack"]},
        "1200p":  {"enable": [], "disable": []},
        "1440p":  {"enable": ["2K Texture Pack"], "disable": ["4K Texture Pack"]},
        "1600p":  {"enable": [], "disable": []},
        "4K":     {"enable": ["4K Texture Pack"], "disable": ["2K Texture Pack"]},
        "5K":     {"enable": ["4K Texture Pack"], "disable": []},
        "8K":     {"enable": ["4K Texture Pack"], "disable": []},
    },
    "dlss": {
        "On":  {"enable": ["DLSS"], "disable": ["FSR", "TAAU"]},
        "Off": {"enable": ["TAAU"], "disable": ["DLSS"]},
    },
    "difficulty": {
        "Novice":    {"enable": ["Difficulty - Novice"], "disable": ["Difficulty - Expert", "Difficulty - Legendary"]},
        "Adept":     {"enable": ["Difficulty - Adept"], "disable": ["Difficulty - Expert", "Difficulty - Legendary"]},
        "Expert":    {"enable": ["Difficulty - Expert"], "disable": ["Difficulty - Novice"]},
        "Legendary": {"enable": ["Difficulty - Legendary"], "disable": ["Difficulty - Novice"]},
    },
    "main_menu": {
        "Vanilla": {"enable": ["Main Menu - Vanilla"], "disable": ["Main Menu - Dark", "Main Menu - Fantasy"]},
        "Dark":    {"enable": ["Main Menu - Dark"],    "disable": ["Main Menu - Vanilla", "Main Menu - Fantasy"]},
        "Fantasy": {"enable": ["Main Menu - Fantasy"], "disable": ["Main Menu - Vanilla", "Main Menu - Dark"]},
    },
    "nsfw": {
        "On":  {"enable": ["NSFW Bundle"], "disable": ["SFW Patch"]},
        "Off": {"enable": ["SFW Patch"],   "disable": ["NSFW Bundle"]},
    },
    "gamepad": {
        "On":  {"enable": ["Gamepad UI", "Gamepad Tweaks"], "disable": ["Keyboard UI"]},
        "Off": {"enable": ["Keyboard UI"],                  "disable": ["Gamepad UI"]},
    },
    "graphics_framework": {
        "ENB":               {"enable": ["ENB Binary", "ENB Helper"], "disable": ["Community Shaders"]},
        "Community Shaders": {"enable": ["Community Shaders"],        "disable": ["ENB Binary", "ENB Helper"]},
    },
    "enb_preset": {
        "Rudy ENB":        {"enable": ["ENB Preset - Rudy"],            "disable": ["ENB Preset - PI-CHO", "ENB Preset - Silent Horizons"]},
        "PI-CHO ENB":      {"enable": ["ENB Preset - PI-CHO"],          "disable": ["ENB Preset - Rudy", "ENB Preset - Silent Horizons"]},
        "Silent Horizons": {"enable": ["ENB Preset - Silent Horizons"], "disable": ["ENB Preset - Rudy", "ENB Preset - PI-CHO"]}
    },
    "poise": {
        "On":  {"enable": ["Poise System"], "disable": ["No Poise"]},
        "Off": {"enable": ["No Poise"],     "disable": ["Poise System"]},
    },
    "ini_base": {
        "Low":    {"enable": ["INI Base - Low"],    "disable": ["INI Base - Medium", "INI Base - High"]},
        "Medium": {"enable": ["INI Base - Medium"], "disable": ["INI Base - Low", "INI Base - High"]},
        "High":   {"enable": ["INI Base - High"],   "disable": ["INI Base - Low", "INI Base - Medium"]},
    },
    "anti_aliasing": {
        "FSR":  {"enable": ["FSR AA"],  "disable": ["DLAA"]},
        "DLAA": {"enable": ["DLAA"],    "disable": ["FSR AA"]},
    },
    "npc_resistances": {
        "On":  {"enable": ["NPC Resistances Enabled"], "disable": ["NPC Resistances Removed"]},
        "Off": {"enable": ["NPC Resistances Removed"], "disable": ["NPC Resistances Enabled"]},
    },
    "ui_mod": {
        "Edge UI Explorer": {"enable": ["Edge UI Explorer"], "disable": ["Oathvein UI"]},
        "Oathvein UI":      {"enable": ["Oathvein UI"],      "disable": ["Edge UI Explorer"]},
    },
    "ui_visibility": {
        "resolution": True,
        "dlss": True,
        "difficulty": True,
        "main_menu": True,
        "nsfw": True,
        "gamepad": True,
        "graphics_framework": True,
        "enb_preset": True,
        "poise": True,
        "ini_base": True,
        "anti_aliasing": True,
        "npc_resistances": True,
        "ui_mod": True,
    },
    "profile_overrides": {},
}

CATEGORY_ALIASES: Dict[str, List[str]] = {
    "dlss": ["dlss", "DLSS", "framegen", "frame generation", "Frame Generation"],
    "resolution": ["resolution", "Resolution"],
    "difficulty": ["difficulty", "Difficulty"],
    "main_menu": ["main_menu", "main menu", "Main Menu"],
    "nsfw": ["nsfw", "NSFW"],
    "gamepad": ["gamepad", "controller", "pad", "Gamepad"],
    "graphics_framework": ["graphics_framework", "framework", "graphics framework", "Framework"],
    "enb_preset": ["enb_preset", "enb preset", "enb", "ENB Preset"],
    "poise": ["poise", "poise_system", "Poise"],
    "ini_base": ["ini_base", "ini base", "ini preset", "INI Base"],
    "anti_aliasing": ["anti_aliasing", "anti aliasing", "aa", "Anti-aliasing"],
    "npc_resistances": ["npc_resistances", "npc resistances", "NPC Resistances"],
    "ui_mod": ["ui_mod", "ui mod", "ui", "UI Mod"],
    "profile_overrides": ["profile_overrides", "profile overrides"],
}

def rules_path() -> Path:
    return Path(__file__).resolve().parent.parent / RULES_FILENAME

def _write_default_rules_if_missing() -> None:
    p = rules_path()
    if p.exists():
        return
    try:
        p.write_text(json.dumps(INMEMORY_DEFAULTS, indent=2, ensure_ascii=False), encoding="utf-8")
        _LOG.info(f"Default rules written: {p}")
    except Exception as e:
        _LOG.error(f"Cannot write default rules: {e}")

def _strip_comments_and_trailing_commas(text: str) -> str:
    text = text.lstrip("\ufeff")
    text = re.sub(r"^\s*//.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*#.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    return text

def _load_json_lenient(path: Path) -> Optional[Dict]:
    try:
        raw = read_text(path)
        raw = _strip_comments_and_trailing_commas(raw)
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
        _LOG.error("Rules JSON: root is not an object.")
        return None
    except Exception as e:
        _LOG.error(f"Failed to read JSON '{path.name}': {e}")
        return None

def _validate_rules_minimal(data: dict) -> bool:
    return isinstance(data, dict) and "resolution" in data and isinstance(data["resolution"], dict)

def _canon_key_map(data: Dict) -> Dict[str, str]:
    present = {k.lower(): k for k in data.keys()}
    mapping: Dict[str, str] = {}
    for canon, aliases in CATEGORY_ALIASES.items():
        for alias in aliases:
            if alias.lower() in present:
                mapping[canon] = present[alias.lower()]
                break
    return mapping

def _normalize_ui_visibility_map(ui_vis_raw: Dict) -> Dict[str, bool]:
    out: Dict[str, bool] = dict(INMEMORY_DEFAULTS.get("ui_visibility", {}))
    if not isinstance(ui_vis_raw, dict):
        return out
    present = {k.lower(): v for k, v in ui_vis_raw.items()}
    for canon, aliases in CATEGORY_ALIASES.items():
        for alias in aliases:
            if alias.lower() in present:
                try:
                    out[canon] = bool(present[alias.lower()])
                except Exception:
                    pass
                break
    return out

def load_rules_fresh() -> Dict:
    p = rules_path()
    if not p.exists():
        _write_default_rules_if_missing()

    mt = p.stat().st_mtime if p.exists() else None
    if rules_cache["mtime"] == mt and rules_cache["data"] is not None:
        return rules_cache["data"]

    data = _load_json_lenient(p) or {}
    if not _validate_rules_minimal(data):
        _LOG.error("Rules file does not match minimal schema. Using in-memory defaults.")
        data = {}

    keymap = _canon_key_map(data)
    result = dict(INMEMORY_DEFAULTS)
    for canon, default_val in INMEMORY_DEFAULTS.items():
        if canon == "ui_visibility":
            continue
        real_key = keymap.get(canon)
        if real_key:
            result[canon] = data.get(real_key, default_val)

    if isinstance(data.get("defaults"), dict):
        result["defaults"] = data["defaults"]
    if isinstance(data.get("previews"), dict):
        result["previews"] = data["previews"]
    if isinstance(data.get("plugin_rules"), dict):
        result["plugin_rules"] = data["plugin_rules"]
    if isinstance(data.get("plugin_groups"), dict):
        result["plugin_groups"] = data["plugin_groups"]

    result["ui_visibility"] = _normalize_ui_visibility_map(data.get("ui_visibility", {}))

    _LOG.info("Categories (canonical→real): %s",
              {k: keymap.get(k, "(fallback)") for k in INMEMORY_DEFAULTS if k != "ui_visibility"})
    rules_cache["mtime"] = mt
    rules_cache["data"] = result
    return result
