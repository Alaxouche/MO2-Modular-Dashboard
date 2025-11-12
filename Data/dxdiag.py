# -*- coding: utf-8 -*-
import os
import json
import ctypes
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from .logging_sd import _LOG

DXDIAG_XML_PATH = os.path.join(os.getenv("TEMP", "."), "dxdiag_output.xml")

def _safe_float(s: str, default: float) -> float:
    try:
        return float(str(s).strip())
    except Exception:
        return default

def dxdiag_max_wddm() -> float:
    cache = Path(__file__).resolve().parent.parent / "dxdiag_cache.json"
    try:
        if cache.exists():
            data = json.loads(cache.read_text(encoding="utf-8"))
            return float(data.get("max_wddm", 0.0))
    except Exception:
        pass

    try:
        subprocess.run(["dxdiag", "/x", DXDIAG_XML_PATH], capture_output=True, text=True, timeout=30)
        tree = ET.parse(DXDIAG_XML_PATH)
        root = tree.getroot()
        max_wddm = 0.0
        for device in root.findall(".//DisplayDevices/DisplayDevice"):
            driver_model = (device.findtext("DriverModel", "") or "").strip()
            if "WDDM" in driver_model:
                try:
                    ver = _safe_float(driver_model.replace("WDDM", "").strip(), 0.0)
                    max_wddm = max(max_wddm, ver)
                except Exception:
                    pass
        try:
            cache.write_text(json.dumps({"max_wddm": max_wddm}, indent=2), encoding="utf-8")
        except Exception:
            pass
        try:
            Path(DXDIAG_XML_PATH).unlink(missing_ok=True)
        except Exception:
            pass
        return max_wddm
    except Exception as e:
        _LOG.error(f"dxdiag WDDM detection failed: {e}")
        return 0.0

def monitor_count() -> int:
    try:
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        return int(user32.GetSystemMetrics(80))
    except Exception as e:
        _LOG.debug(f"Monitor count detection failed: {e}")
        return 1

def is_dlss_capable(min_wddm: float) -> bool:
    wddm = dxdiag_max_wddm()
    capable = (wddm >= min_wddm)
    _LOG.info(f"DLSS auto-check → WDDM={wddm:.2f} (min {min_wddm:.2f}) → {'capable' if capable else 'not capable'}")
    return capable

# Thread worker (Qt import local pour éviter dépendance globale)
def DxdiagWorkerFactory(min_wddm: float):
    try:
        from PyQt6.QtCore import QThread, pyqtSignal
    except Exception:
        from PyQt5.QtCore import QThread, pyqtSignal

    class DxdiagWorker(QThread):
        done = pyqtSignal(float)
        def __init__(self, min_wddm: float, parent=None):
            super().__init__(parent)
            self.min_wddm = min_wddm
        def run(self):
            self.done.emit(dxdiag_max_wddm())

    return DxdiagWorker(min_wddm)
