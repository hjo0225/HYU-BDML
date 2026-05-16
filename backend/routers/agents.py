"""에이전트 목록·상세 라우터.

Slice 1.2 범위: GET /api/projects/{id}/agents, GET /api/agents/{id}.
seed-twin / 평가 / 대화·FGI 엔드포인트는 후속 Slice 에서 추가.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import Agent, ResearchProject, User, get_db
from models.schemas import AgentDetailOut, AgentOut
from services.agent_service import (
    _parse_jsonish,
    agent_passes_params_filter,
    parse_params_filter,
    short_summary,
)
from services.auth_service import get_current_user

router = APIRouter(tags=["agents"])


async def _verify_owned_project(project_id: str, user: User, db: AsyncSession) -> ResearchProject:
    result = await db.execute(
        select(ResearchProject).where(ResearchProject.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project or project.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="프로젝트를 찾을 수 없습니다.")
    return project


def _to_agent_out(agent: Agent) -> AgentOut:
    return AgentOut(
        id=agent.id,
        project_id=agent.project_id,
        source_type=agent.source_type,
        source_ref=agent.source_ref,
        display_name=agent.display_name,
        emoji=agent.emoji,
        intro_ko=agent.intro_ko,
        persona_params=_parse_jsonish(agent.persona_params),
        cluster=agent.cluster,
        summary=short_summary(agent),
        created_at=agent.created_at,
    )


def _to_agent_detail(agent: Agent) -> AgentDetailOut:
    return AgentDetailOut(
        id=agent.id,
        project_id=agent.project_id,
        source_type=agent.source_type,
        source_ref=agent.source_ref,
        display_name=agent.display_name,
        emoji=agent.emoji,
        intro_ko=agent.intro_ko,
        persona_params=_parse_jsonish(agent.persona_params),
        persona_full_prompt=agent.persona_full_prompt,
        scratch=_parse_jsonish(agent.scratch),
        cluster=agent.cluster,
        summary=short_summary(agent),
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


@router.get("/api/projects/{project_id}/agents", response_model=list[AgentOut])
async def list_project_agents(
    project_id: str,
    source_type: str | None = Query(default=None, pattern="^(twin|survey)$"),
    cluster: int | None = Query(default=None, ge=0),
    params: str | None = Query(
        default=None,
        description="6-Lens 범위 필터 (예: 'l1.risk_aversion:0.3-0.7,l2.maximization:3.0-5.0')",
    ),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """프로젝트 내 에이전트 카탈로그. source_type/cluster 는 DB 필터,
    persona_params 범위 필터는 SQLite 호환을 위해 ORM-side 후처리."""
    await _verify_owned_project(project_id, current_user, db)

    query = (
        select(Agent)
        .where(Agent.project_id == project_id)
        .order_by(Agent.created_at.asc())
    )
    if source_type:
        query = query.where(Agent.source_type == source_type)
    if cluster is not None:
        query = query.where(Agent.cluster == cluster)

    result = await db.execute(query)
    agents = list(result.scalars().all())

    ranges = parse_params_filter(params)
    if ranges:
        agents = [a for a in agents if agent_passes_params_filter(a, ranges)]

    return [_to_agent_out(a) for a in agents[offset : offset + limit]]


@router.get("/api/agents/{agent_id}", response_model=AgentDetailOut)
async def get_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """에이전트 상세 — persona_full_prompt + scratch 포함. 소속 프로젝트 소유권 검증."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="에이전트를 찾을 수 없습니다.")
    await _verify_owned_project(agent.project_id, current_user, db)
    return _to_agent_detail(agent)
