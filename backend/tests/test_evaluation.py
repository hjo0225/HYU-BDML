"""Slice 2.1 — V1·V3 평가 모듈 단위 테스트.

mock_llm + synthetic_embeddings 로 외부 API 의존성 0. 결정적이라 회귀 안정.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from database import (
    Agent,
    AsyncSessionLocal,
    Base,
    EvaluationSnapshot,
    ResearchProject,
    User,
    engine,
)
from evaluation.runner import run_v1_v3
from evaluation.stimuli import v1_questions, v3_questions
from evaluation.v1_response_sync import compute_v1, cosine_similarity
from evaluation.v3_persona_diversity import build_persona_vector, compute_v3
from services.auth_service import hash_password


async def _reset_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


# ── 순수 산출 함수 ────────────────────────────────────────────────────────

def test_cosine_basic():
    assert cosine_similarity([1, 0, 0], [1, 0, 0]) == 1.0
    assert cosine_similarity([1, 0, 0], [0, 1, 0]) == 0.0
    assert round(cosine_similarity([1, 1, 0], [1, 0, 0]), 4) == round(1 / (2 ** 0.5), 4)
    assert cosine_similarity([], [1, 2]) == 0.0


def test_compute_v1_identical_text_high_sync():
    """동일 답변이면 sync 가 1.0 에 가까워야 함."""
    scratch = {
        "self_aspire": "이상적인 삶 텍스트 A",
        "self_ought": "의무 텍스트 B",
        "self_actual": "실제 성격 텍스트 C",
    }
    agent_answers = {
        "self_aspire": "이상적인 삶 텍스트 A",
        "self_ought": "의무 텍스트 B",
        "self_actual": "실제 성격 텍스트 C",
    }
    result = compute_v1(
        agent_answers=agent_answers, scratch=scratch, synthetic_embeddings=True,
    )
    assert result["n_eval"] == 3
    assert result["sync"] >= 0.99  # 동일 텍스트 → 동일 합성 임베딩 → cosine 1


def test_compute_v1_different_text_lower_sync():
    """다른 답변이면 sync 가 떨어져야 함."""
    scratch = {
        "self_aspire": "안정적 가족 중심 삶",
        "self_ought": "성실한 직장 생활",
        "self_actual": "검소한 소비자",
    }
    agent_answers = {
        "self_aspire": "모험과 자유로운 여행",
        "self_ought": "자기 자신을 위한 시간",
        "self_actual": "트렌드를 따라가는 얼리어답터",
    }
    result = compute_v1(
        agent_answers=agent_answers, scratch=scratch, synthetic_embeddings=True,
    )
    assert result["n_eval"] == 3
    # 합성 임베딩은 텍스트 sha256 기반이라 서로 다른 텍스트는 거의 직교 (~0)
    assert -0.2 < result["sync"] < 0.2


def test_compute_v1_skips_missing():
    """scratch 또는 answer 누락 시 skip."""
    scratch = {"self_aspire": "A"}
    agent_answers = {"self_aspire": "A", "self_ought": "B"}  # actual 누락
    result = compute_v1(
        agent_answers=agent_answers, scratch=scratch, synthetic_embeddings=True,
    )
    assert result["n_eval"] == 1
    assert set(result["skipped"]) == {"self_ought", "self_actual"}


def test_compute_v3_diversity_positive():
    """서로 다른 페르소나 벡터 → distinct > 0."""
    vecs = {
        "a": [1.0, 0.0, 0.0],
        "b": [0.0, 1.0, 0.0],
        "c": [0.0, 0.0, 1.0],
    }
    r = compute_v3(agent_persona_vectors=vecs)
    assert r["n_agents"] == 3
    assert r["distinct"] > 1.0  # 직교 단위 벡터 페어와이즈 = sqrt(2) ≈ 1.414
    assert len(r["scatter"]) == 3


def test_compute_v3_single_agent_zero():
    r = compute_v3(agent_persona_vectors={"a": [1.0, 0.0]})
    assert r["distinct"] == 0.0
    assert r["n_agents"] == 1


def test_build_persona_vector_average():
    """답변 N개의 임베딩 평균 = 페르소나 벡터."""
    vec = build_persona_vector(
        answers=["답변1", "답변2", "답변3"],
        synthetic_embeddings=True,
    )
    assert len(vec) == 1536
    assert any(v != 0.0 for v in vec)


# ── runner 통합 ────────────────────────────────────────────────────────────

async def _seed_project_with_agents(n: int = 3) -> tuple[str, list[str]]:
    user_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as session:
        session.add(User(id=user_id, email="e@e.com", hashed_pw=hash_password("pw1234567"), role="user"))
        await session.flush()
        project = ResearchProject(id=str(uuid.uuid4()), user_id=user_id, title="eval test")
        session.add(project)
        await session.flush()
        ids = []
        for i in range(n):
            aid = str(uuid.uuid4())
            ids.append(aid)
            session.add(Agent(
                id=aid,
                project_id=project.id,
                source_type="twin",
                source_ref=f"r{i}",
                display_name=f"A{i}",
                persona_full_prompt=f"당신은 archetype #{i} 의 한국 소비자입니다.",
                scratch={
                    "self_aspire": f"agent {i} 의 이상적 삶",
                    "self_ought": f"agent {i} 의 의무감",
                    "self_actual": f"agent {i} 의 실제 성격",
                },
            ))
        await session.commit()
        return project.id, ids


def test_runner_v1_only():
    async def run():
        await _reset_db()
        project_id, agent_ids = await _seed_project_with_agents(3)
        events: list[dict] = []

        async def on_event(p):
            events.append(p)

        result = await run_v1_v3(
            project_id=project_id,
            metrics=["v1"],
            mock_llm=True,
            synthetic_embeddings=True,
            on_event=on_event,
        )
        assert result["status"] == "ok"
        assert len(result["snapshots"]) == 3
        # V3 미요청 → distinct 없음
        assert result.get("distinct") is None

        # DB 검증
        from sqlalchemy import select as sa_select
        async with AsyncSessionLocal() as db:
            res = await db.execute(sa_select(EvaluationSnapshot))
            snaps = list(res.scalars().all())
            assert len(snaps) == 3
            for s in snaps:
                stats = s.identity_stats
                assert "sync" in stats
                assert "distinct" not in stats  # V3 미실행

        # event 시퀀스
        types = [e["type"] for e in events]
        assert types[0] == "start"
        assert types[-1] == "done"
        assert types.count("agent_done") == 3

    asyncio.run(run())


def test_runner_v1_and_v3():
    async def run():
        await _reset_db()
        project_id, agent_ids = await _seed_project_with_agents(3)

        result = await run_v1_v3(
            project_id=project_id,
            metrics=["v1", "v3"],
            mock_llm=True,
            synthetic_embeddings=True,
        )
        assert result["status"] == "ok"
        assert len(result["snapshots"]) == 3
        assert result["distinct"] is not None
        assert len(result["scatter"]) == 3

        from sqlalchemy import select as sa_select
        async with AsyncSessionLocal() as db:
            res = await db.execute(sa_select(EvaluationSnapshot))
            snaps = list(res.scalars().all())
            for s in snaps:
                stats = s.identity_stats
                assert "sync" in stats
                assert "distinct" in stats
                # V3 distinct 는 모든 agent snapshot 에 동일 값으로 stamp
                assert stats["distinct"] == result["distinct"]
    asyncio.run(run())


def test_runner_version_increments_on_rerun():
    async def run():
        await _reset_db()
        project_id, _ = await _seed_project_with_agents(2)

        await run_v1_v3(project_id=project_id, metrics=["v1"], mock_llm=True, synthetic_embeddings=True)
        await run_v1_v3(project_id=project_id, metrics=["v1"], mock_llm=True, synthetic_embeddings=True)

        from sqlalchemy import select as sa_select, func as sa_func
        async with AsyncSessionLocal() as db:
            res = await db.execute(sa_select(sa_func.max(EvaluationSnapshot.version)))
            max_v = res.scalar_one()
            assert max_v == 2
            res = await db.execute(sa_select(sa_func.count(EvaluationSnapshot.id)))
            assert res.scalar_one() == 4  # 2 agents × 2 runs
    asyncio.run(run())


def test_runner_no_agents_skips():
    async def run():
        await _reset_db()
        user_id = str(uuid.uuid4())
        async with AsyncSessionLocal() as session:
            session.add(User(id=user_id, email="e@e.com", hashed_pw=hash_password("pw1234567"), role="user"))
            await session.flush()
            project = ResearchProject(id=str(uuid.uuid4()), user_id=user_id, title="empty")
            session.add(project)
            await session.commit()
            pid = project.id

        result = await run_v1_v3(project_id=pid, metrics=["v1"], mock_llm=True, synthetic_embeddings=True)
        assert result["status"] == "skipped"
    asyncio.run(run())
