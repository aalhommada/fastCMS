"""
SQLAlchemy base configuration and metadata.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Naming convention for constraints (best practice for migrations)
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=convention)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    metadata = metadata

    def __repr__(self) -> str:
        """String representation of model."""
        columns = ", ".join(
            f"{col}={getattr(self, col)!r}"
            for col in self.__table__.columns.keys()
        )
        return f"<{self.__class__.__name__}({columns})>"
