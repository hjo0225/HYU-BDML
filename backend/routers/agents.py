"""에이전트 목록·상세·적재 라우터.

Slice 1.2: GET /api/projects/{id}/agents, GET /api/agents/{id}.
Slice 1.4: POST /api/projects/{id}/agents/seed-twin (NDJSON 진행 스트림).
Plan 0023: GET /api/agents/{id}/holdout — 사전계산된 홀드아웃 유사도 결과 반환.
평가 / 대화·FGI 엔드포인트는 후속 Slice 에서 추가.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import Agent, ResearchProject, User, get_db
from models.schemas import AgentDetailOut, AgentOut
from services.agent_service import (
    _parse_jsonish,
    agent_passes_params_filter,
    demographics,
    parse_params_filter,
    short_summary,
)
from services.auth_service import get_current_user
from services.seed_service import process_record, recluster_project

# 홀드아웃 유사도 사전계산 캐시 위치 (plan 0023)
# 파일 캐시는 로컬 개발용 폴백. 배포(Cloud Run)는 파일시스템이 ephemeral 이라
# 결과를 agents.scratch['holdout_eval'] (Cloud SQL) 에 영구 저장하고 그걸 1차로 읽는다.
_HOLDOUT_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "holdout_eval"
_HOLDOUT_SCRATCH_KEY = "holdout_eval"


def _scratch_holdout(agent: Agent) -> dict | None:
    """agent.scratch['holdout_eval'] 를 안전하게 dict 로 추출. 없으면 None."""
    scratch = _parse_jsonish(agent.scratch) if agent.scratch else None
    if not isinstance(scratch, dict):
        return None
    data = scratch.get(_HOLDOUT_SCRATCH_KEY)
    return data if isinstance(data, dict) else None

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
    age_range, gender = demographics(agent)
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
        age_range=age_range,
        gender=gender,
        summary=short_summary(agent),
        created_at=agent.created_at,
    )


def _to_agent_detail(agent: Agent) -> AgentDetailOut:
    age_range, gender = demographics(agent)
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
        age_range=age_range,
        gender=gender,
        summary=short_summary(agent),
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


@router.get("/api/projects/{project_id}/agents", response_model=list[AgentOut])
async def list_project_agents(
    project_id: str,
    source_type: str | None = Query(default=None, pattern="^(twin|survey|package)$"),
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


# ── 홀드아웃 유사도 (plan 0023) ───────────────────────────────────────────

@router.get("/api/agents/{agent_id}/holdout")
async def get_agent_holdout(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """사전계산된 홀드아웃 유사도 결과 JSON 반환.

    조회 순서 (배포 영속성 우선):
      1) DB — agent.scratch['holdout_eval'] (원본/이미 평가된 에이전트)
      2) DB — 같은 source_ref 를 가진 에이전트의 scratch 폴백
      3~4) 로컬 파일 캐시 (개발용 폴백, 배포에선 비어 있음)

    데모 세션의 임시 에이전트는 source(원본) 에이전트의 결과를 source_ref(pid) 로
    fallback 조회한다 — 데모 복제본은 매번 새 id 라 직접 적중이 안 되기 때문.

    404 = 사전계산 결과 없음 (scripts/run_holdout_eval.py 또는 load_holdout_to_db.py 실행 필요).
    """
    res = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = res.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="에이전트를 찾을 수 없습니다.")
    await _verify_owned_project(agent.project_id, current_user, db)

    # 1) DB 직접 매칭 — 본인 scratch 에 저장된 결과
    own = _scratch_holdout(agent)
    if own is not None:
        return own

    # 2) DB source_ref 폴백 — 데모 복제본은 새 id 라 같은 source_ref 의 원본 결과를 share.
    #    created_at 오름차순 → 가장 먼저 적재된 원본(데모 소스)이 우선.
    if agent.source_ref:
        cand_res = await db.execute(
            select(Agent)
            .where(Agent.source_ref == agent.source_ref, Agent.id != agent.id)
            .order_by(Agent.created_at.asc())
        )
        for cand in cand_res.scalars().all():
            data = _scratch_holdout(cand)
            if data is not None:
                # 클라이언트 입장에서는 이 에이전트의 결과로 보이게 id 만 갱신
                data = {**data, "agent_id": agent.id}
                return data

    # 3) 로컬 파일 직접 매칭 (개발용 폴백)
    direct = _HOLDOUT_CACHE_DIR / f"{agent.id}.json"
    if direct.exists():
        return json.loads(direct.read_text(encoding="utf-8"))

    # 4) 로컬 파일 source_ref 폴백 (개발용 폴백)
    if agent.source_ref:
        for cand_path in _HOLDOUT_CACHE_DIR.glob("*.json"):
            try:
                data = json.loads(cand_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if data.get("agent_source_ref") == agent.source_ref:
                data["agent_id"] = agent.id
                return data

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="홀드아웃 평가가 아직 실행되지 않았습니다. (scripts/run_holdout_eval.py 실행 필요)",
    )


# ── seed-twin ─────────────────────────────────────────────────────────────

class SeedTwinRequest(BaseModel):
    """Twin-2K-500 적재 요청.

    fixture 미지정 시 backend/tests/_fixtures/mock_twin_30.json 사용 (mock 단계).
    실데이터 도착 시 fixture 만 갈아끼우면 됨.
    """
    limit: int = Field(default=30, ge=1, le=500)
    cluster_k: int = Field(default=5, ge=2, le=20)
    fixture: str | None = None  # 절대경로 또는 backend/ 기준 상대경로
    synthetic_embeddings: bool | None = None  # None=자동, True/False=강제


def _default_fixture_path() -> Path:
    return Path(__file__).resolve().parent.parent / "tests" / "_fixtures" / "mock_twin_30.json"


def _resolve_fixture(req_fixture: str | None) -> Path:
    if not req_fixture:
        return _default_fixture_path()
    p = Path(req_fixture)
    if not p.is_absolute():
        p = Path(__file__).resolve().parent.parent / req_fixture
    return p


async def _stream_seed(
    project_id: str,
    req: SeedTwinRequest,
) -> AsyncGenerator[bytes, None]:
    """NDJSON 진행 스트림 생성기."""
    def emit(payload: dict) -> bytes:
        return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")

    fixture_path = _resolve_fixture(req.fixture)
    if not fixture_path.exists():
        yield emit({"type": "error", "reason": f"fixture 없음: {fixture_path}"})
        return

    try:
        records = json.loads(fixture_path.read_text(encoding="utf-8"))
    except Exception as e:
        yield emit({"type": "error", "reason": f"fixture 로드 실패: {e}"})
        return

    if isinstance(records, dict):
        records = [records]
    records = records[: req.limit]
    total = len(records)
    yield emit({"type": "start", "total": total, "fixture": fixture_path.name})

    created = 0
    for i, record in enumerate(records, start=1):
        try:
            result = await process_record(
                record,
                project_id=project_id,
                synthetic_embeddings=req.synthetic_embeddings,
            )
            created += 1
            yield emit({
                "type": "progress",
                "current": i,
                "total": total,
                "agent_id": result.get("agent_id"),
                "respondent_id": result.get("respondent_id"),
                "display_name": result.get("display_name"),
            })
        except Exception as e:
            yield emit({
                "type": "error",
                "respondent_id": record.get("respondent_id", f"idx_{i}"),
                "reason": str(e),
            })

    if created >= 2:
        k = await recluster_project(project_id, k=req.cluster_k)
        yield emit({"type": "cluster_done", "k": k})

    yield emit({"type": "done", "total_created": created})


@router.post("/api/projects/{project_id}/agents/seed-twin")
async def seed_twin(
    project_id: str,
    req: SeedTwinRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Twin-2K-500 30명을 프로젝트에 적재. NDJSON 진행 스트림.

    mock 단계에서는 backend/tests/_fixtures/mock_twin_30.json 사용.
    fixture 만 갈아끼우면 실데이터 적재로 전환.
    """
    await _verify_owned_project(project_id, current_user, db)
    request = req or SeedTwinRequest()
    return StreamingResponse(
        _stream_seed(project_id, request),
        media_type="application/x-ndjson",
        # 프록시(Cloud Run/nginx)가 응답을 버퍼링해 진행 상황이 한꺼번에 나오는 것을 방지.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
