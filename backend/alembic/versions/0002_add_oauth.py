"""users — oauth 컬럼 추가 + hashed_pw nullable

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-07
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("hashed_pw", nullable=True)
        batch_op.add_column(sa.Column("oauth_provider", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("oauth_id", sa.String(255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("oauth_id")
        batch_op.drop_column("oauth_provider")
        batch_op.alter_column("hashed_pw", nullable=False)
