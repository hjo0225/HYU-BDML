"""FGI(다자 회의) 라우터 — plan 0008.

POST  /api/projects/{project_id}/fgi-sessions   세션 생성
POST  /api/fgi-sessions/{session_id}/run        SSE 진행 (모더레이터·에이전트·개입)
POST  /api/fgi-sessions/{session_id}/intervene  사용자 개입 발언
GET   /api/fgi-sessions/{session_id}            세션 메타 + 전체 turn (+ minutes_md)

SSE 이벤트(api-spec.md): round_start / moderator / agent_delta / agent_end /
user_turn_required / round_end / session_end / error
"""
from __future__ import annotations

import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import (
    Agent,
    AsyncSessionLocal,
    FGISession,
    FGITurn,
    ResearchProject,
    User,
    get_db,
)
from fgi import engine
from fgi.round_suggest import suggest_rounds
from models.schemas import (
    CreateFGIRequest,
    FGIControlRequest,
    FGISessionDetailOut,
    FGISessionOut,
    FGITurnOut,
    InterveneRequest,
    SuggestRoundsRequest,
    SuggestRoundsResponse,
)
from services.agent_service import _parse_jsonish
from services.auth_service import get_current_user

router = APIRouter(tags=["fgi"])


async def _verify_owned_project(project_id: str, user: User, db: AsyncSession) -> ResearchProject:
    res = await db.execute(select(ResearchProject).where(ResearchProject.id == project_id))
    project = res.scalar_one_or_none()
    if not project or project.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="프로젝트를 찾을 수 없습니다.")
    return project


async def _load_session(session_id: str, db: AsyncSession) -> FGISession:
    res = await db.execute(select(FGISession).where(FGISession.id == session_id))
    sess = res.scalar_one_or_none()
    if not sess:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FGI 세션을 찾을 수 없습니다.")
    return sess


async def _load_agents_ordered(project_id: str, agent_ids: list[str], db: AsyncSession) -> list[Agent]:
    res = await db.execute(
        select(Agent).where(Agent.id.in_(agent_ids), Agent.project_id == project_id)
    )
    by_id = {a.id: a for a in res.scalars().all()}
    missing = [aid for aid in agent_ids if aid not in by_id]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"프로젝트에 속하지 않은 에이전트가 있습니다: {missing}",
        )
    return [by_id[aid] for aid in agent_ids]  # 요청 순서 보존


