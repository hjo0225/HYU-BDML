"""initial — Ditto 기본 스키마

Revision ID: 0001
Revises:
Create Date: 2026-05-07
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: str | None = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # ── users ──────────────────────────────────────────────────────────────
    if not _table_exists("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("email", sa.String(254), nullable=False),
            sa.Column("hashed_pw", sa.Text, nullable=False),
            sa.Column("name", sa.String(100), nullable=True),
            sa.Column("role", sa.String(20), nullable=False, server_default="user"),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.func.now()),
        )
        op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── refresh_tokens ─────────────────────────────────────────────────────
    if not _table_exists("refresh_tokens"):
        op.create_table(
            "refresh_tokens",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36),
                      sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("is_revoked", sa.Boolean, nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.func.now()),
        )
        op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)

    # ── activity_logs ──────────────────────────────────────────────────────
    if not _table_exists("activity_logs"):
        op.create_table(
            "activity_logs",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.String(36),
                      sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("action", sa.String(50), nullable=False),
            sa.Column("model", sa.String(100), nullable=True),
            sa.Column("input_tokens", sa.Integer, nullable=False, server_default="0"),
            sa.Column("output_tokens", sa.Integer, nullable=False, server_default="0"),
            sa.Column("cost_usd", sa.Numeric(10, 6), nullable=False, server_default="0.0"),
            sa.Column("extra_json", sa.Text if dialect == "sqlite" else sa.JSON, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.func.now()),
        )

    # ── research_projects ──────────────────────────────────────────────────
    if not _table_exists("research_projects"):
        op.create_table(
            "research_projects",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36),
                      sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.String(200), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
            sa.Column("settings", sa.Text if dialect == "sqlite" else sa.JSON, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.func.now()),
        )
        op.create_index("ix_research_projects_user_id", "research_projects", ["user_id"])

    # ── agents ─────────────────────────────────────────────────────────────
    if not _table_exists("agents"):
        op.create_table(
            "agents",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("project_id", sa.String(36),
                      sa.ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_type", sa.String(20), nullable=False),
            sa.Column("source_ref", sa.String(50), nullable=True),
            sa.Column("persona_params", sa.Text if dialect == "sqlite" else sa.JSON, nullable=True),
            sa.Column("persona_full_prompt", sa.Text, nullable=True),
            sa.Column("avg_embedding", sa.Text if dialect == "sqlite" else sa.JSON, nullable=True),
            sa.Column("cluster", sa.Integer, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.func.now()),
        )
        op.create_index("ix_agents_project_id", "agents", ["project_id"])

    # ── agent_memories ─────────────────────────────────────────────────────
    if not _table_exists("agent_memories"):
        op.create_table(
            "agent_memories",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("agent_id", sa.String(36),
                      sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source", sa.String(20), nullable=False, server_default="base"),
            sa.Column("category", sa.String(50), nullable=False),
            sa.Column("text", sa.Text, nullable=False),
            sa.Column("importance", sa.Integer, nullable=False, server_default="50"),
            sa.Column("embedding", sa.Text if dialect == "sqlite" else sa.JSON, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.func.now()),
        )
        op.create_index("ix_agent_memories_agent_id", "agent_memories", ["agent_id"])

    # ── evaluation_snapshots ───────────────────────────────────────────────
    if not _table_exists("evaluation_snapshots"):
        op.create_table(
            "evaluation_snapshots",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("agent_id", sa.String(36),
                      sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
            sa.Column("version", sa.Integer, nullable=False, server_default="1"),
            sa.Column("identity_stats", sa.Text if dialect == "sqlite" else sa.JSON, nullable=True),
            sa.Column("logic_stats", sa.Text if dialect == "sqlite" else sa.JSON, nullable=True),
            sa.Column("verdict", sa.String(50), nullable=True),
            sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.func.now()),
        )
        op.create_index("ix_evaluation_snapshots_agent_id", "evaluation_snapshots", ["agent_id"])


def downgrade() -> None:
    for table in ["evaluation_snapshots", "agent_memories", "agents",
                  "research_projects", "activity_logs", "refresh_tokens", "users"]:
        if _table_exists(table):
            op.drop_table(table)


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    return sa.inspect(bind).has_table(name)
