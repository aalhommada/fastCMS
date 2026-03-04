"""Add token_type and new_email columns to verification_tokens table

Revision ID: 20260302_002
Revises: 20260302_001
Create Date: 2026-03-02

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260302_002"
down_revision: Union[str, None] = "20260302_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add token_type to differentiate verification vs email_change vs otp tokens
    op.add_column(
        "verification_tokens",
        sa.Column("token_type", sa.String(30), nullable=False, server_default="email_verification"),
    )
    # Add new_email for email change flow
    op.add_column(
        "verification_tokens",
        sa.Column("new_email", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("verification_tokens", "new_email")
    op.drop_column("verification_tokens", "token_type")
