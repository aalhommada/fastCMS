"""Add ip_rules table

Revision ID: 20260302_005
Revises: 20260302_004
Create Date: 2026-03-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260302_005"
down_revision: Union[str, None] = "20260302_004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ip_rules",
        sa.Column("id", sa.String(36), nullable=False, primary_key=True),
        sa.Column("cidr", sa.String(50), nullable=False, index=True),
        sa.Column("rule_type", sa.String(10), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created", sa.DateTime(), nullable=False),
        sa.Column("updated", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ip_rules")
