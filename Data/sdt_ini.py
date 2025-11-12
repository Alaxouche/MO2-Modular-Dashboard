# -*- coding: utf-8 -*-
from pathlib import Path
from typing import Dict, Optional, Tuple

from .logging_sd import _LOG
from .files import read_text, atomic_write
from .regex_cache import _RX_SECTION, _RX_RENDER, _RX_KEY_TPL
from .mo2_helpers import overwrite_dir, mo2_mods_dir, enabled_mod_names

_SD_DEFAULT_INI = """[Render]
# Written by StartupDashboard — minimal section if no base INI was found.
Fullscreen = false
Borderless = true
Resolution = 1920x1080
ResolutionScale = 1
"""

def _find_sdt_base_ini(profile: str) -> Optional[Path]:
    for mod in reversed(enabled_mod_names(profile)):
        p = mo2_mods_dir() / mod / "SKSE" / "Plugins" / "SSEDisplayTweaks.ini"
        if p.exists():
            return p
    return None

def _patch_ini_render_keys(ini_text: str, kv: Dict[str, str]) -> str:
    import re
    if _RX_RENDER.search(ini_text) is None:
        if ini_text and not ini_text.endswith("\n"):
            ini_text += "\n"
        ini_text += "[Render]\n"

    parts = _RX_SECTION.split(ini_text)
    out_parts = []
    in_render = False

    rx_by_key = {k: re.compile(_RX_KEY_TPL.format(key=re.escape(k)), re.IGNORECASE) for k in kv}
    for chunk in parts:
        if _RX_SECTION.match(chunk or ""):
            in_render = _RX_RENDER.match(chunk or "") is not None
            out_parts.append(chunk)
            continue

        if in_render:
            lines = chunk.splitlines(True)
            found = {k: False for k in kv}
            new_lines = []
            for ln in lines:
                replaced = False
                for k, rx in rx_by_key.items():
                    if rx.match(ln):
                        new_lines.append(f"{k} = {kv[k]}\n")
                        found[k] = True
                        replaced = True
                        break
                if not replaced:
                    new_lines.append(ln)
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines[-1] = new_lines[-1] + "\n"
            for k, ok in found.items():
                if not ok:
                    new_lines.append(f"{k} = {kv[k]}\n")
            out_parts.append("".join(new_lines))
        else:
            out_parts.append(chunk)

    return "".join(out_parts)

def compose_sdt_text_for(res_text: str, profile: str) -> Tuple[str, Optional[str]]:
    base_ini = _find_sdt_base_ini(profile)
    if base_ini:
        base_text = read_text(base_ini)
        _LOG.info(f"SDT base INI found in enabled mod: {base_ini}")
    else:
        base_text = _SD_DEFAULT_INI
        _LOG.info("No SDT base INI found; using minimal default.")

    final_text = _patch_ini_render_keys(base_text, {
        "Fullscreen":      "false",
        "Borderless":      "true",
        "Resolution":      res_text,
        "ResolutionScale": "1",
    })
    return final_text, (base_text if base_ini else None)

def apply_resolution_to_sdt(res_text: str, profile: str) -> Path:
    ini_text, _ = compose_sdt_text_for(res_text, profile)
    target = overwrite_dir() / "SKSE" / "Plugins" / "SSEDisplayTweaks.ini"
    atomic_write(target, ini_text)
    _LOG.info(f"SSEDisplayTweaks.ini written to Overwrite: {target}")
    return target
