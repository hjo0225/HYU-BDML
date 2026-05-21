"""research_projects.brief 컬럼 추가 — 프로젝트 의뢰서 (plan 0009 · item 4)

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-22

프로젝트 생성 시 입력받는 의뢰서(목적·타겟·활용방안)를 JSON 으로 저장한다.
이후 AI(설문 생성·FGI 모더레이터·라운드 질문 제안)의 판단 컨텍스트로 사용.
Cloud SQL(Postgres) ↔ 로컬 SQLite 양쪽 호환.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
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
    if not _has_column("research_projects", "brief"):
        op.add_column("research_projects", sa.Column("brief", json_type, nullable=True))


def downgrade() -> None:
    if _has_column("research_projects", "brief"):
        op.drop_column("research_projects", "brief")
