"""
Plugin settings model — key/value store for plugin configuration.
"""
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, String, Text, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PluginSetting(Base):
    """
    Stores plugin configuration as JSON-encoded key/value pairs.
    Composite primary key: (plugin_id, key).
    """

    __tablename__ = "plugin_settings"
    __table_args__ = (PrimaryKeyConstraint("plugin_id", "key"),)

    plugin_id: Mapped[str] = mapped_column(String(128), nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    def get_value(self) -> Any:
        """Deserialize JSON value."""
        return json.loads(self.value)

    def set_value(self, val: Any) -> None:
        """Serialize value to JSON."""
        self.value = json.dumps(val)
