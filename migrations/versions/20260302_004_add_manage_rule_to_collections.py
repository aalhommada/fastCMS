"""Add manage_rule column to collections table

Revision ID: 20260302_004
Revises: 20260302_003
Create Date: 2026-03-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260302_004"
down_revision: Union[str, None] = "20260302_003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "collections",
        sa.Column("manage_rule", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("collections", "manage_rule")
