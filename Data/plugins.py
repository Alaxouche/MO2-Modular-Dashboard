# -*- coding: utf-8 -*-
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .logging_sd import _LOG
from .files import atomic_write
from .mo2_helpers import mo2_profiles_dir, mo2_mods_dir

# -------- chemins loadorder/plugins --------

def loadorder_txt_path(profile: str) -> Path:
    return mo2_profiles_dir() / profile / "loadorder.txt"

def plugins_txt_path(profile: str) -> Path:
    return mo2_profiles_dir() / profile / "plugins.txt"

# -------- util plugins --------

def _norm(s: str) -> str:
    return re.sub(r"[\s_\-]+", "", (s or "").strip().lower())

def _plugin_ext_rank(name: str) -> int:
    n = (name or "").lower()
    if n.endswith(".esm"): return 0
    if n.endswith(".esp"): return 1
    if n.endswith(".esl"): return 2
    return 3

def _discover_plugins_for_mod(mod_name: str) -> List[str]:
    out: Set[str] = set()
    base = mo2_mods_dir() / mod_name
    if not base.exists():
        return []
    candidates = [base, base / "Data"]
    exts = (".esp", ".esm", ".esl")
    for root in candidates:
        try:
            for p in root.rglob("*"):
                if p.is_file() and p.suffix.lower() in exts:
                    out.add(p.name)
        except Exception:
            pass
    return sorted(out, key=str.lower)

# -------- I/O loadorder.txt --------

def _read_loadorder_file(path: Path) -> List[str]:
    try:
        return [ln.strip() for ln in path.read_text(encoding="utf-8", errors="ignore").splitlines()
                if ln.strip() and not ln.strip().startswith("#")]
    except FileNotFoundError:
        return []
    except Exception:
        return []

def _write_loadorder_file(path: Path, order: List[str]) -> None:
    text = "".join(f"{p}\n" for p in order)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, text)

# -------- I/O plugins.txt --------

def _read_plugins_file(path: Path) -> List[str]:
    try:
        return path.read_text(encoding="utf-8", errors="ignore").splitlines(True)
    except FileNotFoundError:
        return [
            "# This file is used by Skyrim to keep track of your downloaded content.\n",
            "# Managed by StartupDashboard — auto-enabled plugins\n"
        ]
    except Exception:
        return []

def _write_plugins_file(path: Path, lines: List[str]) -> None:
    if not lines:
        lines = [
            "# This file is used by Skyrim to keep track of your downloaded content.\n",
            "# Managed by StartupDashboard — auto-enabled plugins\n"
        ]
    if not lines[-1].endswith("\n"):
        lines = lines + ["\n"]
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, "".join(lines))

def _set_plugin_enabled_in_plugins_lines(lines: List[str], plugin: str, enable: bool = True) -> Tuple[List[str], bool]:
    tgt = plugin.strip()
    tgt_low = tgt.lower()
    last_idx = -1
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        name = s[1:].strip() if s.startswith("*") else s
        if name.lower() == tgt_low:
            last_idx = i
    if last_idx >= 0:
        new = lines[:]
        new[last_idx] = f"*{tgt}\n" if enable else f"{tgt}\n"
        return new, (new[last_idx] != lines[last_idx])
    new = lines[:] + [f"*{tgt}\n" if enable else f"{tgt}\n"]
    return new, True

def _ensure_plugin_enabled(profile: str, plugin: str) -> None:
    ppath = plugins_txt_path(profile)
    lines = _read_plugins_file(ppath)
    new_lines, changed = _set_plugin_enabled_in_plugins_lines(lines, plugin, True)
    if changed:
        _write_plugins_file(ppath, new_lines)
        _LOG.info("plugins.txt: '%s' enabled for profile '%s'.", plugin, profile)

def _ensure_all_enabled(profile: str, plugins: List[str]) -> None:
    ppath = plugins_txt_path(profile)
    lines = _read_plugins_file(ppath)
    changed = False
    for pl in plugins:
        lines, c = _set_plugin_enabled_in_plugins_lines(lines, pl, True)
        changed |= c
    if changed:
        _write_plugins_file(ppath, lines)
        _LOG.info("plugins.txt: batch activation of %d plugins for profile '%s'.", len(plugins), profile)

# -------- règles d’ancrage --------

def _resolve_anchor_ci(name_or_regex: Optional[str], names: List[str], allow_regex: bool) -> Set[str]:
    out: Set[str] = set()
    if not name_or_regex:
        return out
    if allow_regex:
        try:
            rgx = re.compile(name_or_regex, re.IGNORECASE)
            for n in names:
                if rgx.search(n):
                    out.add(n)
            return out
        except Exception:
            pass
    low = str(name_or_regex).strip().lower()
    for n in names:
        if n.strip().lower() == low:
            out.add(n)
    return out

