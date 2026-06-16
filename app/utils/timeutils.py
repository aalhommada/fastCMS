"""Time helpers.

Single source of truth for "now". Returns a timezone-aware UTC datetime,
matching the `DateTime(timezone=True)` columns used across the models and
replacing the deprecated `datetime.utcnow()` (removed in Python 3.14).
"""

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)
