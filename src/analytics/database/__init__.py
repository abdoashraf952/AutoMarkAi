"""
src/analytics/database — analytics persistence.

Schema and engines now live in src/shared, so the whole project shares one
database and one init path. This package keeps only the analytics-specific
repository; `Base`, `get_db`, and `init_db` are re-exported from the shared
layer so existing analytics imports keep working unchanged.
"""

from src.shared.db import init_all_sync as init_db
from src.shared.db import sync_session as get_db
from src.shared.models import Base

from src.analytics.database.repository import AnalyticsRepository

__all__ = ["init_db", "get_db", "Base", "AnalyticsRepository"]
