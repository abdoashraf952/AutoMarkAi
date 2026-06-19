"""
Memory & Checkpoint Management
Provides session-scoped memory that bridges LangGraph invocations.
Since LangGraph's built-in checkpointing requires async backends or
specific serde configurations, we implement a lightweight PostgreSQL-backed
state snapshot store using our existing SQLAlchemy layer.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Column, String, JSON, DateTime, Text
from sqlalchemy.orm import Session as DBSession

from app.database.models import Base
from app.database.connection import get_db


# ── ORM model for session snapshots ──────────────────────────────────────────

class SessionSnapshot(Base):
    """
    Stores a serialized snapshot of AnalyticsState for a given session.
    Used to restore context across Streamlit re-renders and LangGraph invocations.
    """
    __tablename__ = "session_snapshots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), nullable=False, index=True)
    snapshot_key = Column(String(256), nullable=False)  # e.g. "latest_analysis"
    state_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notes = Column(Text, nullable=True)


# ── Checkpoint manager ────────────────────────────────────────────────────────

class CheckpointManager:
    """
    Save and restore AnalyticsState snapshots to/from PostgreSQL.

    Usage:
        manager = CheckpointManager()
        manager.save(session_id, "latest", state_dict)
        restored = manager.load(session_id, "latest")
    """

    def save(
        self,
        session_id: str,
        key: str,
        state: dict[str, Any],
        notes: Optional[str] = None,
    ) -> None:
        """Upsert a state snapshot for the given session + key."""
        try:
            # Strip non-serializable items (DataFrames should never reach here)
            serializable = _make_serializable(state)
            with get_db() as db:
                existing = (
                    db.query(SessionSnapshot)
                    .filter_by(session_id=session_id, snapshot_key=key)
                    .first()
                )
                if existing:
                    existing.state_json = serializable
                    existing.updated_at = datetime.utcnow()
                    if notes:
                        existing.notes = notes
                else:
                    snap = SessionSnapshot(
                        session_id=session_id,
                        snapshot_key=key,
                        state_json=serializable,
                        notes=notes,
                    )
                    db.add(snap)
        except Exception as e:
            # Checkpoint failures are non-fatal — log and continue
            print(f"[CHECKPOINT] Save failed for session={session_id}, key={key}: {e}")

    def load(
        self,
        session_id: str,
        key: str,
    ) -> Optional[dict[str, Any]]:
        """Retrieve the most recent snapshot for the given session + key."""
        try:
            with get_db() as db:
                snap = (
                    db.query(SessionSnapshot)
                    .filter_by(session_id=session_id, snapshot_key=key)
                    .order_by(SessionSnapshot.updated_at.desc())
                    .first()
                )
                if snap:
                    return snap.state_json
        except Exception as e:
            print(f"[CHECKPOINT] Load failed for session={session_id}, key={key}: {e}")
        return None

    def list_keys(self, session_id: str) -> list[str]:
        """Return all snapshot keys for a given session."""
        try:
            with get_db() as db:
                snaps = (
                    db.query(SessionSnapshot.snapshot_key)
                    .filter_by(session_id=session_id)
                    .all()
                )
                return [s[0] for s in snaps]
        except Exception:
            return []

    def delete(self, session_id: str, key: str) -> None:
        """Delete a specific snapshot."""
        try:
            with get_db() as db:
                db.query(SessionSnapshot).filter_by(
                    session_id=session_id, snapshot_key=key
                ).delete()
        except Exception as e:
            print(f"[CHECKPOINT] Delete failed: {e}")

    def delete_session(self, session_id: str) -> None:
        """Delete all snapshots for a session (e.g., on session reset)."""
        try:
            with get_db() as db:
                db.query(SessionSnapshot).filter_by(session_id=session_id).delete()
        except Exception as e:
            print(f"[CHECKPOINT] Delete session failed: {e}")


# ── In-memory fallback cache (used when DB is unavailable) ───────────────────

class InMemoryCheckpointManager:
    """
    Fallback checkpoint manager that stores snapshots in a process-local dict.
    Data is lost on process restart, but allows the app to function without DB.
    """
    _store: dict[str, dict[str, Any]] = {}

    def save(self, session_id: str, key: str, state: dict, notes: Optional[str] = None) -> None:
        full_key = f"{session_id}::{key}"
        self._store[full_key] = _make_serializable(state)

    def load(self, session_id: str, key: str) -> Optional[dict]:
        full_key = f"{session_id}::{key}"
        return self._store.get(full_key)

    def list_keys(self, session_id: str) -> list[str]:
        prefix = f"{session_id}::"
        return [k.replace(prefix, "") for k in self._store if k.startswith(prefix)]

    def delete(self, session_id: str, key: str) -> None:
        self._store.pop(f"{session_id}::{key}", None)

    def delete_session(self, session_id: str) -> None:
        keys = [k for k in self._store if k.startswith(f"{session_id}::")]
        for k in keys:
            del self._store[k]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_serializable(obj: Any) -> Any:
    """Recursively ensure all values are JSON-serialisable."""
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_serializable(i) for i in obj]
    if hasattr(obj, "model_dump"):
        return _make_serializable(obj.model_dump())
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)


# ── Singleton factory ─────────────────────────────────────────────────────────

_checkpoint_manager: Optional[CheckpointManager | InMemoryCheckpointManager] = None


def get_checkpoint_manager(use_db: bool = True) -> CheckpointManager | InMemoryCheckpointManager:
    global _checkpoint_manager
    if _checkpoint_manager is None:
        if use_db:
            _checkpoint_manager = CheckpointManager()
        else:
            _checkpoint_manager = InMemoryCheckpointManager()
    return _checkpoint_manager
