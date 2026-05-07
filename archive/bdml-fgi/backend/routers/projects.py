"""프로젝트 CRUD 라우터.

사용자가 진행한 연구 세션(프로젝트)을 DB에 영구 저장한다.
각 단계 완료 시 프론트엔드가 PATCH로 해당 필드를 업데이트한다.
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import Project, ProjectEdit, User, get_db
from services.auth_service import get_current_user
from services.project_service import generate_project_title

router = APIRouter(prefix="/api/projects", tags=["projects"])


# ── 헬퍼 ──────────────────────────────────────────────────────────────────

def _parse_jsonb(value: Any) -> Any:
    """SQLite에서 Text로 저장된 JSON을 dict로 파싱."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


def _dump_jsonb(value: Any) -> Any:
    """SQLite에서 dict를 Text로 저장하기 위해 직렬화."""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _project_to_dict(p: Project) -> dict:
    return {
        "id": p.id,
        "title": p.title,
        "current_phase": p.current_phase,
        "status": p.status,
        "brief": _parse_jsonb(p.brief),
        "refined": _parse_jsonb(p.refined),
        "market_report": _parse_jsonb(p.market_report),
        "agents": _parse_jsonb(p.agents),
        "meeting_topic": p.meeting_topic,
        "meeting_messages": _parse_jsonb(p.meeting_messages),
        "minutes": p.minutes,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


# ── 스키마 ─────────────────────────────────────────────────────────────────

class CreateProjectRequest(BaseModel):
    brief: dict  # ResearchBrief


class UpdateProjectRequest(BaseModel):
    """단계별 저장: 필요한 필드만 보낸다."""
    current_phase: int | None = None
    status: str | None = None
    title: str | None = None
    brief: dict | None = None
    refined: dict | None = None
    market_report: dict | None = None
    agents: list | None = None
    meeting_topic: str | None = None
    meeting_messages: list | None = None
    minutes: str | None = None


# ── 엔드포인트 ──────────────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_project(
    req: CreateProjectRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """새 프로젝트 생성. LLM이 브리프에서 한 줄 제목을 자동 생성한다."""
    # LLM 제목 생성 (실패 시 배경 앞 30자 사용)
    try:
        title = await generate_project_title(req.brief)
    except Exception:
        title = str(req.brief.get("background", "새 연구"))[:30]

    project = Project(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        title=title,
        brief=_dump_jsonb(req.brief),
        current_phase=1,
    )
    db.add(project)
    await db.flush()
    return _project_to_dict(project)


@router.get("")
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """내 프로젝트 목록 (최신순, 최대 50개)."""
    result = await db.execute(
        select(Project)
        .where(Project.user_id == current_user.id)
        .order_by(Project.updated_at.desc())
        .limit(50)
    )
    projects = result.scalars().all()
    # 목록에는 heavy한 필드(report, messages) 제외
    return [
        {
            "id": p.id,
            "title": p.title,
            "current_phase": p.current_phase,
            "status": p.status,
            "brief_summary": (
                _parse_jsonb(p.brief) or {}
            ).get("background", "")[:60] if p.brief else "",
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        }
        for p in projects
    ]


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """특정 프로젝트 전체 조회."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
    return _project_to_dict(project)


def _record_edits(
    edits: list,
    project_id: str,
    user_id: str,
    field: str,
    old_value: str | None,
    new_value: str | None,
) -> None:
    """변경이 있을 때만 편집 이력을 추가한다."""
    if old_value is None or old_value == new_value:
        return
    edits.append(
        ProjectEdit(
            project_id=project_id,
            user_id=user_id,
            field=field,
            old_value=old_value,
            new_value=new_value,
        )
    )


def _diff_refined(project_id: str, user_id: str, old: dict, new: dict) -> list[ProjectEdit]:
    """정제본 sub-field 변경 이력을 반환한다."""
    edits: list[ProjectEdit] = []
    for key in ("refined_background", "refined_objective", "refined_usage_plan"):
        _record_edits(edits, project_id, user_id, key, old.get(key), new.get(key))
    return edits


def _diff_agents(project_id: str, user_id: str, old_list: list, new_list: list) -> list[ProjectEdit]:
    """에이전트 추가·삭제·수정 이력을 반환한다."""
    edits: list[ProjectEdit] = []
    old_map = {a["id"]: a for a in old_list if isinstance(a, dict) and "id" in a}
    new_map = {a["id"]: a for a in new_list if isinstance(a, dict) and "id" in a}

    for aid, agent in new_map.items():
        if aid not in old_map:
            edits.append(ProjectEdit(
                project_id=project_id, user_id=user_id,
                field="agent_added",
                old_value=None,
                new_value=agent.get("name", aid),
            ))

    for aid, agent in old_map.items():
        if aid not in new_map:
            edits.append(ProjectEdit(
                project_id=project_id, user_id=user_id,
                field="agent_removed",
                old_value=agent.get("name", aid),
                new_value=None,
            ))

    for aid in old_map:
        if aid not in new_map:
            continue
        old_a, new_a = old_map[aid], new_map[aid]
        for key in ("name", "description"):
            _record_edits(edits, project_id, user_id,
                          f"agent_{key}",
                          str(old_a.get(key, "") or ""),
                          str(new_a.get(key, "") or ""))
        old_profile = json.dumps(old_a.get("persona_profile") or {}, ensure_ascii=False, sort_keys=True)
        new_profile = json.dumps(new_a.get("persona_profile") or {}, ensure_ascii=False, sort_keys=True)
        _record_edits(edits, project_id, user_id, "agent_persona", old_profile, new_profile)

    return edits


@router.patch("/{project_id}")
async def update_project(
    project_id: str,
    req: UpdateProjectRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """단계별 저장: 완료된 단계 데이터를 저장하고 current_phase를 올린다."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")

    # 편집 이력 수집
    edit_records: list[ProjectEdit] = []

    if req.refined is not None:
        old_refined = _parse_jsonb(project.refined) or {}
        if old_refined:  # AI 최초 저장본이 있을 때만 비교
            edit_records += _diff_refined(project_id, current_user.id, old_refined, req.refined)

    if req.agents is not None:
        old_agents = _parse_jsonb(project.agents) or []
        if old_agents:  # AI 추천본이 있을 때만 비교
            edit_records += _diff_agents(project_id, current_user.id, old_agents, req.agents)

    if req.meeting_topic is not None and project.meeting_topic:
        _record_edits(edit_records, project_id, current_user.id,
                      "meeting_topic", project.meeting_topic, req.meeting_topic)

    # 요청에서 None이 아닌 필드만 업데이트
    if req.current_phase is not None:
        project.current_phase = req.current_phase
    if req.status is not None:
        project.status = req.status
    if req.title is not None:
        project.title = req.title
    if req.brief is not None:
        project.brief = _dump_jsonb(req.brief)
    if req.refined is not None:
        project.refined = _dump_jsonb(req.refined)
    if req.market_report is not None:
        project.market_report = _dump_jsonb(req.market_report)
    if req.agents is not None:
        project.agents = _dump_jsonb(req.agents)
    if req.meeting_topic is not None:
        project.meeting_topic = req.meeting_topic
    if req.meeting_messages is not None:
        project.meeting_messages = _dump_jsonb(req.meeting_messages)
    if req.minutes is not None:
        project.minutes = req.minutes

    project.updated_at = datetime.now(timezone.utc)
    for record in edit_records:
        db.add(record)
    await db.flush()
    return _project_to_dict(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """프로젝트 삭제."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
    await db.delete(project)
