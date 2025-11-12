# -*- coding: utf-8 -*-
import os
import configparser
from pathlib import Path
from typing import List, Set, Tuple, Optional

from .logging_sd import _LOG
from .files import atomic_write
from .regex_cache import enabled_cache

# -------- racines MO2 --------

def mo2_root() -> Path:
    p = Path(__file__).resolve().parent.parent
    for parent in [p] + list(p.parents):
        if (parent / "mods").exists() and (parent / "profiles").exists():
            return parent
    return p.parent

def mo2_mods_dir() -> Path:
    return mo2_root() / "mods"

def mo2_profiles_dir() -> Path:
    return mo2_root() / "profiles"

def overwrite_dir() -> Path:
    return mo2_root() / "overwrite"

# -------- UI / Qt helpers --------

def apply_qt_style_from_name(style_name: Optional[str]) -> None:
    if not style_name:
        return
    try:
        # import paresseux pour éviter dépendance si utilisé côté non-Qt
        try:
            from PyQt6.QtWidgets import QStyleFactory, QApplication
        except Exception:
            from PyQt5.QtWidgets import QStyleFactory, QApplication
        keys = {s.lower(): s for s in QStyleFactory.keys()}
        key = style_name.lower().strip()
        qt_style = keys.get(key)
        if qt_style:
            QApplication.setStyle(QStyleFactory.create(qt_style))
    except Exception as e:
        _LOG.debug(f"apply_qt_style_from_name ignored: {e}")

def selected_profile_from_ini() -> str:
    ini = mo2_root() / "ModOrganizer.ini"
    if not ini.exists():
        return "Default"
    try:
        text = ini.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            if line.strip().startswith("selected_profile"):
                raw = line.split("=", 1)[-1].strip()
                return raw.replace("@ByteArray(", "").replace(")", "").strip() or "Default"
    except Exception as e:
        _LOG.warning(f"selected_profile_from_ini failed: {e}")
    return "Default"

def read_mo2_style() -> Tuple[Optional[str], bool]:
    ini = mo2_root() / "ModOrganizer.ini"
    if not ini.exists():
        return None, False
    cp = configparser.ConfigParser()
    try:
        cp.read(ini, encoding="utf-8")
    except Exception:
        try:
            raw = ini.read_text(encoding="utf-8", errors="ignore")
            cp.read_string(raw)
        except Exception:
            return None, False
    val = None
    for sec in ("settings", "Settings", "General", "general"):
        if cp.has_section(sec) and cp.has_option(sec, "style"):
            val = cp.get(sec, "style", fallback=None)
            break
    if not val:
        return None, False
    is_dark = "dark" in val.lower()
    return val.strip(), is_dark

# -------- modlist.txt --------

def modlist_path(profile: str) -> Path:
    p = mo2_profiles_dir() / profile
    p.mkdir(parents=True, exist_ok=True)
    return p / "modlist.txt"

def read_modlist(path: Path) -> List[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    except Exception as e:
        _LOG.error(f"read_modlist error: {e}")
        return []

def write_modlist(path: Path, lines: List[str]) -> None:
    try:
        normalized = [(ln if ln.endswith("\n") else ln + "\n") for ln in lines]
        path.write_text("".join(normalized), encoding="utf-8")
    except Exception as e:
        _LOG.error(f"write_modlist error: {e}")

def set_mod_enabled_in_lines(lines: List[str], mod_name: str, enable: bool) -> List[str]:
    prefix = "+" if enable else "-"
    entry = f"{prefix}{mod_name}"
    norm = [ln if ln.endswith("\n") else ln + "\n" for ln in lines]

    positions = []
    for i, ln in enumerate(norm):
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        if len(s) >= 2 and s[1:].strip() == mod_name:
            positions.append(i)

    if not positions:
        norm.append(entry + "\n")
        return norm

    keep_idx = positions[-1]
    filtered: List[str] = []
    for i, ln in enumerate(norm):
        s = ln.strip()
        if len(s) >= 2 and s[1:].strip() == mod_name:
            continue
        filtered.append(ln)
    insert_idx = min(keep_idx, len(filtered))
    filtered.insert(insert_idx, entry + "\n")
    return filtered

def apply_mod_sets(profile: str, mods_to_enable: Set[str], mods_to_disable: Set[str]) -> None:
    path = modlist_path(profile)
    lines = read_modlist(path)

    final_enable = set(mods_to_enable) - set(mods_to_disable)
    final_disable = set(mods_to_disable)

    try:
        existing_mods = set(os.listdir(mo2_mods_dir()))
        unknown_enable = sorted([m for m in final_enable if m not in existing_mods])
        unknown_disable = sorted([m for m in final_disable if m not in existing_mods])
        if unknown_enable or unknown_disable:
            _LOG.warning("Unknown in 'mods/': + %s ; - %s", unknown_enable, unknown_disable)
    except Exception as e:
        _LOG.debug(f"Unable to list mods/: {e}")

    original = lines[:]
    for m in sorted(final_enable):
        lines = set_mod_enabled_in_lines(lines, m, True)
    for m in sorted(final_disable):
        lines = set_mod_enabled_in_lines(lines, m, False)

    if lines != original:
        write_modlist(path, lines)
        _LOG.info("Applied to profile '%s': +%d / -%d", profile, len(final_enable), len(final_disable))
    else:
        _LOG.info("Profile '%s': no changes.", profile)

# -------- util: mods activés (cache lié à modlist.txt) --------

def enabled_mod_names(profile: str) -> List[str]:
    path = modlist_path(profile)
    try:
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        return []
    key = (profile, mtime)
    cached = enabled_cache.get(key)
    if cached is not None:
        return cached

    names: List[str] = []
    for ln in read_modlist(path):
        s = ln.strip()
        if s and not s.startswith("#") and s[0] == "+":
            names.append(s[1:].strip())

    enabled_cache.clear()
    enabled_cache[key] = names
    return names
