"""
CRM/config.py — thin redirect to the unified root config.

All modules in CRM/app/ that do `from config import settings` find this file
first when Python's working directory is CRM/. We forward to the root config.py
so settings are always loaded from the shared .env at the repo root.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

# Load root config.py explicitly to avoid shadowing by this file
_spec = importlib.util.spec_from_file_location("_root_config", Path(_root) / "config.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

settings = _mod.settings
Settings = _mod.Settings
