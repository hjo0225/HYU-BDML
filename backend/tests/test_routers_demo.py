"""Plan 0008 — 데모 진입(/api/demo/session) 통합 테스트.

무인증 데모 세션 발급 → 토큰으로 데모 프로젝트 에이전트 조회 + 멱등성 확인.
SOURCE_PROJECT_ID 를 테스트에서 시드한 프로젝트로 바꿔치기한다.
"""
from __future__ import annotations

import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-please-ignore")
os.environ.pop("OPENAI_API_KEY", None)

import asyncio

import httpx
from httpx import ASGITransport

from database import Agent, AgentMemory, AsyncSessionLocal, Base, ResearchProject, User, engine
from main import app
from services import demo_service
from services.auth_service import hash_password


async def _reset_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def _seed_source(n: int = 2) -> str:
    """원본 user/project + package 에이전트 n명(+메모리). project_id 반환."""
    user_id = str(uuid.uuid4())
    pid = str(uuid.uuid4())
    async with AsyncSessionLocal() as s:
        s.add(User(id=user_id, email="owner@example.com", hashed_pw=hash_password("password1234"), role="user"))
        await s.commit()
        s.add(ResearchProject(id=pid, user_id=user_id, title="원본", status="active"))
        await s.commit()
        for i in range(n):
            aid = str(uuid.uuid4())
            s.add(Agent(id=aid, project_id=pid, source_type="package", source_ref=f"pid_{i:03d}",
                        display_name=f"참여자 {i+1}", persona_full_prompt="페르소나"))
            await s.commit()
            s.add(AgentMemory(agent_id=aid, source="base", category="l1_economic", text="경제 관점",
                              importance=70, embedding=[0.1, 0.2, 0.3]))
            await s.commit()
    return pid


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def test_demo_session_seeds_and_authorizes():
    async def run():
        await _reset_db()
        source_pid = await _seed_source(2)
        demo_service.SOURCE_PROJECT_ID = source_pid  # 복제 원본 바꿔치기

        async with _client() as ac:
            # 1) 무인증으로 데모 세션 시작
            r = await ac.post("/api/demo/session")
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["n_agents"] == 2
            assert data["project_id"] and data["project_id"] != source_pid  # 새 임시 프로젝트
            token = data["access_token"]

            # 2) 데모 토큰으로 임시 데모 프로젝트 에이전트 조회
            r = await ac.get(
                f"/api/projects/{data['project_id']}/agents",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 200, r.text
            assert len(r.json()) == 2

            # 3) 세션별 격리 — 두 번째 호출은 별개의 프로젝트/유저(각 2명)
            r2 = await ac.post("/api/demo/session")
            data2 = r2.json()
            assert data2["n_agents"] == 2
            assert data2["project_id"] != data["project_id"]

    asyncio.run(run())


def test_demo_cannot_create_or_modify_project():
    """공용 데모 계정(role='demo')은 프로젝트 생성·삭제 차단 (plan 0009)."""
    async def run():
        await _reset_db()
        source_pid = await _seed_source(2)
        demo_service.SOURCE_PROJECT_ID = source_pid

        async with _client() as ac:
            data = (await ac.post("/api/demo/session")).json()
            headers = {"Authorization": f"Bearer {data['access_token']}"}

            # 생성 차단
            r = await ac.post("/api/projects", json={"title": "데모가 만든 프로젝트"}, headers=headers)
            assert r.status_code == 403, r.text

            # 삭제 차단 (데모 프로젝트 보호)
            r = await ac.delete(f"/api/projects/{data['project_id']}", headers=headers)
            assert r.status_code == 403, r.text

            # 조회는 정상
            r = await ac.get(f"/api/projects/{data['project_id']}", headers=headers)
            assert r.status_code == 200, r.text

    asyncio.run(run())


def test_demo_session_can_start_fgi():
    async def run():
        await _reset_db()
        source_pid = await _seed_source(3)
        demo_service.SOURCE_PROJECT_ID = source_pid

        async with _client() as ac:
            r = await ac.post("/api/demo/session")
            data = r.json()
            token = data["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            agents = (await ac.get(f"/api/projects/{data['project_id']}/agents", headers=headers)).json()
            agent_ids = [a["id"] for a in agents]

            r = await ac.post(
                f"/api/projects/{data['project_id']}/fgi-sessions",
                json={"topic": "재방문율", "agent_ids": agent_ids,
                      "rounds": [{"round": 1, "subtopic": "경험", "goal_question": "최근 경험은?"}],
                      "allow_user_intervention": False},
                headers=headers,
            )
            assert r.status_code == 201, r.text

    asyncio.run(run())
