"""V1·V3 평가 오케스트레이션 + EvaluationSnapshot 적재.

설계 의도:
- agent.persona_full_prompt 를 system, 자극 question_ko 를 user 로 LLM 호출
- 답변을 V1·V3 양쪽에서 재사용 → LLM 호출 1회로 두 지표 산출
- agent 별 progress 이벤트 발행 (NDJSON 라우터에서 사용)
- V3 distinct 는 프로젝트 단위 산출 후 각 agent snapshot identity_stats 에
  같은 값을 stamp — 시각화·verdict 산정 양쪽에서 self-contained

EvaluationSnapshot.version 은 (agent_id 기준 max+1) 로 자동 증가.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, Awaitable, Callable, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import Agent, AsyncSessionLocal, EvaluationSnapshot, ResearchProject
from services.llm_client import chat_completion

from .stimuli import Question, v3_questions
from .v1_response_sync import compute_v1
from .v3_persona_diversity import build_persona_vector, compute_v3


EventCallback = Optional[Callable[[dict[str, Any]], Awaitable[None]]]


def _parse_scratch(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}


async def _next_version(db: AsyncSession, agent_id: str) -> int:
    res = await db.execute(
        select(func.max(EvaluationSnapshot.version)).where(EvaluationSnapshot.agent_id == agent_id)
    )
    cur = res.scalar_one_or_none()
    return (cur or 0) + 1


async def _generate_answers(
    *,
    agent: Agent,
    questions: list[Question],
    mock_llm: bool | None,
) -> dict[str, str]:
    """agent 1명에 대해 N개 자극의 답변을 모두 생성."""
    system = agent.persona_full_prompt or "당신은 평범한 한국 소비자입니다."
    answers: dict[str, str] = {}
    for q in questions:
        answer = await chat_completion(system=system, user=q.question_ko, mock=mock_llm)
        answers[q.qid] = answer
    return answers


async def run_v1_v3(
    *,
    project_id: str,
    metrics: list[str],
    mock_llm: bool | None = None,
    synthetic_embeddings: bool | None = None,
    on_event: EventCallback = None,
) -> dict[str, Any]:
    """프로젝트의 모든 agent 에 대해 V1·V3 평가 실행.

    Args:
        project_id: 평가 대상 프로젝트.
        metrics: ['v1'], ['v3'], ['v1','v3'] 중. 다른 값은 무시(후속 슬라이스).
        mock_llm: chat completion 합성 모드 강제.
        synthetic_embeddings: 임베딩 합성 모드 강제.
        on_event: NDJSON 진행 콜백.

    Returns:
        {distinct, snapshots_by_agent, scatter} 요약.
    """
    metrics = [m for m in metrics if m in ("v1", "v3")]
    if not metrics:
        return {"status": "skipped", "reason": "지원하는 지표 없음 (v1/v3 만)"}

    eval_config = {
        "metrics": metrics,
        "mock_llm": mock_llm,
        "synthetic_embeddings": synthetic_embeddings,
        "model": "gpt-4o",
        "embedding_model": "text-embedding-3-small",
    }

    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(Agent).where(Agent.project_id == project_id).order_by(Agent.created_at.asc())
        )
        agents = list(res.scalars().all())

    if not agents:
        return {"status": "skipped", "reason": "프로젝트에 에이전트가 없음"}

    questions = v3_questions()  # V1 ⊆ V3 자극이므로 V3 자극을 한 번 생성하면 V1 도 커버
    if on_event:
        await on_event({"type": "start", "total": len(agents), "metrics": metrics})

    # 단계 1: agent 별 답변 생성 + V1 계산
    persona_vectors: dict[str, list[float]] = {}
    per_agent_v1: dict[str, dict[str, Any]] = {}
    per_agent_answers: dict[str, dict[str, str]] = {}

    for idx, agent in enumerate(agents, start=1):
        if on_event:
            await on_event({"type": "agent_start", "current": idx, "total": len(agents), "agent_id": agent.id})

        try:
            answers = await _generate_answers(agent=agent, questions=questions, mock_llm=mock_llm)
            per_agent_answers[agent.id] = answers

            if "v1" in metrics:
                scratch = _parse_scratch(agent.scratch)
                v1 = compute_v1(
                    agent_answers=answers,
                    scratch=scratch,
                    synthetic_embeddings=synthetic_embeddings,
                )
                per_agent_v1[agent.id] = v1

            if "v3" in metrics:
                vec = build_persona_vector(
                    answers=[answers[q.qid] for q in questions if q.qid in answers],
                    synthetic_embeddings=synthetic_embeddings,
                )
                persona_vectors[agent.id] = vec

            if on_event:
                payload = {"type": "agent_done", "current": idx, "total": len(agents), "agent_id": agent.id}
                if agent.id in per_agent_v1:
                    payload["v1_sync"] = per_agent_v1[agent.id]["sync"]
                await on_event(payload)

        except Exception as e:
            if on_event:
                await on_event({"type": "error", "agent_id": agent.id, "reason": str(e)})

    # 단계 2: V3 프로젝트 단위 산출
    v3_result: dict[str, Any] = {}
    v3_xy: dict[str, tuple[float, float]] = {}
    if "v3" in metrics and persona_vectors:
        v3_result = compute_v3(agent_persona_vectors=persona_vectors)
        for s in v3_result.get("scatter", []):
            v3_xy[s["agent_id"]] = (s["x"], s["y"])
        if on_event:
            await on_event({
                "type": "v3_done",
                "distinct": v3_result.get("distinct"),
                "n_agents": v3_result.get("n_agents"),
            })

    # 단계 3: snapshot 저장 — 각 agent 별 identity_stats 채워 INSERT
    snapshots: dict[str, str] = {}
    async with AsyncSessionLocal() as db:
        for agent in agents:
            identity: dict[str, Any] = {}
            if agent.id in per_agent_v1:
                v1 = per_agent_v1[agent.id]
                identity["sync"] = v1["sync"]
                identity["v1_n_eval"] = v1["n_eval"]
            if v3_result:
                identity["distinct"] = v3_result["distinct"]
                identity["v3_n_agents"] = v3_result["n_agents"]
                xy = v3_xy.get(agent.id)
                if xy:
                    identity["pca_x"] = xy[0]
                    identity["pca_y"] = xy[1]
            if not identity:
                continue

            version = await _next_version(db, agent.id)
            verdict = _verdict_partial(identity)
            snap_id = str(uuid.uuid4())
            db.add(EvaluationSnapshot(
                id=snap_id,
                agent_id=agent.id,
                version=version,
                identity_stats=identity,
                logic_stats=None,
                verdict=verdict,
                eval_config=eval_config,
            ))
            snapshots[agent.id] = snap_id

        await db.commit()

    if on_event:
        await on_event({"type": "done", "snapshots": len(snapshots)})

    return {
        "status": "ok",
        "snapshots": snapshots,
        "distinct": v3_result.get("distinct"),
        "scatter": v3_result.get("scatter", []),
    }


def _verdict_partial(identity: dict[str, Any]) -> str:
    """EVAL_SPEC.md §6 임계의 V1 부분만 적용 (V2/V4/V5 는 후속 슬라이스).

    sync ≥ 0.80 + V3 distinct 미달 아님 → 'verified_partial'
    sync ≥ 0.60 → 'partial'
    else → 'failed'
    """
    sync = identity.get("sync")
    if sync is None:
        return "pending"
    if sync >= 0.80:
        return "verified_partial"
    if sync >= 0.60:
        return "partial"
    return "failed"
