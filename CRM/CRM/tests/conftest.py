"""
tests/conftest.py — AutoMark AI CRM Agent (ORCAST)

Ensures tests always run with CWD = CRM/CRM so relative paths
(e.g. knowledge_base/) resolve correctly regardless of where pytest
is invoked from.  config.py already resolves .env via __file__ so
no manual dotenv loading is needed here.
"""

import os
from pathlib import Path

# Change CWD to the project root (CRM/CRM) before any imports.
os.chdir(Path(__file__).parent.parent)
