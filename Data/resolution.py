# -*- coding: utf-8 -*-
import re
from typing import Dict, List, Optional, Tuple

from .logging_sd import _LOG

_RX_RES = re.compile(r"^\s*(\d+)\s*x\s*(\d+)\s*$", re.IGNORECASE)

RESOLUTIONS_BY_RATIO: Dict[str, List[str]] = {
    "16:9":  ["1280x720", "1600x900", "1920x1080", "2560x1440", "3200x1800", "3840x2160", "5120x2880", "7680x4320"],
    "16:10": ["1280x800", "1440x900", "1680x1050", "1920x1200", "2560x1600", "3840x2400"],
    "21:9":  ["2560x1080", "3440x1440", "3840x1600", "5120x2160"],
    "32:9":  ["3840x1080", "5120x1440", "7680x2160"],
    "3:2":   ["2160x1440", "2256x1504", "2496x1664", "2736x1824", "3000x2000", "3240x2160"],
    "4:3":   ["1024x768", "1280x960", "1600x1200", "2048x1536"],
    "5:4":   ["1280x1024", "2560x2048"],
}

def bucket_from_resolution(res_text: str) -> str:
    m = _RX_RES.match(res_text or "")
    if not m:
        return "1080p"
    h = int(m.group(2))
    if h < 800:    return "720p"
    if h < 1000:   return "900p"
    if h < 1140:   return "1080p"
    if h < 1300:   return "1200p"
    if h < 1500:   return "1440p"
    if h < 2000:   return "1600p"
    if h < 2400:   return "4K"
    if h < 3000:   return "5K"
    return "8K"

def detect_primary_resolution() -> Tuple[int, int]:
    """
    Retourne la résolution *totale* de l'écran principal, sans retrancher la barre des tâches.
    Préfère QScreen.geometry() à availableGeometry(). Fallback robuste en cas d'erreur.
    """
    try:
        try:
            from PyQt6.QtWidgets import QApplication
        except Exception:
            from PyQt5.QtWidgets import QApplication
        import sys

        app = QApplication.instance() or QApplication(sys.argv)
        screen = app.primaryScreen()
        # Géométrie complète de l'écran (inclut les zones système)
        full_geo = screen.geometry()
        w, h = int(full_geo.width()), int(full_geo.height())

        # Optionnel: si Qt fournit aussi availableGeometry, on ignore sa hauteur
        # mais on garde le plus grand des deux au cas où.
        try:
            avail = screen.availableGeometry()
            w = max(w, int(avail.width()))
            h = max(h, int(avail.height()))
        except Exception:
            pass

        # Sécurités: valeurs minimales raisonnables
        if w <= 0 or h <= 0:
            return 1920, 1080
        return w, h
    except Exception as e:
        from .logging_sd import _LOG
        _LOG.warning(f"Primary resolution detect failed: {e}")
        return 1920, 1080


def normalize_ratio(w: int, h: int, tolerance: float = 0.02) -> str:
    if w <= 0 or h <= 0:
        return "16:9"
    r = w / h
    candidates = {
        "16:9": 16/9,
        "16:10": 16/10,
        "21:9": 21/9,
        "32:9": 32/9,
        "3:2":  3/2,
        "4:3":  4/3,
        "5:4":  5/4,
    }
    best, best_diff = "16:9", 999.0
    for key, val in candidates.items():
        diff = abs(r - val) / val
        if diff < best_diff:
            best, best_diff = key, diff
    return best if best_diff <= tolerance else "16:9"

def nearest_in_list(target_wh: Tuple[int, int], options: List[str]) -> Optional[str]:
    tw, th = target_wh
    t_area = tw * th
    best, best_d = None, None
    for opt in options:
        m = _RX_RES.match(opt or "")
        if not m:
            continue
        ow, oh = int(m.group(1)), int(m.group(2))
        d = abs(ow * oh - t_area)
        if best_d is None or d < best_d:
            best, best_d = opt, d
    return best
