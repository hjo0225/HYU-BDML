"""plan 0025 v2 회귀 검증 — mock 모드 FGI 1라운드 SSE 캡처에서
**발화 중 engagement 이벤트가 0개**(빈 dict → 생략) 인지 확인.

v2 는 발화 중 listener_update 핸들러가 임베딩이 아니라 LLM 추정을 호출한다.
mock 모드에서는 chat_completion 이 결정적 더미 답을 돌려주므로 JSON 파싱이
실패해 llm_engagement 가 빈 dict 를 반환 → 이벤트 생략. 이게 SSE 계약 보존의
회귀 가드. 실모드 검증은 데모 화면에서 사용자가 직접 확인한다.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ.setdefault("JWT_SECRET_KEY", "verify-secret")
os.environ.pop("OPENAI_API_KEY", None)
os.environ["FGI_INTERVENTION_TIMEOUT"] = "1"
os.environ["FGI_MAX_UTTER_PER_ROUND"] = "3"
os.environ["FGI_LLM_ENGAGEMENT"] = "0"
os.environ["FGI_MODERATOR_JUDGE"] = "0"

import httpx
from httpx import ASGITransport

from database import Agent, AsyncSessionLocal, Base, ResearchProject, User, engine
from main import app
from services.auth_service import create_access_token, hash_password


async def _reset_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def _seed(n: int = 3):
    uid, pid = str(uuid.uuid4()), str(uuid.uuid4())
    aids: list[str] = []
    async with AsyncSessionLocal() as s:
        s.add(User(id=uid, email="v@x.com", hashed_pw=hash_password("password1234"), name="v", role="user"))
        await s.commit()
        s.add(ResearchProject(id=pid, user_id=uid, title="verify", status="active"))
        await s.commit()
        for i in range(n):
            aid = str(uuid.uuid4())
            aids.append(aid)
            s.add(Agent(
                id=aid, project_id=pid, source_type="package", source_ref=f"v_{i}",
                display_name=f"청자 {i+1}", emoji="🧑",
                persona_full_prompt=f"당신은 소비자 {i+1}.",
            ))
        await s.commit()
    return create_access_token(uid, "v@x.com", "user"), pid, aids


async def main():
    await _reset_db()
    token, pid, aids = await _seed(3)
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post(
            f"/api/projects/{pid}/fgi-sessions",
            json={"topic": "검증용", "agent_ids": aids,
                  "rounds": [{"round": 1, "subtopic": "경험", "goal_question": "최근 경험은?"}],
                  "allow_user_intervention": False},
            headers=headers,
        )
        sess = r.json()
        r = await ac.post(f"/api/fgi-sessions/{sess['id']}/run", headers=headers)
        events = [json.loads(line[len("data: "):]) for line in r.text.splitlines() if line.startswith("data: ")]

    types = Counter(e["type"] for e in events)
    engagement_events = [e for e in events if e["type"] == "engagement"]
    print("이벤트 타입 분포:", dict(types))
    print(f"engagement 이벤트 수: {len(engagement_events)}  (mock 기대값=0)")
    assert len(engagement_events) == 0, (
        "mock 모드인데 engagement 이벤트가 흘렀음 — LLM 폴백/생략 경로가 깨졌을 가능성"
    )

    # plan 0026 회귀 가드 — 직전 PHASE_C_RECENT_LOCK(2) 턴 안에서 같은 사람이 다시 발화하지 않는지.
    # mock 모드는 모든 관심도가 0.5 라 안정 정렬상 등록 순서가 유지되지만, 직전 lock 이 깨지면
    # 같은 사람이 연속 나오는 회귀가 잡힌다.
    agent_ends = [e for e in events if e["type"] == "agent_end"]
    speakers = [e["agent_id"] for e in agent_ends]
    print(f"발화자 순서({len(speakers)}회): {[s[:6] for s in speakers]}")
    for i in range(len(speakers)):
        window = speakers[max(0, i - 2):i]   # 직전 2턴
        assert speakers[i] not in window, (
            f"직전 2턴 lock 위반: idx={i}, speaker={speakers[i][:6]}, recent={[s[:6] for s in window]}"
        )

    # 발화 자체는 정상 진행됐는지 — agent_end 가 ≥1
    assert len(agent_ends) >= 1, "발화가 아예 진행되지 않음"
    print("\n✓ plan 0026 회귀 가드 통과 — engagement 생략 + 직전 2턴 lock 유지 + 발화 정상 진행")


if __name__ == "__main__":
    asyncio.run(main())
