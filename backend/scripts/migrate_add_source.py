"""1회성 마이그레이션 — `panels` / `panel_memories`에 `source` 컬럼 추가.

CLAUDE.md / docs/DATA_MODEL.md의 source 분리 규칙 도입 시 한 번만 실행한다.

- 멱등(idempotent): 컬럼이 이미 있으면 건너뜀.
- 기존 행은 'fgi500'으로 백필.
- PostgreSQL(Cloud SQL)과 SQLite 양쪽 호환.

실행:
    cd backend && python -m scripts.migrate_add_source
"""
from __future__ import annotations

import asyncio
import os

# .env 파일을 모듈 import 전에 로드해야 database.py의 DATABASE_URL이 올바르게 잡힌다.
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except ImportError:
    pass  # 환경변수가 이미 셸에 export 돼 있으면 무시

from sqlalchemy import text

from database import engine, DATABASE_URL


IS_SQLITE = DATABASE_URL.startswith("sqlite")


async def _column_exists(conn, table: str, column: str) -> bool:
    if IS_SQLITE:
        rows = (await conn.execute(text(f"PRAGMA table_info({table})"))).fetchall()
        return any(r[1] == column for r in rows)
    # PostgreSQL
    sql = text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = :t AND column_name = :c"
    )
    result = (await conn.execute(sql, {"t": table, "c": column})).first()
    return result is not None


async def _add_source(conn, table: str) -> None:
    if await _column_exists(conn, table, "source"):
        print(f"[migrate] {table}.source 이미 존재 — 건너뜀")
        return

    print(f"[migrate] {table}.source 추가 중...")
    await conn.execute(
        text(
            f"ALTER TABLE {table} "
            f"ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'fgi500'"
        )
    )
    # 기존 행 백필 (DEFAULT가 새 행에만 적용되는 DB 대비)
    await conn.execute(
        text(f"UPDATE {table} SET source = 'fgi500' WHERE source IS NULL")
    )
    # 인덱스 추가 (PostgreSQL — SQLite는 ALTER TABLE의 DEFAULT만으로 충분)
    if not IS_SQLITE:
        await conn.execute(
            text(f"CREATE INDEX IF NOT EXISTS ix_{table}_source ON {table} (source)")
        )
    print(f"[migrate] {table}.source 추가 완료")


async def main() -> None:
    print(f"[migrate] DATABASE_URL={DATABASE_URL[:40]}...")
    async with engine.begin() as conn:
        await _add_source(conn, "panels")
        await _add_source(conn, "panel_memories")
    print("[migrate] 완료")


if __name__ == "__main__":
    asyncio.run(main())