def _match_rule_for_plugin(plugin: str, rules: Dict) -> Dict:
    lst = (rules or {}).get("rules", []) or []
    for r in lst:
        m = (r.get("match") or "").strip()
        rx = r.get("match_regex")
        ok = False
        if m and _norm(plugin) == _norm(m):
            ok = True
        elif rx:
            try:
                ok = re.search(rx, plugin, re.IGNORECASE) is not None
            except Exception:
                ok = False
        if ok:
            return r
    return {}

def _pick_anchor_in_current_order(current_order: List[str], anchors: Set[str]) -> Optional[str]:
    if not anchors:
        return None
    anchor_set_ci = {a.lower(): a for a in anchors}
    for name in current_order:
        if name.lower() in anchor_set_ci:
            return name
    return None

def _partition_by_ext(order: List[str]) -> Dict[int, List[str]]:
    buckets = {0: [], 1: [], 2: [], 3: []}
    for n in order:
        buckets[_plugin_ext_rank(n)].append(n)
    return buckets

def _merge_buckets(bk: Dict[int, List[str]]) -> List[str]:
    return bk[0] + bk[1] + bk[2] + bk[3]

def _insert_relative_once(current_order: List[str],
                          plugin: str,
                          anchor: Optional[str],
                          position: str) -> List[str]:
    order = [n for n in current_order if n.strip().lower() != plugin.strip().lower()]
    pr = _plugin_ext_rank(plugin)
    bk = _partition_by_ext(order)
    tgt = bk.get(pr, [])
    if anchor:
        try:
            if _plugin_ext_rank(anchor) == pr:
                idx = next(i for i, n in enumerate(tgt) if n.strip().lower() == anchor.strip().lower())
                tgt.insert(idx if position.lower()=="before" else idx+1, plugin)
            else:
                tgt.append(plugin)
        except StopIteration:
            tgt.append(plugin)
    else:
        tgt.append(plugin)
    bk[pr] = tgt
    return _merge_buckets(bk)

# -------- synchro incrémentale --------

def sync_new_plugins_incremental(profile: str, mods_enabled_now: Set[str], rules: Dict) -> None:
    discovered: Set[str] = set()
    for mod in sorted(mods_enabled_now):
        for p in _discover_plugins_for_mod(mod):
            discovered.add(p)
    discovered = set(sorted(discovered, key=str.lower))

    lpath = loadorder_txt_path(profile)
    order = _read_loadorder_file(lpath)
    order_ci = {n.strip().lower() for n in order}

    new_plugins = [p for p in sorted(discovered, key=str.lower) if p.strip().lower() not in order_ci]
    _LOG.info("Incremental loadorder: %d new plugin(s) to place.", len(new_plugins))

    for p in new_plugins:
        order = _read_loadorder_file(lpath)
        names_now = order[:]

        r = _match_rule_for_plugin(p, rules or {})
        before = set()
        after  = set()
        if r:
            before |= _resolve_anchor_ci(r.get("before"), names_now, False)
            after  |= _resolve_anchor_ci(r.get("after"),  names_now, False)
            before |= _resolve_anchor_ci(r.get("before_regex"), names_now, True)
            after  |= _resolve_anchor_ci(r.get("after_regex"),  names_now, True)

        anchor = None
        pos = "end"
        if before:
            anc = _pick_anchor_in_current_order(names_now, before)
            if anc:
                anchor, pos = anc, "before"
        if anchor is None and after:
            anc = _pick_anchor_in_current_order(names_now, after)
            if anc:
                anchor, pos = anc, "after"

        new_order = _insert_relative_once(names_now, p, anchor, pos)
        _write_loadorder_file(lpath, new_order)
        _LOG.info("Inserted '%s' %s %s. New size=%d", p, ("before" if pos=="before" else ("after" if pos=="after" else "at end")), (anchor or "(end)"), len(new_order))

        try:
            _ensure_plugin_enabled(profile, p)
        except Exception as e:
            _LOG.error("Auto-activation in plugins.txt failed for '%s': %s", p, e)

    final_order = _read_loadorder_file(lpath)
    try:
        _ensure_all_enabled(profile, final_order)
    except Exception as e:
        _LOG.error("Batch activation in plugins.txt failed: %s", e)

    _LOG.info("loadorder.txt up-to-date. Total entries=%d", len(final_order))
