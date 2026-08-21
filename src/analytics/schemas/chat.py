"""Chat message schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    message_type: str = "text"  # "text" | "analysis" | "kpi" | "insight"
    metadata: Optional[dict] = None
