"""Add plugin_settings table

Revision ID: 20260304_006
Revises: 20260302_005
Create Date: 2026-03-04

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260304_006"
down_revision: Union[str, None] = "20260302_005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plugin_settings",
        sa.Column("plugin_id", sa.String(128), nullable=False),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("value", sa.Text(), nullable=False, server_default="{}"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("plugin_id", "key", name="pk_plugin_settings"),
    )
    op.create_index("ix_plugin_settings_plugin_id", "plugin_settings", ["plugin_id"])


def downgrade() -> None:
    op.drop_index("ix_plugin_settings_plugin_id", table_name="plugin_settings")
    op.drop_table("plugin_settings")
