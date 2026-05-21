"""Ditto Pydantic 스키마.

frontend/src/lib/types.ts 와 항상 동기화 유지.
Slice 1.2 — ResearchProject CRUD + Agent 목록/상세 스키마 추가.
"""
from datetime import datetime
from typing import Any
from pydantic import BaseModel, EmailStr, Field


# ── 인증 ──────────────────────────────────────────────────────────────────

class UserOut(BaseModel):
    id: str
    email: str
    name: str | None
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ── ResearchProject ────────────────────────────────────────────────────────

class ResearchProjectCreate(BaseModel):
    """프로젝트 생성 입력. title 미입력 시 백엔드가 자동 생성."""
    title: str | None = Field(default=None, max_length=200)


class ResearchProjectUpdate(BaseModel):
    """PATCH 부분 갱신. 전달된 필드만 반영."""
    title: str | None = Field(default=None, max_length=200)
    status: str | None = Field(default=None, pattern="^(draft|active|archived)$")


class ResearchProjectOut(BaseModel):
    id: str
    user_id: str
    title: str | None
    status: str
    created_at: datetime
    updated_at: datetime | None = None
    agent_count: int = 0  # 카드 표시용 — 라우터에서 채워줌

    model_config = {"from_attributes": True}


# ── Agent ──────────────────────────────────────────────────────────────────

class AgentOut(BaseModel):
    """에이전트 카드용 목록 응답 — persona_full_prompt 제외(상세에서만)."""
    id: str
    project_id: str
    source_type: str          # 'twin' | 'survey'
    source_ref: str | None
    display_name: str | None
    emoji: str | None
    intro_ko: str | None
    persona_params: dict[str, Any] | None
    cluster: int | None
    summary: str | None = None  # 카드용 short summary (agent_service.short_summary)
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentDetailOut(AgentOut):
    """에이전트 상세 — persona_full_prompt + scratch 포함."""
    persona_full_prompt: str | None
    scratch: dict[str, Any] | None
    updated_at: datetime | None


# ── Conversation (1:1 대화, plan 0007) ──────────────────────────────────────

class ConversationCreate(BaseModel):
    """대화 세션 생성 입력 (agent_id 는 경로 파라미터)."""
    title: str | None = Field(default=None, max_length=200)


class ConversationTurnOut(BaseModel):
    id: str
    role: str            # 'user' | 'agent'
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationOut(BaseModel):
    id: str
    project_id: str
    agent_id: str
    title: str | None
    started_at: datetime
    ended_at: datetime | None = None

    model_config = {"from_attributes": True}


class ConversationDetailOut(ConversationOut):
    """대화 메타 + 전체 turn (재로드용)."""
    turns: list[ConversationTurnOut] = []


class ChatMessageRequest(BaseModel):
    """사용자 발화 — 에이전트 응답을 SSE 로 스트리밍."""
    content: str = Field(min_length=1)


# ── EvaluationSnapshot ────────────────────────────────────────────────────

class EvaluationSnapshotOut(BaseModel):
    id: str
    agent_id: str
    version: int
    identity_stats: dict[str, Any] | None
    logic_stats: dict[str, Any] | None
    verdict: str | None
    eval_config: dict[str, Any] | None = None
    evaluated_at: datetime

    model_config = {"from_attributes": True}
