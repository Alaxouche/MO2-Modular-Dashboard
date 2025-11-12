# -*- coding: utf-8 -*-
import re
from typing import Dict, List, Tuple, Optional

_RX_RES      = re.compile(r"^\s*(\d+)\s*x\s*(\d+)\s*$", re.IGNORECASE)
_RX_SECTION  = re.compile(r"^(\s*\[.*?\]\s*)$", re.MULTILINE)
_RX_RENDER   = re.compile(r"^\s*\[Render\]\s*$", re.MULTILINE)
_RX_KEY_TPL  = r"^\s*[#;]?\s*{key}\s*="

enabled_cache: Dict[Tuple[str, float], List[str]] = {}
rules_cache: Dict[str, Optional[float] or Dict] = {"mtime": None, "data": None}
