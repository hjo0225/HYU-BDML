"""데모 시드 서비스 (plan 0008).

로그인 없이 '데모 이용해보기'를 지원하기 위한 데모 전용 user/project 와
package 에이전트 6명 복제를 멱등(idempotent)하게 보장한다. 라우터(/api/demo/session)와
CLI(scripts/seed_demo.py)가 공유한다.

원본 에이전트(jeongoheo0225 프로젝트)는 손대지 않고 **복제**만 한다.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import Agent, AgentMemory, Conversation, FGISession, ResearchProject, User

# 고정 식별자 (멱등 시드)
DEMO_USER_ID = "0de00000-0000-4000-8000-000000000001"
DEMO_USER_EMAIL = "demo@mind-bridge.local"
DEMO_PROJECT_ID = "0de00000-0000-4000-8000-000000000002"
DEMO_PROJECT_TITLE = "포토이즘 재방문율 진단 (데모)"

# 복제 원본 — agent_package PoC 6명이 적재된 프로젝트 (env 로 override 가능)
SOURCE_PROJECT_ID = os.getenv("DEMO_SOURCE_PROJECT_ID", "61f78cf9-8329-4c24-912a-bd3eeac5bba8")

# 세션별 임시 데모 (plan 0016) — 방문마다 격리된 user/project 를 만들어 동시 접속 충돌 방지.
EPHEMERAL_EMAIL_PREFIX = "demo-"   # 고정 데모(demo@…)와 구분되는 임시 데모 이메일 접두어
EPHEMERAL_TTL_HOURS = int(os.getenv("DEMO_EPHEMERAL_TTL_HOURS", "24"))

# 복제할 Agent 컬럼 (id/project_id/타임스탬프 제외)
_AGENT_FIELDS = (
    "source_type", "source_ref", "display_name", "emoji", "intro_ko",
    "persona_params", "persona_full_prompt", "scratch", "responses",
    "avg_embedding", "cluster",
)
_MEMORY_FIELDS = ("source", "category", "text", "importance", "embedding", "meta_json")


async def _ensure_user(db: AsyncSession) -> User:
    res = await db.execute(select(User).where(User.id == DEMO_USER_ID))
    user = res.scalar_one_or_none()
    if user is None:
        # 이메일 충돌 방지 (다른 id 로 이미 있으면 그걸 사용)
        res2 = await db.execute(select(User).where(User.email == DEMO_USER_EMAIL))
        user = res2.scalar_one_or_none()
    if user is None:
        user = User(
            id=DEMO_USER_ID, email=DEMO_USER_EMAIL, hashed_pw=None,
            name="데모 사용자", role="demo", is_active=True,
        )
        db.add(user)
        await db.flush()
    return user


async def _ensure_project(db: AsyncSession, user_id: str) -> ResearchProject:
    res = await db.execute(select(ResearchProject).where(ResearchProject.id == DEMO_PROJECT_ID))
    project = res.scalar_one_or_none()
    if project is None:
        project = ResearchProject(
            id=DEMO_PROJECT_ID, user_id=user_id, title=DEMO_PROJECT_TITLE, status="active",
        )
        db.add(project)
        await db.flush()
    return project


async def _copy_agents(db: AsyncSession, target_project_id: str) -> int:
    """원본 프로젝트의 package 에이전트 + 6-Lens 메모리를 대상 프로젝트로 복제."""
    res = await db.execute(
        select(Agent).where(Agent.project_id == SOURCE_PROJECT_ID).order_by(Agent.created_at.asc())
    )
    sources = list(res.scalars().all())
    copied = 0
    for src in sources:
        new_id = str(uuid.uuid4())
        db.add(Agent(
            id=new_id, project_id=target_project_id,
            **{f: getattr(src, f) for f in _AGENT_FIELDS},
        ))
        # 6-Lens base 메모리 복제
        mres = await db.execute(select(AgentMemory).where(AgentMemory.agent_id == src.id))
        for mem in mres.scalars().all():
            db.add(AgentMemory(agent_id=new_id, **{f: getattr(mem, f) for f in _MEMORY_FIELDS}))
        copied += 1
    await db.flush()
    return copied


async def _reset(db: AsyncSession) -> None:
    """데모 프로젝트의 모든 하위 데이터 삭제 (SQLite ON DELETE 미보장 → 명시 삭제)."""
    agent_ids = (await db.execute(
        select(Agent.id).where(Agent.project_id == DEMO_PROJECT_ID)
    )).scalars().all()
    if agent_ids:
        await db.execute(delete(AgentMemory).where(AgentMemory.agent_id.in_(agent_ids)))
    await db.execute(delete(FGISession).where(FGISession.project_id == DEMO_PROJECT_ID))
    await db.execute(delete(Conversation).where(Conversation.project_id == DEMO_PROJECT_ID))
    await db.execute(delete(Agent).where(Agent.project_id == DEMO_PROJECT_ID))
    await db.flush()


async def ensure_demo(db: AsyncSession, *, reset: bool = False) -> dict:
    """데모 user/project/에이전트를 멱등 보장. (user, project, n_agents) 반환.

    reset=True 면 데모 프로젝트 하위 데이터(에이전트·대화·FGI)를 먼저 비운다.
    """
    user = await _ensure_user(db)
    project = await _ensure_project(db, user.id)

    if reset:
        await _reset(db)

    n = (await db.execute(
        select(func.count()).select_from(Agent).where(Agent.project_id == DEMO_PROJECT_ID)
    )).scalar_one()
    if n == 0:
        n = await _copy_agents(db, DEMO_PROJECT_ID)

    await db.commit()
    return {"user": user, "project": project, "n_agents": n}


# ── 세션별 임시 데모 (plan 0016) ─────────────────────────────────────────────

async def cleanup_stale_demos(db: AsyncSession, ttl_hours: int | None = None) -> int:
    """TTL 지난 임시 데모(user+project+하위 데이터)를 정리. 정리한 user 수 반환.

    고정 데모(demo@…)는 접두어가 달라 대상에서 제외된다. SQLite ON DELETE 미보장이라
    하위 데이터를 명시 삭제한다.
    """
    ttl = EPHEMERAL_TTL_HOURS if ttl_hours is None else ttl_hours
    cutoff = datetime.now(timezone.utc) - timedelta(hours=ttl)
    res = await db.execute(
        select(User).where(
            User.role == "demo",
            User.email.like(f"{EPHEMERAL_EMAIL_PREFIX}%@mind-bridge.local"),
            User.created_at < cutoff,
        )
    )
    stale = list(res.scalars().all())
    for u in stale:
        pids = (await db.execute(
            select(ResearchProject.id).where(ResearchProject.user_id == u.id)
        )).scalars().all()
        for pid in pids:
            aids = (await db.execute(select(Agent.id).where(Agent.project_id == pid))).scalars().all()
            if aids:
                await db.execute(delete(AgentMemory).where(AgentMemory.agent_id.in_(aids)))
            await db.execute(delete(FGISession).where(FGISession.project_id == pid))
            await db.execute(delete(Conversation).where(Conversation.project_id == pid))
            await db.execute(delete(Agent).where(Agent.project_id == pid))
            await db.execute(delete(ResearchProject).where(ResearchProject.id == pid))
        await db.execute(delete(User).where(User.id == u.id))
    await db.commit()
    return len(stale)


async def create_ephemeral_demo(db: AsyncSession) -> dict:
    """방문마다 격리된 데모 user+project 생성(에이전트 복제). (user, project_id, n_agents) 반환.

    동시 접속 시 서로의 대화·FGI·평가가 섞이지 않도록 세션마다 독립 스코프를 둔다.
    오래된 임시 데모는 best-effort 로 먼저 정리한다(정리 실패가 세션 생성을 막지 않음).
    """
    try:
        await cleanup_stale_demos(db)
    except Exception:  # noqa: BLE001
        await db.rollback()

    uid = str(uuid.uuid4())
    user = User(
        id=uid,
        email=f"{EPHEMERAL_EMAIL_PREFIX}{uid[:8]}@mind-bridge.local",
        hashed_pw=None, name="데모 사용자", role="demo", is_active=True,
    )
    db.add(user)
    await db.flush()   # FK 충족을 위해 user 를 먼저 적재
    project_id = str(uuid.uuid4())
    db.add(ResearchProject(
        id=project_id, user_id=uid, title=DEMO_PROJECT_TITLE, status="active",
        settings={"demo_ephemeral": True},
    ))
    await db.flush()
    n = await _copy_agents(db, project_id)
    await db.commit()
    return {"user": user, "project_id": project_id, "n_agents": n}
