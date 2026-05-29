"""1:1 대화 서비스 (plan 0007).

사용자 ↔ 단일 에이전트 대화 세션 생성·조회 + 에이전트 응답 스트리밍.
시스템 프롬프트 = agent.persona_full_prompt (package 는 long-context 그대로),
messages = 이전 history(user/assistant) + 새 user 발화 — README 다중턴 방식.

라우터(routers/conversations.py)가 SSE 로 중계한다.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import Agent, Conversation, ConversationTurn
from fgi.prompts.utterance import build_v1_1_persona_intro
from services.agent_service import demographics as _agent_demographics
from services.llm_client import stream_chat

# package 페르소나(~30k 토큰)는 long-context 모델 필요. gpt-4.1-nano 도 128k+ 컨텍스트라 충분.
# 비용 절감 위해 gpt-4.1-nano 로 하향(2026-05-29) — 4.1-mini 의 ¼ 가격. 홀드아웃 평가는 llm_client 기본값 유지.
_LONG_CONTEXT_MODEL = "gpt-4.1-nano"


async def create_conversation(
    db: AsyncSession,
    *,
    project_id: str,
    agent_id: str,
    user_id: str,
    title: str | None,
) -> Conversation:
    """대화 세션 생성. 호출자가 프로젝트 소유권·에이전트 소속을 검증한 뒤 호출."""
    conv = Conversation(
        id=str(uuid.uuid4()),
        project_id=project_id,
        agent_id=agent_id,
        user_id=user_id,
        title=title,
    )
    db.add(conv)
    await db.flush()
    return conv


async def get_conversation(db: AsyncSession, conversation_id: str) -> Conversation | None:
    res = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    return res.scalar_one_or_none()


async def list_turns(db: AsyncSession, conversation_id: str) -> list[ConversationTurn]:
    res = await db.execute(
        select(ConversationTurn)
        .where(ConversationTurn.conversation_id == conversation_id)
        .order_by(ConversationTurn.created_at.asc(), ConversationTurn.id.asc())
    )
    return list(res.scalars().all())


def _build_messages(turns: list[ConversationTurn], new_user_content: str) -> list[dict[str, str]]:
    """저장된 history + 새 user 발화 → OpenAI messages (role 매핑: agent→assistant)."""
    messages: list[dict[str, str]] = []
    for t in turns:
        messages.append({
            "role": "assistant" if t.role == "agent" else "user",
            "content": t.content,
        })
    messages.append({"role": "user", "content": new_user_content})
    return messages


async def stream_reply(
    db: AsyncSession,
    *,
    conversation: Conversation,
    user_content: str,
    mock: bool | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """user 발화 저장 → 에이전트 응답 스트리밍(delta) → agent 발화 저장.

    Yields SSE 페이로드 dict (api-spec.md 준수):
      {type:'start', conversation_id, agent_id}
      {type:'delta', delta}
      {type:'end', turn_id, content, citations, confidence}
    예외는 호출자(라우터)가 잡아 {type:'error'} 로 전송.

    NOTE(PoC, plan 0007): citations/confidence(자가인용 마커·신뢰도)는 후속.
    이번 단계에서는 citations=[], confidence='unknown' 으로 채운다.
    """
    # 1) 에이전트 페르소나 로드
    res = await db.execute(select(Agent).where(Agent.id == conversation.agent_id))
    agent = res.scalar_one_or_none()
    if agent is None:
        raise ValueError("에이전트를 찾을 수 없습니다.")
    # Toubia v1.1(anti-RLHF·1인칭) 머리말을 페르소나 본문 앞에 결합 — FGI 와 동일 톤.
    age_range, gender = _agent_demographics(agent)
    v1_1_intro = build_v1_1_persona_intro(age_range, gender)
    persona_body = agent.persona_full_prompt or "당신은 설문 응답에 기반한 페르소나입니다."
    system = v1_1_intro + "\n\n" + persona_body

    yield {"type": "start", "conversation_id": conversation.id, "agent_id": conversation.agent_id}

    # 2) history 조회 후 user turn 저장
    turns = await list_turns(db, conversation.id)
    user_turn = ConversationTurn(
        id=str(uuid.uuid4()),
        conversation_id=conversation.id,
        role="user",
        content=user_content,
    )
    db.add(user_turn)
    await db.commit()

    # 3) 응답 스트리밍
    messages = _build_messages(turns, user_content)
    model = _LONG_CONTEXT_MODEL  # package 포함 안전한 기본값
    parts: list[str] = []
    async for delta in stream_chat(system=system, messages=messages, model=model, mock=mock):
        parts.append(delta)
        yield {"type": "delta", "delta": delta}

    full = "".join(parts).strip()

    # 4) agent turn 저장 (citations/confidence 는 PoC 에서 NULL)
    agent_turn = ConversationTurn(
        id=str(uuid.uuid4()),
        conversation_id=conversation.id,
        role="agent",
        content=full,
        confidence="unknown",
    )
    db.add(agent_turn)
    await db.commit()

    yield {
        "type": "end",
        "turn_id": agent_turn.id,
        "content": full,
        "citations": [],
        "confidence": "unknown",
    }
