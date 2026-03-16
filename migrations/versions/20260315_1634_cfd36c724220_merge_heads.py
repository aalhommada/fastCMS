"""merge_heads

Revision ID: cfd36c724220
Revises: 1662d73b2d81, 20260314_007
Create Date: 2026-03-15 16:34:40.733972

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "cfd36c724220"
down_revision: Union[str, None] = ("1662d73b2d81", "20260314_007")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    pass


def downgrade() -> None:
    """Downgrade database schema."""
    pass
