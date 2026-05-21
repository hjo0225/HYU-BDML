"""fgi_sessions.plan 컬럼 추가 — 라운드 플랜 확정본 (plan 0010)

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-22

FGI 시작 전 "라운드별 질문 AI 제안"으로 확정한 라운드 플랜
([{round, subtopic, goal_question}])을 세션에 저장한다. 진행 엔진은 이 플랜을
그대로 토론 라운드로 사용한다(미지정 시에만 자체 플랜 생성).
Cloud SQL(Postgres) ↔ 로컬 SQLite 양쪽 호환.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels = None
depends_on = None


def _json_type(dialect: str):
    return sa.Text if dialect == "sqlite" else sa.JSON


def _has_column(table: str, column: str) -> bool:
    insp = sa.inspect(op.get_bind())
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    json_type = _json_type(bind.dialect.name)
    if not _has_column("fgi_sessions", "plan"):
        op.add_column("fgi_sessions", sa.Column("plan", json_type, nullable=True))


def downgrade() -> None:
    if _has_column("fgi_sessions", "plan"):
        op.drop_column("fgi_sessions", "plan")
