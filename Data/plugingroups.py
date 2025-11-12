# -*- coding: utf-8 -*-
from pathlib import Path
from typing import Dict, List, Tuple

from .files import atomic_write
from .logging_sd import _LOG
from .plugins import loadorder_txt_path
from .mo2_helpers import mo2_profiles_dir

def plugingroups_txt_path(profile: str) -> Path:
    return mo2_profiles_dir() / profile / "plugingroups.txt"

def _read_plugingroups_file(path: Path) -> Tuple[Dict[str, str], List[str], List[str]]:
    mapping: Dict[str, str] = {}
    header: List[str] = []
    others: List[str] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except FileNotFoundError:
        return {}, ["# This file is managed by StartupDashboard (plugin_groups)\n"], []
    except Exception:
        return {}, ["# This file is managed by StartupDashboard (plugin_groups)\n"], []

    comments_passed = False
    for raw in lines:
        line = raw.rstrip("\n")
        s = line.strip()
        if not s or s.startswith("#"):
            if not comments_passed:
                header.append(line)
            else:
                others.append(line)
            continue
        comments_passed = True
        if "|" in s:
            left, right = s.split("|", 1)
            plg = left.strip()
            grp = right.strip()
            if plg and grp:
                mapping[plg] = grp
                continue
        others.append(line)

    if not header:
        header = ["# This file is managed by StartupDashboard (plugin_groups)\n"]
    return mapping, header, others

def _write_plugingroups_file(path: Path, ordered_plugins: List[str],
                             mapping: Dict[str, str],
                             header: List[str],
                             others: List[str]) -> None:
    out: List[str] = []
    out.extend([ln if ln.endswith("\n") else ln + "\n" for ln in header])
    if out and out[-1].strip():
        out.append("\n")
    for ln in others:
        out.append(ln if ln.endswith("\n") else ln + "\n")

    seen: set = set()
    for p in ordered_plugins:
        if p in mapping and p not in seen:
            out.append(f"{p}|{mapping[p]}\n")
            seen.add(p)
    for p in sorted(mapping.keys(), key=str.lower):
        if p not in seen:
            out.append(f"{p}|{mapping[p]}\n")
            seen.add(p)

    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, "".join(out))

def sync_plugingroups(profile: str, rules: Dict) -> None:
    group_map: Dict[str, str] = (rules or {}).get("plugin_groups") or {}
    if not isinstance(group_map, dict) or not group_map:
        _LOG.info("plugin_groups missing or empty → no plugingroups.txt write.")
        return
    order = []
    try:
        order = (loadorder_txt_path(profile)).read_text(encoding="utf-8", errors="ignore").splitlines()
        order = [x.strip() for x in order if x.strip()]
    except Exception:
        order = []
    gpath = plugingroups_txt_path(profile)
    existing_map, header, others = _read_plugingroups_file(gpath)
    target_map = dict(existing_map)
    for plugin, group in group_map.items():
        plg = (plugin or "").strip()
        grp = (group or "").strip()
        if plg and grp:
            target_map[plg] = grp
    if target_map != existing_map:
        _write_plugingroups_file(gpath, order, target_map, header, others)
        _LOG.info("plugingroups.txt synchronized: %d entries written.", len(target_map))
    else:
        _LOG.info("plugingroups.txt: no changes required.")
