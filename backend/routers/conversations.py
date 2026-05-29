"""1:1 대화 라우터 (plan 0007).

POST   /api/projects/{project_id}/conversations      대화 세션 생성
GET    /api/projects/{project_id}/conversations      목록 (agent_id 필터 옵션)
GET    /api/conversations/{conversation_id}          메타 + 전체 turn
POST   /api/conversations/{conversation_id}/messages 사용자 발화 → 에이전트 SSE 응답

SSE 페이로드: {type:'delta',content} / {type:'done',turn_id,content} / {type:'error',reason}
"""
from __future__ import annotations

import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import Agent, AsyncSessionLocal, Conversation, ResearchProject, User, get_db
from models.schemas import (
    ChatMessageRequest,
    ConversationCreate,
    ConversationDetailOut,
    ConversationOut,
    ConversationTurnOut,
)
from services import chat_service
from services.auth_service import get_current_user

router = APIRouter(tags=["conversations"])


async def _verify_owned_project(project_id: str, user: User, db: AsyncSession) -> ResearchProject:
    result = await db.execute(select(ResearchProject).where(ResearchProject.id == project_id))
    project = result.scalar_one_or_none()
    if not project or project.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="프로젝트를 찾을 수 없습니다.")
    return project


async def _verify_owned_conversation(conversation_id: str, user: User, db: AsyncSession) -> Conversation:
    conv = await chat_service.get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="대화를 찾을 수 없습니다.")
    await _verify_owned_project(conv.project_id, user, db)
    return conv


async def _verify_owned_agent(agent_id: str, user: User, db: AsyncSession) -> Agent:
    res = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = res.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="에이전트를 찾을 수 없습니다.")
    await _verify_owned_project(agent.project_id, user, db)
    return agent


@router.post(
    "/api/agents/{agent_id}/conversations",
    response_model=ConversationOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    agent_id: str,
    body: ConversationCreate | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """대화 세션 생성 — 에이전트 스코프. 프로젝트는 에이전트에서 도출."""
    agent = await _verify_owned_agent(agent_id, current_user, db)
    conv = await chat_service.create_conversation(
        db, project_id=agent.project_id, agent_id=agent_id,
        user_id=current_user.id, title=(body.title if body else None),
    )
    return ConversationOut.model_validate(conv)


@router.get("/api/agents/{agent_id}/conversations", response_model=list[ConversationOut])
async def list_conversations(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """에이전트의 대화 목록 (started_at 내림차순)."""
    await _verify_owned_agent(agent_id, current_user, db)
    result = await db.execute(
        select(Conversation)
        .where(Conversation.agent_id == agent_id)
        .order_by(Conversation.started_at.desc())
    )
    return [ConversationOut.model_validate(c) for c in result.scalars().all()]


@router.get("/api/conversations/{conversation_id}", response_model=ConversationDetailOut)
async def get_conversation_detail(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = await _verify_owned_conversation(conversation_id, current_user, db)
    turns = await chat_service.list_turns(db, conversation_id)
    detail = ConversationDetailOut.model_validate(conv)
    detail.turns = [ConversationTurnOut.model_validate(t) for t in turns]
    return detail


@router.post("/api/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    body: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """사용자 발화 전송 → 에이전트 응답을 SSE 로 스트리밍.

    스트림 제너레이터는 자체 DB 세션을 열어 사용한다 (요청 의존성 세션은 응답
    반환 시 닫히므로). 소유권 검증은 의존성 세션으로 먼저 끝낸다.
    """
    conv = await _verify_owned_conversation(conversation_id, current_user, db)

    async def event_stream() -> AsyncGenerator[bytes, None]:
        def sse(payload: dict) -> bytes:
            return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")

        async with AsyncSessionLocal() as stream_db:
            try:
                async for ev in chat_service.stream_reply(
                    stream_db, conversation=conv, user_content=body.content,
                ):
                    yield sse(ev)
            except Exception as e:  # noqa: BLE001
                yield sse({"type": "error", "reason": str(e)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        # 프록시(Cloud Run/nginx)가 응답을 버퍼링해 토큰이 한꺼번에 나오는 것을 방지.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
