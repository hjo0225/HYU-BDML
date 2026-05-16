"""Slice 1.2 — projects/agents 라우터 통합 테스트.

aiosqlite in-memory DB + httpx.AsyncClient + ASGITransport.
pytest-asyncio 미사용 — asyncio.run() 으로 각 테스트 동기 실행.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 테스트용 in-memory SQLite 강제 — main 임포트 전에 설정해야 함
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-please-ignore")

import httpx
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import database as db_mod
from database import (
    Agent,
    AsyncSessionLocal,
    Base,
    ResearchProject,
    User,
    engine,
)
from main import app
from services.auth_service import create_access_token, hash_password


async def _reset_db() -> None:
    """모든 테이블 drop + create — 각 테스트마다 격리."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def _seed_user(email: str = "u1@example.com") -> tuple[str, str]:
    user_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as session:
        session.add(User(
            id=user_id,
            email=email,
            hashed_pw=hash_password("password1234"),
            name="테스터",
            role="user",
        ))
        await session.commit()
    token = create_access_token(user_id, email, "user")
    return user_id, token


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ── projects ───────────────────────────────────────────────────────────────

def test_create_and_list_projects():
    async def run():
        await _reset_db()
        _, token = await _seed_user()
        async with _client() as ac:
            r = await ac.post(
                "/api/projects",
                json={"title": "테스트 프로젝트"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 201, r.text
            created = r.json()
            assert created["title"] == "테스트 프로젝트"
            assert created["status"] == "draft"
            assert created["agent_count"] == 0

            r = await ac.get("/api/projects", headers={"Authorization": f"Bearer {token}"})
            assert r.status_code == 200
            assert any(p["id"] == created["id"] for p in r.json())

    asyncio.run(run())


def test_project_auto_title_when_omitted():
    async def run():
        await _reset_db()
        _, token = await _seed_user()
        async with _client() as ac:
            r = await ac.post("/api/projects", json={}, headers={"Authorization": f"Bearer {token}"})
            assert r.status_code == 201
            assert r.json()["title"].endswith("프로젝트")
    asyncio.run(run())


def test_other_user_cannot_access_project():
    async def run():
        await _reset_db()
        _, token_a = await _seed_user("a@example.com")
        _, token_b = await _seed_user("b@example.com")
        async with _client() as ac:
            r = await ac.post("/api/projects", json={"title": "A 소유"},
                              headers={"Authorization": f"Bearer {token_a}"})
            pid = r.json()["id"]
            r = await ac.get(f"/api/projects/{pid}",
                             headers={"Authorization": f"Bearer {token_b}"})
            assert r.status_code == 404  # 403 대신 404 — 존재 자체 비노출
    asyncio.run(run())


def test_patch_project_partial():
    async def run():
        await _reset_db()
        _, token = await _seed_user()
        async with _client() as ac:
            r = await ac.post("/api/projects", json={"title": "old"},
                              headers={"Authorization": f"Bearer {token}"})
            pid = r.json()["id"]
            r = await ac.patch(f"/api/projects/{pid}",
                               json={"status": "active"},
                               headers={"Authorization": f"Bearer {token}"})
            assert r.status_code == 200
            assert r.json()["status"] == "active"
            assert r.json()["title"] == "old"  # title 미변경
    asyncio.run(run())


def test_delete_project_cascades_agents():
    async def run():
        await _reset_db()
        user_id, token = await _seed_user()
        # 프로젝트 + 에이전트 시드
        async with AsyncSessionLocal() as session:
            project = ResearchProject(id=str(uuid.uuid4()), user_id=user_id, title="X", status="draft")
            session.add(project)
            await session.flush()
            session.add(Agent(
                id=str(uuid.uuid4()),
                project_id=project.id,
                source_type="twin",
                source_ref="r1",
                display_name="에이전트1",
            ))
            await session.commit()
            pid = project.id

        async with _client() as ac:
            r = await ac.delete(f"/api/projects/{pid}",
                                headers={"Authorization": f"Bearer {token}"})
            assert r.status_code == 204

        # CASCADE 확인
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select, func
            row = await session.execute(select(func.count(Agent.id)).where(Agent.project_id == pid))
            assert row.scalar_one() == 0
    asyncio.run(run())


# ── agents ─────────────────────────────────────────────────────────────────

async def _seed_project_with_agents(user_id: str) -> tuple[str, list[str]]:
    """프로젝트 + 에이전트 3건 시드."""
    async with AsyncSessionLocal() as session:
        project = ResearchProject(id=str(uuid.uuid4()), user_id=user_id, title="P", status="active")
        session.add(project)
        await session.flush()
        ids = []
        for i, (st, ra, mx, cluster) in enumerate([
            ("twin", 0.30, 4.5, 0),
            ("twin", 0.55, 3.0, 1),
            ("survey", 0.80, 2.0, 1),
        ]):
            aid = str(uuid.uuid4())
            ids.append(aid)
            session.add(Agent(
                id=aid,
                project_id=project.id,
                source_type=st,
                source_ref=f"r{i}",
                display_name=f"A{i}",
                emoji="🧪",
                intro_ko=f"intro {i}",
                persona_params={"l1.risk_aversion": ra, "l2.maximization": mx},
                cluster=cluster,
                scratch={"age_range": "30대", "gender": "여성"},
            ))
        await session.commit()
        return project.id, ids


def test_list_agents_basic():
    async def run():
        await _reset_db()
        user_id, token = await _seed_user()
        pid, ids = await _seed_project_with_agents(user_id)
        async with _client() as ac:
            r = await ac.get(f"/api/projects/{pid}/agents",
                             headers={"Authorization": f"Bearer {token}"})
            assert r.status_code == 200
            body = r.json()
            assert len(body) == 3
            assert body[0]["summary"]  # short_summary 채워짐
            assert body[0]["display_name"] == "A0"
    asyncio.run(run())


def test_list_agents_source_filter():
    async def run():
        await _reset_db()
        user_id, token = await _seed_user()
        pid, _ = await _seed_project_with_agents(user_id)
        async with _client() as ac:
            r = await ac.get(f"/api/projects/{pid}/agents?source_type=survey",
                             headers={"Authorization": f"Bearer {token}"})
            assert r.status_code == 200
            assert len(r.json()) == 1
    asyncio.run(run())


def test_list_agents_params_range_filter():
    async def run():
        await _reset_db()
        user_id, token = await _seed_user()
        pid, _ = await _seed_project_with_agents(user_id)
        async with _client() as ac:
            # risk_aversion 0.5-0.9 → 2건 (0.55, 0.80)
            r = await ac.get(
                f"/api/projects/{pid}/agents?params=l1.risk_aversion:0.5-0.9",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200
            assert len(r.json()) == 2
    asyncio.run(run())


def test_get_agent_detail_owner_only():
    async def run():
        await _reset_db()
        user_id_a, token_a = await _seed_user("a@example.com")
        _, token_b = await _seed_user("b@example.com")
        _, ids = await _seed_project_with_agents(user_id_a)
        async with _client() as ac:
            r = await ac.get(f"/api/agents/{ids[0]}",
                             headers={"Authorization": f"Bearer {token_a}"})
            assert r.status_code == 200
            assert "persona_full_prompt" in r.json()
            assert r.json()["scratch"] == {"age_range": "30대", "gender": "여성"}

            r = await ac.get(f"/api/agents/{ids[0]}",
                             headers={"Authorization": f"Bearer {token_b}"})
            assert r.status_code == 404
    asyncio.run(run())


def test_unauth_returns_401():
    async def run():
        await _reset_db()
        async with _client() as ac:
            r = await ac.get("/api/projects")
            assert r.status_code == 401
    asyncio.run(run())


# ── seed-twin (Slice 1.4) ──────────────────────────────────────────────────

def test_seed_twin_creates_30_agents():
    """fixture 30명 적재 → NDJSON 진행 + DB INSERT 검증."""
    async def run():
        await _reset_db()
        user_id, token = await _seed_user()
        # 프로젝트 시드
        async with AsyncSessionLocal() as session:
            project = ResearchProject(id=str(uuid.uuid4()), user_id=user_id, title="seed test", status="draft")
            session.add(project)
            await session.commit()
            pid = project.id

        async with _client() as ac:
            r = await ac.post(
                f"/api/projects/{pid}/agents/seed-twin",
                json={"limit": 30, "synthetic_embeddings": True},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200, r.text
            assert r.headers["content-type"].startswith("application/x-ndjson")
            events = [json.loads(line) for line in r.text.splitlines() if line.strip()]

        # start + 30 progress + cluster_done + done = 33 (또는 error 발생 시 차감)
        types = [e["type"] for e in events]
        assert types[0] == "start"
        assert types[-1] == "done"
        assert sum(1 for t in types if t == "progress") == 30
        assert events[-1]["total_created"] == 30

        # DB 검증 — 30명 + 클러스터 라벨 채워짐
        from sqlalchemy import func, select as sa_select
        async with AsyncSessionLocal() as session:
            row = await session.execute(
                sa_select(func.count(Agent.id)).where(Agent.project_id == pid)
            )
            assert row.scalar_one() == 30

    asyncio.run(run())


def test_seed_twin_unauthorized():
    """타인 프로젝트에 seed-twin 호출 → 404."""
    async def run():
        await _reset_db()
        user_a, token_a = await _seed_user("a@example.com")
        _, token_b = await _seed_user("b@example.com")
        async with AsyncSessionLocal() as session:
            project = ResearchProject(id=str(uuid.uuid4()), user_id=user_a, title="A 소유")
            session.add(project)
            await session.commit()
            pid = project.id

        async with _client() as ac:
            r = await ac.post(
                f"/api/projects/{pid}/agents/seed-twin",
                json={"limit": 1, "synthetic_embeddings": True},
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert r.status_code == 404
    asyncio.run(run())


def test_seed_twin_then_filter_by_params():
    """적재 후 /agents?params=l1.risk_aversion:0.0-0.5 가 일부 archetype 만 반환."""
    async def run():
        await _reset_db()
        user_id, token = await _seed_user()
        async with AsyncSessionLocal() as session:
            project = ResearchProject(id=str(uuid.uuid4()), user_id=user_id, title="filter test")
            session.add(project)
            await session.commit()
            pid = project.id

        async with _client() as ac:
            r = await ac.post(
                f"/api/projects/{pid}/agents/seed-twin",
                json={"limit": 30, "synthetic_embeddings": True},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200

            r = await ac.get(
                f"/api/projects/{pid}/agents?params=l1.risk_aversion:0.0-0.3",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200
            low_risk = r.json()

            r = await ac.get(
                f"/api/projects/{pid}/agents?params=l1.risk_aversion:0.4-1.0",
                headers={"Authorization": f"Bearer {token}"},
            )
            high_risk = r.json()

            r = await ac.get(
                f"/api/projects/{pid}/agents",
                headers={"Authorization": f"Bearer {token}"},
            )
            total = r.json()

        # 필터가 의미 있게 분할해야 함
        assert len(total) == 30
        assert len(low_risk) + len(high_risk) <= 30  # 중복 없음(0.3 vs 0.4 경계 분리)
        assert 0 < len(low_risk) < 30
        assert 0 < len(high_risk) < 30

    asyncio.run(run())
