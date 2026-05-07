import asyncio
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import Base, DATABASE_URL  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _make_sync_url(url: str) -> str:
    """비동기 드라이버 prefix → 동기 prefix 변환 (offline mode용)."""
    return (
        url.replace("sqlite+aiosqlite", "sqlite")
           .replace("postgresql+asyncpg", "postgresql+psycopg2")
    )


def run_migrations_offline() -> None:
    url = DATABASE_URL
    context.configure(
        url=_make_sync_url(url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=url.startswith("sqlite"),  # SQLite ALTER TABLE 우회
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=DATABASE_URL.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_async_engine(DATABASE_URL, poolclass=pool.NullPool)
    async with connectable.connect() as conn:
        await conn.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
