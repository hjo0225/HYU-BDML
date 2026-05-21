"""fgi_sessions / fgi_turns 테이블 추가 — 정식 FGI 엔진 (plan 0008)

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-21

다자 회의 세션과 발화 누적 (모더레이터 / 에이전트 / 사용자 개입). 종료 시
인사이트 보고서를 minutes_md(Markdown)로 저장한다.
Cloud SQL(Postgres) ↔ 로컬 SQLite 양쪽 호환.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels = None
depends_on = None


def _json_type(dialect: str):
    return sa.Text if dialect == "sqlite" else sa.JSON


def upgrade() -> None:
    bind = op.get_bind()
    json_type = _json_type(bind.dialect.name)

    if not _has_table("fgi_sessions"):
        op.create_table(
            "fgi_sessions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("project_id", sa.String(36), sa.ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("topic", sa.Text, nullable=False),
            sa.Column("agent_ids", json_type, nullable=False),
            sa.Column("max_rounds", sa.Integer, nullable=False, server_default="6"),
            sa.Column("allow_user_intervention", sa.Boolean, nullable=False, server_default=sa.true()),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("minutes_md", sa.Text, nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_fgi_sessions_project_id", "fgi_sessions", ["project_id"])

    if not _has_table("fgi_turns"):
        op.create_table(
            "fgi_turns",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("session_id", sa.String(36), sa.ForeignKey("fgi_sessions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("round", sa.Integer, nullable=False),
            sa.Column("order_in_round", sa.Integer, nullable=False),
            sa.Column("role", sa.String(20), nullable=False),
            sa.Column("agent_id", sa.String(36), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=True),
            sa.Column("content", sa.Text, nullable=False),
            sa.Column("meta_json", json_type, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_fgi_turns_session_id", "fgi_turns", ["session_id"])
        op.create_index("ix_fgi_turns_session_round_order", "fgi_turns", ["session_id", "round", "order_in_round"])


def downgrade() -> None:
    if _has_table("fgi_turns"):
        op.drop_table("fgi_turns")
    if _has_table("fgi_sessions"):
        op.drop_table("fgi_sessions")


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)
