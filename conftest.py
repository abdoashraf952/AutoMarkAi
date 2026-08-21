"""
Root pytest configuration.

Puts the repo root on sys.path so every test can `from src.… import …`
regardless of the directory pytest was invoked from. This replaces the
per-module sys.path shims the three projects each carried before the merge.
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
