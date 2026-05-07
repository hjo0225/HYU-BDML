"""데이터베이스 엔진, 세션, ORM 모델 정의.

DATABASE_URL 환경변수로 로컬(aiosqlite)과 배포(asyncpg/Cloud SQL) 자동 전환.
SQLite 에서는 JSONB → Text, vector → Text(JSON) 폴백.
"""
import json
import os
from datetime import datetime, timezone
from typing import AsyncGenerator

from sqlalchemy import (
    BigInteger, Boolean, Column, Float, ForeignKey,
    Integer, Numeric, String, Text, DateTime,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./app.db")

_engine_kwargs: dict = {"echo": False}
if DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_async_engine(DATABASE_URL, **_engine_kwargs)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# ── 타입 헬퍼 ─────────────────────────────────────────────────────────────

def _uuid_col(primary_key: bool = False, nullable: bool = False, **kw):
    """SQLite = String(36), PostgreSQL = UUID."""
    if DATABASE_URL.startswith("sqlite"):
        return Column(String(36), primary_key=primary_key, nullable=nullable, **kw)
    return Column(UUID(as_uuid=False), primary_key=primary_key, nullable=nullable, **kw)


def _jsonb_col(nullable: bool = True):
    """SQLite = Text, PostgreSQL = JSONB."""
    if DATABASE_URL.startswith("sqlite"):
        return Column(Text, nullable=nullable)
    return Column(JSONB, nullable=nullable)


def _now():
    return datetime.now(timezone.utc)


# ── 인증 모델 ─────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id             = Column(String(36), primary_key=True)
    email          = Column(String(254), unique=True, nullable=False, index=True)
    hashed_pw      = Column(Text, nullable=True)          # Google OAuth 사용자는 null
    name           = Column(String(100), nullable=True)
    role           = Column(String(20), nullable=False, default="user")
    is_active      = Column(Boolean, nullable=False, default=True)
    oauth_provider = Column(String(20), nullable=True)    # 'google' | None
    oauth_id       = Column(String(255), nullable=True)   # Google sub
    created_at     = Column(DateTime(timezone=True), nullable=False, default=_now)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id         = Column(String(36), primary_key=True)
    user_id    = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(64), unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_revoked = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id            = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id       = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action        = Column(String(50), nullable=False)
    model         = Column(String(100), nullable=True)
    input_tokens  = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    cost_usd      = Column(Numeric(10, 6), nullable=False, default=0.0)
    extra_json    = _jsonb_col()
    created_at    = Column(DateTime(timezone=True), nullable=False, default=_now)


# ── Ditto 도메인 모델 ─────────────────────────────────────────────────────

class ResearchProject(Base):
    """Ditto 리서치 프로젝트 — 에이전트·대화·FGI의 컨테이너."""
    __tablename__ = "research_projects"

    id         = Column(String(36), primary_key=True)
    user_id    = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title      = Column(String(200), nullable=True)
    status     = Column(String(20), nullable=False, default="draft")  # 'draft' | 'active' | 'archived'
    settings   = _jsonb_col()  # 프로젝트 설정 (평가 파라미터 등)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class Agent(Base):
    """Ditto 에이전트 — Twin 데이터 또는 사용자 Survey 응답 기반."""
    __tablename__ = "agents"

    id                  = Column(String(36), primary_key=True)
    project_id          = Column(String(36), ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type         = Column(String(20), nullable=False)  # 'twin' | 'survey'
    source_ref          = Column(String(50), nullable=True)   # 원본 respondent_id
    persona_params      = _jsonb_col(nullable=True)           # L1~L6 + ability 수치 결과
    persona_full_prompt = Column(Text, nullable=True)         # 합성된 시스템 프롬프트 (<= 8k tokens)
    avg_embedding       = _jsonb_col(nullable=True)           # 메모리 임베딩 평균 (1536차원 list)
    cluster             = Column(Integer, nullable=True)      # KMeans 클러스터 ID
    created_at          = Column(DateTime(timezone=True), nullable=False, default=_now)


class AgentMemory(Base):
    """에이전트 메모리 — 기본(base), 대화 누적(conversation), FGI(fgi)."""
    __tablename__ = "agent_memories"

    id         = Column(BigInteger, primary_key=True, autoincrement=True)
    agent_id   = Column(String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    source     = Column(String(20), nullable=False, default="base")  # 'base' | 'conversation' | 'fgi'
    category   = Column(String(50), nullable=False)   # 6-Lens 카테고리 (예: 'l1_economic')
    text       = Column(Text, nullable=False)
    importance = Column(Integer, nullable=False, default=50)  # 0~100
    embedding  = _jsonb_col(nullable=False)                   # list[float] 1536차원
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)


class EvaluationSnapshot(Base):
    """에이전트 성능 평가 스냅샷 — V1~V5 점수 시계열."""
    __tablename__ = "evaluation_snapshots"

    id             = Column(String(36), primary_key=True)
    agent_id       = Column(String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    version        = Column(Integer, nullable=False, default=1)
    identity_stats = _jsonb_col()   # V1(sync), V2(stability), V3(diversity)
    logic_stats    = _jsonb_col()   # V4(humanity), V5(reasoning_delta)
    verdict        = Column(String(50), nullable=True)   # 예: 'Verified (S3 Entry)'
    evaluated_at   = Column(DateTime(timezone=True), nullable=False, default=_now)


# ── 세션 Dependency ───────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── 테이블 초기화 ─────────────────────────────────────────────────────────

async def init_db() -> None:
    """앱 시작 시 Alembic 마이그레이션 또는 create_all 실행."""
    import subprocess
    import sys
    import asyncio

    # Cloud SQL 소켓 준비 대기 (최대 30초)
    for attempt in range(6):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(lambda c: None)
            break
        except Exception as e:
            print(f"[DB] 연결 대기 중... ({attempt+1}/6): {e}")
            await asyncio.sleep(5)
    else:
        raise RuntimeError("[DB] DB 연결 실패.")

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

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[DB] 테이블 자동 생성 완료 (create_all)")
