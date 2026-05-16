"""Slice 2.2 — evaluation 라우터 통합 테스트."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid

import httpx
import pytest
from httpx import ASGITransport

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-please-ignore")

from database import (
    Agent,
    AsyncSessionLocal,
    Base,
    EvaluationSnapshot,
    ResearchProject,
    User,
    engine,
)
from main import app
from services.auth_service import create_access_token, hash_password


async def _reset_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def _seed_user(email: str = "u@u.com") -> tuple[str, str]:
    uid = str(uuid.uuid4())
    async with AsyncSessionLocal() as s:
        s.add(User(id=uid, email=email, hashed_pw=hash_password("password1234"), role="user"))
        await s.commit()
    return uid, create_access_token(uid, email, "user")


async def _seed_project_with_agents(user_id: str, n: int = 3) -> tuple[str, list[str]]:
    async with AsyncSessionLocal() as s:
        project = ResearchProject(id=str(uuid.uuid4()), user_id=user_id, title="p")
        s.add(project)
        await s.flush()
        ids = []
        for i in range(n):
            aid = str(uuid.uuid4())
            ids.append(aid)
            s.add(Agent(
                id=aid,
                project_id=project.id,
                source_type="twin",
                source_ref=f"r{i}",
                display_name=f"A{i}",
                emoji="🧪",
                persona_full_prompt=f"archetype {i} 한국 소비자.",
                scratch={
                    "self_aspire": f"agent {i} 이상",
                    "self_ought": f"agent {i} 의무",
                    "self_actual": f"agent {i} 실제",
                },
            ))
        await s.commit()
        return project.id, ids


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def test_evaluate_creates_snapshots_per_agent():
    async def run():
        await _reset_db()
        user_id, token = await _seed_user()
        project_id, agent_ids = await _seed_project_with_agents(user_id, n=3)

        async with _client() as ac:
            r = await ac.post(
                f"/api/agents/{agent_ids[0]}/evaluate",
                json={"metrics": ["v1", "v3"], "mock_llm": True, "synthetic_embeddings": True},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200, r.text
            assert r.headers["content-type"].startswith("application/x-ndjson")
            events = [json.loads(line) for line in r.text.splitlines() if line.strip()]

        types = [e["type"] for e in events]
        assert "trigger_meta" in types
        assert "start" in types
        assert "v3_done" in types
        assert "result" in types

        # 3 agent × 1 run = 3 snapshot
        from sqlalchemy import select as sa_select
        async with AsyncSessionLocal() as db:
            res = await db.execute(sa_select(EvaluationSnapshot))
            snaps = list(res.scalars().all())
            assert len(snaps) == 3
            for s in snaps:
                assert "sync" in s.identity_stats
                assert "distinct" in s.identity_stats
                assert "pca_x" in s.identity_stats
    asyncio.run(run())


def test_list_evaluations_sorted_desc():
    async def run():
        await _reset_db()
        user_id, token = await _seed_user()
        project_id, agent_ids = await _seed_project_with_agents(user_id, n=2)

        async with _client() as ac:
            # 2회 실행 → version 2 까지
            for _ in range(2):
                r = await ac.post(
                    f"/api/agents/{agent_ids[0]}/evaluate",
                    json={"metrics": ["v1"], "mock_llm": True, "synthetic_embeddings": True},
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert r.status_code == 200

            r = await ac.get(
                f"/api/agents/{agent_ids[0]}/evaluations",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200
            snaps = r.json()
            assert len(snaps) == 2
            assert snaps[0]["version"] == 2  # 내림차순
            assert snaps[1]["version"] == 1
    asyncio.run(run())


def test_latest_evaluation():
    async def run():
        await _reset_db()
        user_id, token = await _seed_user()
        project_id, agent_ids = await _seed_project_with_agents(user_id, n=2)

        async with _client() as ac:
            r = await ac.get(
                f"/api/agents/{agent_ids[0]}/evaluations/latest",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200
            assert r.json() is None  # 평가 전이라 null

            await ac.post(
                f"/api/agents/{agent_ids[0]}/evaluate",
                json={"metrics": ["v1"], "mock_llm": True, "synthetic_embeddings": True},
                headers={"Authorization": f"Bearer {token}"},
            )

            r = await ac.get(
                f"/api/agents/{agent_ids[0]}/evaluations/latest",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200
            body = r.json()
            assert body is not None
            assert body["version"] == 1
            assert "sync" in body["identity_stats"]
    asyncio.run(run())


def test_project_scatter_after_eval():
    async def run():
        await _reset_db()
        user_id, token = await _seed_user()
        project_id, agent_ids = await _seed_project_with_agents(user_id, n=3)

        async with _client() as ac:
            # 평가 전 — points 비어야 함
            r = await ac.get(
                f"/api/projects/{project_id}/evaluations/scatter",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200
            assert r.json()["n_points"] == 0

            # 평가 실행
            r = await ac.post(
                f"/api/agents/{agent_ids[0]}/evaluate",
                json={"metrics": ["v1", "v3"], "mock_llm": True, "synthetic_embeddings": True},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200

            r = await ac.get(
                f"/api/projects/{project_id}/evaluations/scatter",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200
            body = r.json()
            assert body["n_points"] == 3
            assert body["distinct"] is not None
            for p in body["points"]:
                assert "x" in p and "y" in p
                assert p["display_name"] is not None
    asyncio.run(run())


def test_evaluate_other_user_forbidden():
    async def run():
        await _reset_db()
        user_a, token_a = await _seed_user("a@a.com")
        _, token_b = await _seed_user("b@b.com")
        _, agent_ids = await _seed_project_with_agents(user_a, n=1)

        async with _client() as ac:
            r = await ac.post(
                f"/api/agents/{agent_ids[0]}/evaluate",
                json={"metrics": ["v1"], "mock_llm": True, "synthetic_embeddings": True},
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert r.status_code == 404  # 존재 비노출
    asyncio.run(run())
