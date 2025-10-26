"""
Collection model for storing collection metadata.
Collections define the schema for dynamic tables.
"""

from typing import Any, Dict, List, Literal

from sqlalchemy import JSON, Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import BaseModel


class Collection(BaseModel):
    """
    Collection model storing metadata for dynamic collections.

    A collection defines:
    - Schema (fields and their types)
    - Type (base, auth, view)
    - Access control rules
    - Validation options
    """

    __tablename__ = "collections"

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="base",
    )

    # JSON field storing the complete schema
    schema: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    # JSON field for collection options
    options: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    # Access control rules (stored as text for complex expressions)
    list_rule: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        default=None,
    )

    view_rule: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        default=None,
    )

    create_rule: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        default=None,
    )

    update_rule: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        default=None,
    )

    delete_rule: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        default=None,
    )

    # System collection flag (cannot be deleted)
    system: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<Collection(name={self.name}, type={self.type})>"
