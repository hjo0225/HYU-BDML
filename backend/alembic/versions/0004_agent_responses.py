"""agents.responses 컬럼 추가 — 234문항 raw 응답 보존

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-19

페르소나 프롬프트의 [BEHAVIORAL DATA] 섹션이 raw 응답을 시나리오로 텍스트화하므로
원본 응답을 영구 보존한다. 추후 LLM 모델 교체·자극 세트 확장 시 재빌드 가능.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels = None
depends_on = None


def _json_type(dialect: str):
    return sa.Text if dialect == "sqlite" else sa.JSON


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    json_type = _json_type(dialect)

    if _has_table("agents"):
        existing = _columns("agents")
        with op.batch_alter_table("agents") as batch_op:
            if "responses" not in existing:
                batch_op.add_column(sa.Column("responses", json_type, nullable=True))


def downgrade() -> None:
    if _has_table("agents"):
        existing = _columns("agents")
        with op.batch_alter_table("agents") as batch_op:
            if "responses" in existing:
                batch_op.drop_column("responses")


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    return sa.inspect(bind).has_table(name)


def _columns(table: str) -> set[str]:
    bind = op.get_bind()
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}
