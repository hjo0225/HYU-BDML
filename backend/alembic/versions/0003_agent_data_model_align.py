"""agents/agent_memories/evaluation_snapshots — DATA_MODEL.md 정합

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-16

DATA_MODEL.md (SSOT) 와 ORM 간 누락된 컬럼을 보강한다.
- agents: display_name, emoji, intro_ko, scratch, updated_at
- agent_memories: metadata (ORM 어트리뷰트는 meta_json)
- evaluation_snapshots: eval_config

SQLite/PostgreSQL 양쪽 호환을 위해 batch_alter_table 을 사용.
JSONB 타입은 SQLite 에서 Text 로 폴백한다.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels = None
depends_on = None


def _json_type(dialect: str):
    """SQLite = Text, PostgreSQL = JSON."""
    return sa.Text if dialect == "sqlite" else sa.JSON


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    json_type = _json_type(dialect)

    # ── agents ─────────────────────────────────────────────────────────────
    if _has_table("agents"):
        existing = _columns("agents")
        with op.batch_alter_table("agents") as batch_op:
            if "display_name" not in existing:
                batch_op.add_column(sa.Column("display_name", sa.String(100), nullable=True))
            if "emoji" not in existing:
                batch_op.add_column(sa.Column("emoji", sa.String(8), nullable=True))
            if "intro_ko" not in existing:
                batch_op.add_column(sa.Column("intro_ko", sa.Text, nullable=True))
            if "scratch" not in existing:
                batch_op.add_column(sa.Column("scratch", json_type, nullable=True))
            if "updated_at" not in existing:
                batch_op.add_column(sa.Column(
                    "updated_at",
                    sa.DateTime(timezone=True),
                    nullable=False,
                    server_default=sa.func.now(),
                ))

    # ── agent_memories ─────────────────────────────────────────────────────
    if _has_table("agent_memories"):
        existing = _columns("agent_memories")
        with op.batch_alter_table("agent_memories") as batch_op:
            if "metadata" not in existing:
                batch_op.add_column(sa.Column("metadata", json_type, nullable=True))

    # ── evaluation_snapshots ───────────────────────────────────────────────
    if _has_table("evaluation_snapshots"):
        existing = _columns("evaluation_snapshots")
        with op.batch_alter_table("evaluation_snapshots") as batch_op:
            if "eval_config" not in existing:
                batch_op.add_column(sa.Column("eval_config", json_type, nullable=True))


def downgrade() -> None:
    if _has_table("evaluation_snapshots"):
        with op.batch_alter_table("evaluation_snapshots") as batch_op:
            if "eval_config" in _columns("evaluation_snapshots"):
                batch_op.drop_column("eval_config")

    if _has_table("agent_memories"):
        with op.batch_alter_table("agent_memories") as batch_op:
            if "metadata" in _columns("agent_memories"):
                batch_op.drop_column("metadata")

    if _has_table("agents"):
        existing = _columns("agents")
        with op.batch_alter_table("agents") as batch_op:
            for col in ("updated_at", "scratch", "intro_ko", "emoji", "display_name"):
                if col in existing:
                    batch_op.drop_column(col)


# ── helpers ────────────────────────────────────────────────────────────────

def _has_table(name: str) -> bool:
    bind = op.get_bind()
    return sa.inspect(bind).has_table(name)


def _columns(table: str) -> set[str]:
    bind = op.get_bind()
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}
