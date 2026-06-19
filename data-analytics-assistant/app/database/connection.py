"""Database connection and session management."""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

from app.database.models import Base

_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://analytics_user:analytics_pass@localhost:5432/analytics_db")

engine = create_engine(
    _DATABASE_URL,
    poolclass=NullPool,
    echo=os.getenv("DEBUG", "false").lower() == "true",
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Context manager that yields a database session and handles cleanup."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
