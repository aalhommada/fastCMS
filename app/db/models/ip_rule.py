"""IP allowlist/blocklist rules."""
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import BaseModel


class IPRule(BaseModel):
    """Stores IP allow/block rules (supports CIDR notation)."""

    __tablename__ = "ip_rules"

    # CIDR range or single IP, e.g. "192.168.1.0/24" or "10.0.0.1"
    cidr: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # "allow" or "block"
    rule_type: Mapped[str] = mapped_column(String(10), nullable=False)

    # Human-readable reason
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Optional expiry (None = permanent)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Admin who created the rule
    created_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
