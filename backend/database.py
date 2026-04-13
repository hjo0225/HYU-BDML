"""데이터베이스 엔진, 세션, ORM 모델 정의.

DATABASE_URL 환경변수로 로컬(aiosqlite)과 배포(asyncpg/Cloud SQL) 자동 전환.
"""
# database.py
import os
from datetime import datetime, timezone
from typing import AsyncGenerator

from sqlalchemy import (
    BigInteger, Boolean, Column, Float, ForeignKey, Integer,
    Numeric, String, Text, DateTime,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func


# ── 환경 변수 ──────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./app.db",  # 로컬 기본값
)

# ── 엔진 ──────────────────────────────────────────────────────────────────
_engine_kwargs: dict = {"echo": False}
if DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_async_engine(DATABASE_URL, **_engine_kwargs)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


# ── Base ──────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── 헬퍼: SQLite / PostgreSQL 타입 분기 ──────────────────────────────────
def _uuid_col(primary_key: bool = False, nullable: bool = False, **kw):
    """SQLite는 String, PostgreSQL은 UUID 타입 사용."""
    if DATABASE_URL.startswith("sqlite"):
        return Column(String(36), primary_key=primary_key, nullable=nullable, **kw)
    return Column(UUID(as_uuid=False), primary_key=primary_key, nullable=nullable, **kw)


def _jsonb_col(nullable: bool = True):
    """SQLite는 Text, PostgreSQL은 JSONB 사용."""
    if DATABASE_URL.startswith("sqlite"):
        return Column(Text, nullable=nullable)
    return Column(JSONB, nullable=nullable)


def _now():
    return datetime.now(timezone.utc)


# ── ORM 모델 ──────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id         = Column(String(36), primary_key=True)
    email      = Column(String(254), unique=True, nullable=False, index=True)
    hashed_pw  = Column(Text, nullable=False)
    name       = Column(String(100), nullable=True)
    role       = Column(String(20), nullable=False, default="user")   # 'user' | 'admin'
    is_active  = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id         = Column(String(36), primary_key=True)
    user_id    = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(64), unique=True, nullable=False)  # SHA-256
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_revoked = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)


class Project(Base):
    __tablename__ = "projects"

    id               = Column(String(36), primary_key=True)
    user_id          = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title            = Column(String(200), nullable=True)          # LLM 자동 생성
    current_phase    = Column(Integer, nullable=False, default=1)
    status           = Column(String(20), nullable=False, default="draft")  # 'draft' | 'completed'

    # Phase 1 – 연구 브리프
    brief            = _jsonb_col()

    # Phase 2 – 정제본 + 시장조사
    refined          = _jsonb_col()
    market_report    = _jsonb_col()

    # Phase 3 – 에이전트/페르소나
    agents           = _jsonb_col()

    # Phase 4 – 회의
    meeting_topic    = Column(Text, nullable=True)
    meeting_messages = _jsonb_col()

    # Phase 5 – 회의록
    minutes          = Column(Text, nullable=True)

    created_at       = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at       = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class ProjectEdit(Base):
    """사용자가 AI 생성 결과를 수정한 이력."""
    __tablename__ = "project_edits"

    id         = Column(BigInteger, primary_key=True, autoincrement=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id    = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    field      = Column(String(100), nullable=False)   # 'refined_background' | 'agent_added' 등
    old_value  = Column(Text, nullable=True)
    new_value  = Column(Text, nullable=True)
    edited_at  = Column(DateTime(timezone=True), nullable=False, default=_now)


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id            = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id       = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    project_id    = Column(String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    action        = Column(String(50), nullable=False)   # 'research' | 'agents' | 'meeting' | 'minutes'
    model         = Column(String(100), nullable=True)
    input_tokens  = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    cost_usd      = Column(Numeric(10, 6), nullable=False, default=0.0)
    extra_json    = _jsonb_col()
    created_at    = Column(DateTime(timezone=True), nullable=False, default=_now)


# ── 패널 데이터 (RAG) ─────────────────────────────────────────────────────

class Panel(Base):
    """500명 FGI 패널 — 사전 적재된 인구통계 + 행동 차원."""
    __tablename__ = "panels"

    panel_id        = Column(String(20), primary_key=True)
    cluster         = Column(Integer, nullable=False)

    # 인구통계 (디코딩 완료된 값)
    age             = Column(Integer, nullable=True)
    gender          = Column(String(10), nullable=True)
    occupation      = Column(String(50), nullable=True)
    region          = Column(String(50), nullable=True)

    # 행동 차원 (0-1 비율, 클러스터링/필터링용)
    dim_night_owl       = Column(Float, nullable=True)
    dim_gamer           = Column(Float, nullable=True)
    dim_social_diner    = Column(Float, nullable=True)
    dim_drinker         = Column(Float, nullable=True)
    dim_shopper         = Column(Float, nullable=True)
    dim_health          = Column(Float, nullable=True)
    dim_entertainment   = Column(Float, nullable=True)
    dim_weekend_oriented = Column(Float, nullable=True)

    # 사전 계산된 scratch (전체 인구통계 dict)
    scratch         = _jsonb_col(nullable=False)

    # 메모리 임베딩 평균 벡터 (1536차원, 패널 선정 스코어링용)
    avg_embedding   = _jsonb_col(nullable=True)


class PanelMemory(Base):
    """패널별 카테고리 메모리 — 임베딩 포함."""
    __tablename__ = "panel_memories"

    id          = Column(BigInteger, primary_key=True, autoincrement=True)
    panel_id    = Column(String(20), ForeignKey("panels.panel_id", ondelete="CASCADE"),
                         nullable=False, index=True)
    category    = Column(String(50), nullable=False)
    text        = Column(Text, nullable=False)
    importance  = Column(Integer, nullable=False, default=50)
    embedding   = _jsonb_col(nullable=False)   # list[float] 1536차원


# ── 세션 Dependency ────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── 테이블 생성 (개발용 / Alembic 없을 때) ────────────────────────────────

async def init_db() -> None:
    import subprocess
    import sys
    import asyncio

    # Cloud SQL 소켓 준비 대기 (최대 30초)
    for attempt in range(6):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(lambda c: None)  # 연결 테스트
            break
        except Exception as e:
            print(f"[DB] 연결 대기 중... ({attempt+1}/6): {e}")
            await asyncio.sleep(5)
    else:
        raise RuntimeError("[DB] Cloud SQL 연결 실패: 소켓을 찾을 수 없습니다.")

    alembic_ini = os.path.join(os.path.dirname(__file__), "alembic.ini")
    if os.path.exists(alembic_ini):
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=os.path.dirname(__file__),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"[DB] Alembic 마이그레이션 실패:\n{result.stderr}")
        else:
            print("[DB] Alembic 마이그레이션 완료")
        return

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("[DB] 테이블 자동 생성 완료 (create_all)")
    except Exception as e:
        # 이미 테이블이 존재하는 경우 (Cloud SQL에서 타입 충돌 가능)
        print(f"[DB] create_all 건너뜀 (테이블이 이미 존재할 수 있음): {e}")