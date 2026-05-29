"""평가 라우터 (Slice 2 — V1·V3).

엔드포인트:
- POST   /api/agents/{agent_id}/evaluate           — NDJSON 진행 스트림
- GET    /api/agents/{agent_id}/evaluations        — 시계열 (version 내림차순)
- GET    /api/agents/{agent_id}/evaluations/latest — 최신 스냅샷
- GET    /api/projects/{project_id}/evaluations/scatter — V3 산점도 데이터

V1·V3 는 함께 트리거 시 LLM 호출을 공유하므로 단일 agent 호출이라도
프로젝트 전체 agent 가 평가된다(V3 가 프로젝트 단위 지표).
"""
from __future__ import annotations

import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import Agent, EvaluationSnapshot, ResearchProject, User, get_db
from evaluation.runner import run_v1_v3
from evaluation.v3_persona_diversity import normalize_distinct
from models.schemas import EvaluationSnapshotOut
from services.auth_service import get_current_user

router = APIRouter(tags=["evaluation"])


async def _load_agent_with_project(agent_id: str, user: User, db: AsyncSession) -> Agent:
    res = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = res.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="에이전트를 찾을 수 없습니다.")
    res = await db.execute(select(ResearchProject).where(ResearchProject.id == agent.project_id))
    project = res.scalar_one_or_none()
    if not project or project.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="에이전트를 찾을 수 없습니다.")
    return agent


async def _verify_owned_project(project_id: str, user: User, db: AsyncSession) -> ResearchProject:
    res = await db.execute(select(ResearchProject).where(ResearchProject.id == project_id))
    project = res.scalar_one_or_none()
    if not project or project.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="프로젝트를 찾을 수 없습니다.")
    return project


def _snapshot_to_out(s: EvaluationSnapshot) -> EvaluationSnapshotOut:
    return EvaluationSnapshotOut(
        id=s.id,
        agent_id=s.agent_id,
        version=s.version,
        identity_stats=s.identity_stats,
        logic_stats=s.logic_stats,
        verdict=s.verdict,
        eval_config=s.eval_config,
        evaluated_at=s.evaluated_at,
    )


# ── 트리거 ────────────────────────────────────────────────────────────────

class EvaluateRequest(BaseModel):
    """평가 트리거 요청.

    Slice 2 범위는 v1/v3 만. v2/v4/v5 는 무시(후속 슬라이스).
    """
    metrics: list[str] = Field(default_factory=lambda: ["v1", "v3"])
    mock_llm: bool | None = None
    synthetic_embeddings: bool | None = None


async def _stream_eval(
    project_id: str,
    triggered_by_agent_id: str,
    req: EvaluateRequest,
) -> AsyncGenerator[bytes, None]:
    def emit(payload: dict) -> bytes:
        return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")

    yield emit({
        "type": "trigger_meta",
        "project_id": project_id,
        "triggered_by_agent_id": triggered_by_agent_id,
        "metrics": req.metrics,
    })

    queue: list[dict] = []

    async def on_event(p: dict) -> None:
        queue.append(p)

    # 백그라운드 코루틴으로 평가 진행 + 큐 드레인
    import asyncio
    runner_task = asyncio.create_task(run_v1_v3(
        project_id=project_id,
        metrics=req.metrics,
        mock_llm=req.mock_llm,
        synthetic_embeddings=req.synthetic_embeddings,
        on_event=on_event,
    ))

    while True:
        # 큐에 쌓인 이벤트 모두 flush
        while queue:
            yield emit(queue.pop(0))
        if runner_task.done():
            break
        await asyncio.sleep(0.05)

    # 종료 후 남은 이벤트
    while queue:
        yield emit(queue.pop(0))

    try:
        result = runner_task.result()
        yield emit({"type": "result", **{k: v for k, v in result.items() if k != "scatter"}})
    except Exception as e:
        yield emit({"type": "error", "reason": str(e)})


@router.post("/api/agents/{agent_id}/evaluate")
async def trigger_evaluate(
    agent_id: str,
    req: EvaluateRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """V1·V3 평가 트리거. NDJSON 진행 스트림.

    V3 는 프로젝트 단위 지표이므로 한 agent 트리거라도 프로젝트의 모든
    agent 가 평가되어 각자 EvaluationSnapshot 이 생성된다.
    """
    agent = await _load_agent_with_project(agent_id, current_user, db)
    request = req or EvaluateRequest()
    return StreamingResponse(
        _stream_eval(agent.project_id, agent_id, request),
        media_type="application/x-ndjson",
        # 프록시(Cloud Run/nginx)가 응답을 버퍼링해 진행 상황이 한꺼번에 나오는 것을 방지.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


# ── 조회 ───────────────────────────────────────────────────────────────────

@router.get("/api/agents/{agent_id}/evaluations", response_model=list[EvaluationSnapshotOut])
async def list_evaluations(
    agent_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """평가 스냅샷 시계열 — version 내림차순 (최신 먼저)."""
    await _load_agent_with_project(agent_id, current_user, db)
    res = await db.execute(
        select(EvaluationSnapshot)
        .where(EvaluationSnapshot.agent_id == agent_id)
        .order_by(EvaluationSnapshot.version.desc())
        .limit(limit)
    )
    return [_snapshot_to_out(s) for s in res.scalars().all()]


@router.get("/api/agents/{agent_id}/evaluations/latest", response_model=EvaluationSnapshotOut | None)
async def latest_evaluation(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """최신 스냅샷 (대시보드용). 없으면 null."""
    await _load_agent_with_project(agent_id, current_user, db)
    res = await db.execute(
        select(EvaluationSnapshot)
        .where(EvaluationSnapshot.agent_id == agent_id)
        .order_by(EvaluationSnapshot.version.desc())
        .limit(1)
    )
    s = res.scalar_one_or_none()
    return _snapshot_to_out(s) if s else None


@router.get("/api/projects/{project_id}/evaluations/scatter")
async def project_scatter(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """프로젝트 내 모든 agent 의 최신 V3 산점 좌표.

    응답: {distinct, distinct_norm, n_points, points: [{agent_id, display_name, emoji, x, y, sync}]}
    """
    await _verify_owned_project(project_id, current_user, db)

    # 프로젝트 내 agent 별 최신 snapshot 조회
    res = await db.execute(
        select(Agent).where(Agent.project_id == project_id).order_by(Agent.created_at.asc())
    )
    agents = list(res.scalars().all())

    points: list[dict] = []
    distinct_vals: list[float] = []
    for a in agents:
        r2 = await db.execute(
            select(EvaluationSnapshot)
            .where(EvaluationSnapshot.agent_id == a.id)
            .order_by(EvaluationSnapshot.version.desc())
            .limit(1)
        )
        snap = r2.scalar_one_or_none()
        if not snap or not snap.identity_stats:
            continue
        stats = snap.identity_stats
        if "pca_x" not in stats or "pca_y" not in stats:
            continue
        points.append({
            "agent_id": a.id,
            "display_name": a.display_name,
            "emoji": a.emoji,
            "cluster": a.cluster,
            "x": stats["pca_x"],
            "y": stats["pca_y"],
            "sync": stats.get("sync"),
        })
        if "distinct" in stats:
            distinct_vals.append(stats["distinct"])

    distinct = max(distinct_vals) if distinct_vals else None
    return {
        "distinct": distinct,
        "distinct_norm": normalize_distinct(distinct),
        "n_points": len(points),
        "points": points,
    }
