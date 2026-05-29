"""Plan 0008 — FGI 라우터/엔진 통합 테스트.

aiosqlite in-memory + httpx.AsyncClient + ASGITransport. OPENAI_API_KEY 미설정이라
LLM 은 결정적 mock (services/llm_client._mock_answer). 개입 대기로 테스트가 멈추지
않도록 run 은 allow_user_intervention=false 로 호출한다.
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
os.environ["FGI_INTERVENTION_TIMEOUT"] = "1"
os.environ["FGI_MAX_UTTER_PER_ROUND"] = "4"   # mock 라운드 빠르게
os.environ["FGI_LLM_ENGAGEMENT"] = "0"        # LLM 점수/판단은 mock 폴백이라 테스트선 생략
os.environ["FGI_MODERATOR_JUDGE"] = "0"

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


async def _seed(n_agents: int = 3) -> tuple[str, str, list[str]]:
    """user(token) + project + package agent n명. (token, project_id, [agent_id])."""
    user_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())
    agent_ids: list[str] = []
    async with AsyncSessionLocal() as s:
        s.add(User(id=user_id, email="host@example.com", hashed_pw=hash_password("password1234"), name="호스트", role="user"))
        await s.commit()
        s.add(ResearchProject(id=project_id, user_id=user_id, title="포토이즘 데모", status="active"))
        await s.commit()
        for i in range(n_agents):
            aid = str(uuid.uuid4())
            agent_ids.append(aid)
            s.add(Agent(
                id=aid, project_id=project_id, source_type="package", source_ref=f"pid_{i:03d}",
                display_name=f"참여자 {i+1}", emoji="👤",
                persona_full_prompt=f"당신은 셀프사진관 이용 경험이 있는 소비자 {i+1} 입니다. 일관되게 답하세요.",
            ))
        await s.commit()
    token = create_access_token(user_id, "host@example.com", "user")
    return token, project_id, agent_ids


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def test_create_run_and_reload():
    async def run():
        await _reset_db()
        token, project_id, agent_ids = await _seed(3)
        headers = {"Authorization": f"Bearer {token}"}
        async with _client() as ac:
            # 1) 세션 생성
            r = await ac.post(
                f"/api/projects/{project_id}/fgi-sessions",
                json={"topic": "포토이즘 재방문율 저하 원인", "agent_ids": agent_ids,
                      "rounds": [
                          {"round": 1, "subtopic": "경험 공유", "goal_question": "최근 경험을 들려주시겠어요?"},
                          {"round": 2, "subtopic": "원인 진단", "goal_question": "왜 그렇게 느끼셨나요?"},
                      ],
                      "allow_user_intervention": False},
                headers=headers,
            )
            assert r.status_code == 201, r.text
            sess = r.json()
            sid = sess["id"]
            assert sess["status"] == "running"
            assert sess["agent_ids"] == agent_ids

            # 2) 진행 (SSE) — 개입 없이 2라운드
            r = await ac.post(f"/api/fgi-sessions/{sid}/run", headers=headers)
            assert r.status_code == 200, r.text
            events = [json.loads(line[len("data: "):]) for line in r.text.splitlines()
                      if line.startswith("data: ")]
            types = [e["type"] for e in events]
            assert types[0] == "round_start"
            assert "moderator" in types
            assert "agent_delta" in types
            assert "agent_end" in types
            assert "round_end" in types
            assert types[-1] == "session_end"
            assert "user_turn_required" not in types  # 개입 비활성

            # round_start 는 소주제·목표질문을 포함 (v2 토론 플랜)
            rs0 = next(e for e in events if e["type"] == "round_start")
            assert rs0.get("subtopic") and rs0.get("goal_question")

            # 동적 선정이라 발화 수는 가변 — 최소 라운드당 1명 이상
            agent_ends = [e for e in events if e["type"] == "agent_end"]
            assert len(agent_ends) >= 2

            # session_end 는 구조화 보고서 포함
            rep = events[-1]["report"]
            assert rep["key_insights"] and rep["round_analysis"]
            assert rep["meta"]["n_rounds"] == 2

            # 3) 재로드 — turn 영속 + status=completed + minutes_md(JSON)
            r = await ac.get(f"/api/fgi-sessions/{sid}", headers=headers)
            assert r.status_code == 200, r.text
            detail = r.json()
            assert detail["status"] == "completed"
            assert json.loads(detail["minutes_md"])["key_insights"]  # JSON 보고서
            roles = [t["role"] for t in detail["turns"]]
            assert roles.count("agent") == len(agent_ends)
            assert roles.count("moderator") >= 2

    asyncio.run(run())


def test_intervene_rejected_outside_window():
    async def run():
        await _reset_db()
        token, project_id, agent_ids = await _seed(2)
        headers = {"Authorization": f"Bearer {token}"}
        async with _client() as ac:
            r = await ac.post(
                f"/api/projects/{project_id}/fgi-sessions",
                json={"topic": "테스트", "agent_ids": agent_ids,
                      "rounds": [{"round": 1, "subtopic": "경험", "goal_question": "최근 경험은?"}]},
                headers=headers,
            )
            sid = r.json()["id"]
            # 진행 전이라 개입 가능 구간이 아님 → 409
            r = await ac.post(f"/api/fgi-sessions/{sid}/intervene",
                              json={"content": "가격을 더 깊게 다뤄주세요"}, headers=headers)
            assert r.status_code == 409, r.text

    asyncio.run(run())


def test_suggest_rounds():
    """주제 → 라운드별 질문 제안 (plan 0009 · item 6). 키 미설정이라 템플릿 폴백."""
    async def run():
        await _reset_db()
        token, project_id, _ = await _seed(2)
        headers = {"Authorization": f"Bearer {token}"}
        async with _client() as ac:
            r = await ac.post(
                f"/api/projects/{project_id}/fgi-sessions/suggest-rounds",
                json={"topic": "포토이즘 재방문율 저하 원인", "n_rounds": 4},
                headers=headers,
            )
            assert r.status_code == 200, r.text
            rounds = r.json()["rounds"]
            assert len(rounds) == 4
            assert [x["round"] for x in rounds] == [1, 2, 3, 4]
            assert all(x["goal_question"] and x["subtopic"] for x in rounds)

    asyncio.run(run())


def test_suggest_rounds_ownership():
    async def run():
        await _reset_db()
        _, project_id, _ = await _seed(1)
        other_id = str(uuid.uuid4())
        async with AsyncSessionLocal() as s:
            s.add(User(id=other_id, email="intruder2@example.com", hashed_pw=hash_password("password1234"), role="user"))
            await s.commit()
        other = create_access_token(other_id, "intruder2@example.com", "user")
        async with _client() as ac:
            r = await ac.post(
                f"/api/projects/{project_id}/fgi-sessions/suggest-rounds",
                json={"topic": "x", "n_rounds": 3},
                headers={"Authorization": f"Bearer {other}"},
            )
            assert r.status_code == 404, r.text

    asyncio.run(run())


def test_ownership_enforced():
    async def run():
        await _reset_db()
        token, project_id, agent_ids = await _seed(2)
        other_id = str(uuid.uuid4())
        async with AsyncSessionLocal() as s:
            s.add(User(id=other_id, email="intruder@example.com", hashed_pw=hash_password("password1234"), role="user"))
            await s.commit()
        other = create_access_token(other_id, "intruder@example.com", "user")
        async with _client() as ac:
            r = await ac.post(
                f"/api/projects/{project_id}/fgi-sessions",
                json={"topic": "x", "agent_ids": agent_ids,
                      "rounds": [{"round": 1, "subtopic": "x", "goal_question": "x?"}]},
                headers={"Authorization": f"Bearer {other}"},
            )
            assert r.status_code == 404, r.text

    asyncio.run(run())


def test_engagement_events_emitted():
    """plan 0022 — Phase C 발화자 선정 점수를 engagement 이벤트로 라이브 송출한다.

    mock 기본은 FGI_LLM_ENGAGEMENT=0 이라 점수가 비어 이벤트가 생략된다(기존 계약 유지).
    여기선 config.USE_LLM_ENGAGEMENT 와 llm_engagement 를 패치해 점수가 있을 때 이벤트가
    올바른 스키마로 나오는지 검증한다.
    """
    from unittest.mock import patch

    from fgi import config as fgi_config
    from fgi import engagement as fgi_engagement

    async def _fake_engagement(agents_meta, subtopic, last_utterance, *, mock=None):
        # 참여자마다 구분되는 관심도 → 최상위가 next_agent_id 로 잡혀야 한다.
        return {a["agent_id"]: {"interest": round(0.9 - 0.2 * i, 2), "reaction": 0.5}
                for i, a in enumerate(agents_meta)}

    async def run():
        await _reset_db()
        token, project_id, agent_ids = await _seed(3)
        headers = {"Authorization": f"Bearer {token}"}
        async with _client() as ac:
            r = await ac.post(
                f"/api/projects/{project_id}/fgi-sessions",
                json={"topic": "관심도 송출 테스트", "agent_ids": agent_ids,
                      "rounds": [{"round": 1, "subtopic": "경험", "goal_question": "최근 경험은?",
                                  "probes": ["가격이 더 중요한가요, 품질이 더 중요한가요?"]}],
                      "allow_user_intervention": False},
                headers=headers,
            )
            sid = r.json()["id"]
            with patch.object(fgi_config, "USE_LLM_ENGAGEMENT", True), \
                 patch.object(fgi_engagement, "llm_engagement", _fake_engagement):
                r = await ac.post(f"/api/fgi-sessions/{sid}/run", headers=headers)
            assert r.status_code == 200, r.text
            events = [json.loads(line[len("data: "):]) for line in r.text.splitlines()
                      if line.startswith("data: ")]
            eng = [e for e in events if e["type"] == "engagement"]
            assert eng, "engagement 이벤트가 하나도 송출되지 않음"
            ev = eng[0]
            assert ev["phase"] in ("B", "C", "followup", "intervention")  # plan 0026: Phase B 도 송출
            assert set(ev["scores"]) == set(agent_ids)          # 전원 점수 포함
            assert all(0.0 <= v <= 1.0 for v in ev["scores"].values())
            assert ev.get("next_agent_id") in agent_ids
            # 기존 SSE 계약(첫·끝 이벤트)은 그대로 유지
            types = [e["type"] for e in events]
            assert types[0] == "round_start"
            assert types[-1] == "session_end"

    asyncio.run(run())
