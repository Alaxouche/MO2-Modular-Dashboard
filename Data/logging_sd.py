# -*- coding: utf-8 -*-
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

class _SDLogger:
    def __init__(self):
        self.log = logging.getLogger("StartupDashboard")
        self.log.setLevel(logging.DEBUG)
        try:
            logs_dir = Path(__file__).resolve().parent.parent / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            fh = RotatingFileHandler(
                logs_dir / "StartupDashboard.log",
                encoding="utf-8",
                mode="a",
                maxBytes=1_000_000,
                backupCount=3
            )
            fmt = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
            fh.setFormatter(fmt)
            if not self.log.handlers:
                self.log.addHandler(fh)
        except Exception:
            if not self.log.handlers:
                self.log.addHandler(logging.StreamHandler(sys.stderr))

_LOG = _SDLogger().log
