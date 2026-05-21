"""Plan 0007 — conversations 라우터 통합 테스트.

aiosqlite in-memory + httpx.AsyncClient + ASGITransport. OPENAI_API_KEY 미설정이라
LLM 은 결정적 mock 으로 동작 (services/llm_client._mock_answer).
"""
from __future__ import annotations

import json
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-please-ignore")
os.environ.pop("OPENAI_API_KEY", None)  # mock LLM 강제

import asyncio

import httpx
from httpx import ASGITransport

from database import Agent, AsyncSessionLocal, Base, ResearchProject, User, engine
from main import app
from services.auth_service import create_access_token, hash_password


async def _reset_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def _seed_user_project_agent() -> tuple[str, str, str]:
    """user(token) + project + package agent 1명 시드. (token, project_id, agent_id)."""
    user_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())
    # FK 의존성 순서대로 분리 커밋 (relationship 미정의라 단일 commit 시 insert 순서 보장 안 됨)
    async with AsyncSessionLocal() as s:
        s.add(User(id=user_id, email="u1@example.com", hashed_pw=hash_password("password1234"), name="테스터", role="user"))
        await s.commit()
        s.add(ResearchProject(id=project_id, user_id=user_id, title="PoC", status="active"))
        await s.commit()
        s.add(Agent(
            id=agent_id, project_id=project_id, source_type="package", source_ref="pid_001",
            display_name="20대 여성 · 페르소나 001", emoji="👤",
            persona_full_prompt="당신은 20대 여성 소비자 페르소나입니다. 일관되게 답하세요.",
        ))
        await s.commit()
    token = create_access_token(user_id, "u1@example.com", "user")
    return token, project_id, agent_id


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def test_create_message_and_reload():
    async def run():
        await _reset_db()
        token, project_id, agent_id = await _seed_user_project_agent()
        headers = {"Authorization": f"Bearer {token}"}
        async with _client() as ac:
            # 1) 대화 생성 (에이전트 스코프)
            r = await ac.post(f"/api/agents/{agent_id}/conversations",
                              json={"title": "첫 대화"}, headers=headers)
            assert r.status_code == 201, r.text
            conv_id = r.json()["id"]

            # 2) 메시지 전송 → SSE 스트림
            r = await ac.post(f"/api/conversations/{conv_id}/messages",
                              json={"content": "안녕하세요, 요즘 소비 습관이 궁금해요."}, headers=headers)
            assert r.status_code == 200, r.text
            events = [json.loads(line[len("data: "):]) for line in r.text.splitlines()
                      if line.startswith("data: ")]
            types = [e["type"] for e in events]
            assert types[0] == "start" and "delta" in types and types[-1] == "end"
            full = events[-1]["content"]
            assert full  # 비어있지 않은 응답
            assert events[-1]["confidence"] == "unknown"

            # 3) 재로드 — user + agent 2턴 영속
            r = await ac.get(f"/api/conversations/{conv_id}", headers=headers)
            assert r.status_code == 200, r.text
            turns = r.json()["turns"]
            assert [t["role"] for t in turns] == ["user", "agent"]
            assert turns[1]["content"] == full

    asyncio.run(run())


def test_ownership_enforced():
    async def run():
        await _reset_db()
        token, project_id, agent_id = await _seed_user_project_agent()
        # 실제 존재하는 다른 사용자 (인증은 통과하되 소유권 없음 → 404 기대)
        other_id = str(uuid.uuid4())
        async with AsyncSessionLocal() as s:
            s.add(User(id=other_id, email="intruder@example.com", hashed_pw=hash_password("password1234"), role="user"))
            await s.commit()
        other = create_access_token(other_id, "intruder@example.com", "user")
        async with _client() as ac:
            r = await ac.post(f"/api/agents/{agent_id}/conversations",
                              json={}, headers={"Authorization": f"Bearer {other}"})
            assert r.status_code == 404, r.text

    asyncio.run(run())
