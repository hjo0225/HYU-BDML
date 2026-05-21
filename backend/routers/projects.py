"""ResearchProject CRUD 라우터.

소유자(user_id)만 접근 가능. 본인이 아닌 project_id 접근 시 404 반환
(403 대신 404 — 리소스 존재 자체를 노출하지 않기 위함).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import Agent, ResearchProject, User, get_db
from models.schemas import (
    ResearchProjectCreate,
    ResearchProjectOut,
    ResearchProjectUpdate,
)
from services.auth_service import get_current_user

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _ensure_not_demo(user: User) -> None:
    """공용 데모 계정(role='demo')은 사전 시드 프로젝트만 소비 — 변경 차단 (plan 0009).

    모든 데모 방문자가 단일 데모 계정을 공유하므로, 생성·수정·삭제를 막아
    공유 데이터 오염과 프로젝트 누적을 방지한다.
    """
    if user.role == "demo":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="데모에서는 프로젝트를 만들거나 변경할 수 없습니다. 회원가입 후 이용하세요.",
        )


async def _load_owned(project_id: str, user: User, db: AsyncSession) -> ResearchProject:
    """본인 소유 프로젝트 로드. 없거나 타인 소유면 404."""
    result = await db.execute(
        select(ResearchProject).where(ResearchProject.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project or project.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="프로젝트를 찾을 수 없습니다.")
    return project


async def _agent_count(project_id: str, db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count(Agent.id)).where(Agent.project_id == project_id)
    )
    return int(result.scalar_one() or 0)


def _to_out(project: ResearchProject, agent_count: int) -> ResearchProjectOut:
    return ResearchProjectOut(
        id=project.id,
        user_id=project.user_id,
        title=project.title,
        status=project.status,
        brief=project.brief,
        created_at=project.created_at,
        updated_at=project.updated_at,
        agent_count=agent_count,
    )


@router.get("", response_model=list[ResearchProjectOut])
async def list_projects(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status", pattern="^(draft|active|archived)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """본인 프로젝트 목록. 최신 updated_at 내림차순."""
    query = (
        select(ResearchProject)
        .where(ResearchProject.user_id == current_user.id)
        .order_by(ResearchProject.updated_at.desc(), ResearchProject.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if status_filter:
        query = query.where(ResearchProject.status == status_filter)
    result = await db.execute(query)
    projects = list(result.scalars().all())

    if not projects:
        return []

    # 프로젝트별 agent count 집계 (1 쿼리)
    count_rows = await db.execute(
        select(Agent.project_id, func.count(Agent.id))
        .where(Agent.project_id.in_([p.id for p in projects]))
        .group_by(Agent.project_id)
    )
    counts = {row[0]: int(row[1]) for row in count_rows.all()}
    return [_to_out(p, counts.get(p.id, 0)) for p in projects]


@router.post("", response_model=ResearchProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    req: ResearchProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """프로젝트 생성. title 미입력 시 'YYYY-MM-DD 프로젝트' 자동 생성.

    brief(목적·타겟·활용방안)는 입력값이 하나라도 있을 때만 JSON 으로 저장.
    """
    _ensure_not_demo(current_user)
    title = (req.title or f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')} 프로젝트").strip()
    brief_dict = None
    if req.brief:
        d = req.brief.model_dump()
        if any(v for v in d.values()):
            brief_dict = d
    project = ResearchProject(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        title=title,
        status="draft",
        brief=brief_dict,
    )
    db.add(project)
    await db.flush()
    return _to_out(project, agent_count=0)


@router.get("/{project_id}", response_model=ResearchProjectOut)
async def get_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """프로젝트 단건 조회."""
    project = await _load_owned(project_id, current_user, db)
    count = await _agent_count(project_id, db)
    return _to_out(project, count)


@router.patch("/{project_id}", response_model=ResearchProjectOut)
async def update_project(
    project_id: str,
    req: ResearchProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """프로젝트 부분 갱신. 전달된 필드만 반영."""
    _ensure_not_demo(current_user)
    project = await _load_owned(project_id, current_user, db)
    payload = req.model_dump(exclude_unset=True)
    if not payload:
        raise HTTPException(status_code=400, detail="갱신할 필드가 없습니다.")
    for k, v in payload.items():
        setattr(project, k, v)
    await db.flush()
    count = await _agent_count(project_id, db)
    return _to_out(project, count)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """프로젝트 삭제. agents/agent_memories 는 ondelete=CASCADE 로 연쇄 삭제."""
    _ensure_not_demo(current_user)
    project = await _load_owned(project_id, current_user, db)
    await db.execute(delete(ResearchProject).where(ResearchProject.id == project.id))
