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
from evaluation.stimuli import (
    V1_HOLDOUT_STIMULI,
    V1_OBJECTIVE_STIMULI,
    V1_SYNTHETIC_STIMULI,
    v1_questions,
    v3_questions,
)

# compute_v1 직접 단위 테스트용 — 합성 자극 앞 3개(recent_purchase / info_source
# / lifestyle). EVAL_V1_MODE 기본값(객관식)과 무관하게 동작하도록 명시 전달한다.
_SYNTH3 = list(V1_SYNTHETIC_STIMULI[:3])
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
        "holdout_recent_purchase": "최근 큰 소비 텍스트 A",
        "holdout_info_source": "신뢰하는 정보 출처 텍스트 B",
        "holdout_lifestyle": "라이프스타일 한 단어 텍스트 C",
    }
    agent_answers = {
        "recent_purchase": "최근 큰 소비 텍스트 A",
        "info_source": "신뢰하는 정보 출처 텍스트 B",
        "lifestyle": "라이프스타일 한 단어 텍스트 C",
    }
    result = compute_v1(
        agent_answers=agent_answers, scratch=scratch, questions=_SYNTH3, synthetic_embeddings=True,
    )
    assert result["n_eval"] == 3
    assert result["sync"] >= 0.99  # 동일 텍스트 → 동일 합성 임베딩 → cosine 1


def test_compute_v1_different_text_lower_sync():
    """다른 답변이면 sync 가 떨어져야 함."""
    scratch = {
        "holdout_recent_purchase": "지난 달 가전을 비교 끝에 가장 싼 모델로 결정했습니다.",
        "holdout_info_source": "오랜 거래 동네 가게 사장님의 말을 가장 신뢰합니다.",
        "holdout_lifestyle": "한 단어로 계획형 — 매달 예산을 미리 짭니다.",
    }
    agent_answers = {
        "recent_purchase": "사전예약 한정판 신상 운동화를 시세 두 배에 결제했습니다.",
        "info_source": "인스타와 유튜브 쇼츠에서 트렌드를 가장 먼저 봅니다.",
        "lifestyle": "한 단어로 얼리어답터 — 새 서비스를 가장 먼저 시도합니다.",
    }
    result = compute_v1(
        agent_answers=agent_answers, scratch=scratch, questions=_SYNTH3, synthetic_embeddings=True,
    )
    assert result["n_eval"] == 3
    # 합성 임베딩은 텍스트 sha256 기반이라 서로 다른 텍스트는 거의 직교 (~0)
    assert -0.2 < result["sync"] < 0.2


def test_compute_v1_skips_missing():
    """scratch 또는 answer 누락 시 skip."""
    scratch = {"holdout_recent_purchase": "A"}
    agent_answers = {"recent_purchase": "A", "info_source": "B"}  # lifestyle 누락
    result = compute_v1(
        agent_answers=agent_answers, scratch=scratch, questions=_SYNTH3, synthetic_embeddings=True,
    )
    assert result["n_eval"] == 1
    assert set(result["skipped"]) == {"info_source", "lifestyle"}


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
    assert r["distinct_norm"] == 1.0  # 상한(0.47) 초과 → 1.0 으로 클램프
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
            # V3 anchor + V1 hold-out ground truth(객관식·인터뷰) 를 모두 시드.
            # hold-out 키가 있어야 compute_v1 이 자극을 skip 하지 않고 채점한다
            # (runner 가 v1 자극 답변을 생성하는지 검증하기 위함).
            scratch = {
                "self_aspire": f"agent {i} 의 이상적 삶",
                "self_ought": f"agent {i} 의 의무감",
                "self_actual": f"agent {i} 의 실제 성격",
            }
            for q in (*V1_OBJECTIVE_STIMULI, *V1_HOLDOUT_STIMULI):
                if q.scratch_key:
                    scratch[q.scratch_key] = f"agent {i} · {q.qid} · 3 - 보통이다"
            session.add(Agent(
                id=aid,
                project_id=project.id,
                source_type="twin",
                source_ref=f"r{i}",
                display_name=f"A{i}",
                persona_full_prompt=f"당신은 archetype #{i} 의 한국 소비자입니다.",
                scratch=scratch,
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
                # runner 가 v1 자극 답변을 생성했는지 — qid 불일치 회귀 가드.
                # hold-out 시드가 있는데 n_eval==0 이면 runner 가 v1 자극을
                # 생성하지 않고 전부 skip 한 것(과거 sync 항상 0 버그).
                assert stats["v1_n_eval"] > 0
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
                assert "distinct_norm" in stats  # 정규화 점수도 stamp
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