@router.post(
    "/api/projects/{project_id}/fgi-sessions",
    response_model=FGISessionOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_fgi_session(
    project_id: str,
    body: CreateFGIRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """FGI 세션 생성 (status='running'). 진행은 /run 에서 시작.

    rounds(확정된 라운드별 질문 제안)가 곧 토론 플랜이 된다. 라운드 수는 그 길이로 결정.
    """
    await _verify_owned_project(project_id, current_user, db)
    await _load_agents_ordered(project_id, body.agent_ids, db)  # 소속 검증

    plan = [r.model_dump() for r in body.rounds]
    sess = FGISession(
        id=str(uuid.uuid4()),
        project_id=project_id,
        user_id=current_user.id,
        topic=body.topic,
        agent_ids=body.agent_ids,
        plan=plan,
        max_rounds=len(plan),
        allow_user_intervention=body.allow_user_intervention,
        status="running",
    )
    db.add(sess)
    await db.flush()
    return FGISessionOut.model_validate(sess)


@router.post(
    "/api/projects/{project_id}/fgi-sessions/suggest-rounds",
    response_model=SuggestRoundsResponse,
)
async def suggest_fgi_rounds(
    project_id: str,
    body: SuggestRoundsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """회의 주제 → 라운드별 소주제·핵심 질문 제안 (plan 0009 · item 6).

    프로젝트 의뢰서(brief)를 컨텍스트로 사용. 세션을 만들지 않는 미리보기성 호출.
    """
    project = await _verify_owned_project(project_id, current_user, db)
    brief = _parse_jsonish(getattr(project, "brief", None))
    rounds = await suggest_rounds(topic=body.topic, n_rounds=body.n_rounds, brief=brief)
    return SuggestRoundsResponse(rounds=rounds)


@router.post("/api/fgi-sessions/{session_id}/run")
async def run_fgi_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """FGI 진행을 SSE 로 스트리밍. 진행 파라미터는 세션 생성 시 값을 사용한다.

    스트림 제너레이터는 자체 DB 세션을 연다 (요청 의존성 세션은 응답 시작 시 닫힘).
    소유권·에이전트 로드는 의존성 세션으로 먼저 끝낸다.
    """
    sess = await _load_session(session_id, db)
    await _verify_owned_project(sess.project_id, current_user, db)
    if sess.status != "running":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 종료된 세션입니다.")
    agents = await _load_agents_ordered(sess.project_id, list(sess.agent_ids), db)
    sess_id = sess.id
    agent_ids = list(sess.agent_ids)
    max_rounds = sess.max_rounds
    allow_user_intervention = sess.allow_user_intervention
    plan = list(sess.plan) if sess.plan else None

    async def event_stream() -> AsyncGenerator[bytes, None]:
        def sse(payload: dict) -> bytes:
            return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")

        async with AsyncSessionLocal() as stream_db:
            # 스트림 세션에서 ORM 객체를 다시 로드 (의존성 세션과 분리)
            res = await stream_db.execute(select(FGISession).where(FGISession.id == sess_id))
            stream_sess = res.scalar_one()
            res2 = await stream_db.execute(select(Agent).where(Agent.id.in_(agent_ids)))
            by_id = {a.id: a for a in res2.scalars().all()}
            ordered = [by_id[aid] for aid in agent_ids]
            try:
                async for ev in engine.run_fgi(
                    stream_db, session=stream_sess, agents=ordered,
                    max_rounds=max_rounds, allow_user_intervention=allow_user_intervention,
                    plan=plan,
                ):
                    yield sse(ev)
            except Exception as e:  # noqa: BLE001
                yield sse({"type": "error", "reason": str(e)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/api/fgi-sessions/{session_id}/intervene")
async def intervene(
    session_id: str,
    body: InterveneRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """user_turn_required 구간에서 사용자 개입 발언 삽입."""
    sess = await _load_session(session_id, db)
    await _verify_owned_project(sess.project_id, current_user, db)

    waiter = engine.get_waiter(session_id)
    if waiter is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="지금은 개입할 수 없습니다 (개입 가능 구간이 아님).",
        )

    turn = FGITurn(
        id=str(uuid.uuid4()),
        session_id=session_id,
        round=waiter.round,
        order_in_round=waiter.order,
        role="user",
        content=body.content,
        meta_json={"display_name": "기업 관계자"},
    )
    db.add(turn)
    await db.commit()

    waiter.queue.put_nowait(body.content)
    return {"ok": True, "turn_id": turn.id}


@router.post("/api/fgi-sessions/{session_id}/skip-intervention")
async def skip_intervention(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """사용자가 '개입 안 함'을 선택 — 대기 중인 개입 창을 즉시 닫고 다음 라운드로 진행."""
    sess = await _load_session(session_id, db)
    await _verify_owned_project(sess.project_id, current_user, db)
    ok = engine.skip_intervention(session_id)
    return {"ok": ok}


@router.post("/api/fgi-sessions/{session_id}/control")
async def control(
    session_id: str,
    body: FGIControlRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """수동 제어 — 다음 주제로 전환(next_round) 또는 토론 종료(end_session). 진행 루프가 다음 턴에 소비."""
    sess = await _load_session(session_id, db)
    await _verify_owned_project(sess.project_id, current_user, db)
    ok = engine.set_control(session_id, body.action)
    return {"ok": ok, "action": body.action}


@router.get("/api/fgi-sessions/{session_id}", response_model=FGISessionDetailOut)
async def get_fgi_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """세션 메타 + 전체 turn (+ minutes_md). 재로드용."""
    sess = await _load_session(session_id, db)
    await _verify_owned_project(sess.project_id, current_user, db)
    res = await db.execute(
        select(FGITurn)
        .where(FGITurn.session_id == session_id)
        .order_by(FGITurn.round.asc(), FGITurn.order_in_round.asc(), FGITurn.created_at.asc())
    )
    detail = FGISessionDetailOut.model_validate(sess)
    detail.turns = [FGITurnOut.model_validate(t) for t in res.scalars().all()]
    return detail
