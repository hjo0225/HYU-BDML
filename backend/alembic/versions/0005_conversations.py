"""conversations / conversation_turns 테이블 추가 — 1:1 대화 (plan 0007)

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-21

사용자 ↔ 단일 에이전트 1:1 대화 세션과 발화 누적. citations/confidence 컬럼은
V1 인용 검증·신뢰도 마커용으로 두되 PoC 단계에서는 NULL.
Cloud SQL(Postgres) ↔ 로컬 SQLite 양쪽 호환.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels = None
depends_on = None


def _json_type(dialect: str):
    return sa.Text if dialect == "sqlite" else sa.JSON


def upgrade() -> None:
    bind = op.get_bind()
    json_type = _json_type(bind.dialect.name)

    if not _has_table("conversations"):
        op.create_table(
            "conversations",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("project_id", sa.String(36), sa.ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("agent_id", sa.String(36), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.String(200), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_conversations_project_id", "conversations", ["project_id"])
        op.create_index("ix_conversations_agent_id", "conversations", ["agent_id"])

    if not _has_table("conversation_turns"):
        op.create_table(
            "conversation_turns",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("conversation_id", sa.String(36), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("role", sa.String(20), nullable=False),
            sa.Column("content", sa.Text, nullable=False),
            sa.Column("citations", json_type, nullable=True),
            sa.Column("confidence", sa.String(20), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_conversation_turns_conversation_id", "conversation_turns", ["conversation_id"])
        op.create_index("ix_conversation_turns_conv_created", "conversation_turns", ["conversation_id", "created_at"])


def downgrade() -> None:
    if _has_table("conversation_turns"):
        op.drop_table("conversation_turns")
    if _has_table("conversations"):
        op.drop_table("conversations")


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)
