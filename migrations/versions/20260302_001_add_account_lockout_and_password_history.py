"""Add account lockout fields and password history to users table

Revision ID: 20260302_001
Revises: add_2fa_fields
Create Date: 2026-03-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260302_001"
down_revision: Union[str, None] = "add_2fa_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add account lockout fields
    op.add_column("users", sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))
    # Add password history field (JSON array of previous hashes)
    op.add_column("users", sa.Column("password_history", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "password_history")
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_attempts")
