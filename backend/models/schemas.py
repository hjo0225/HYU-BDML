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

class ProjectBrief(BaseModel):
    """프로젝트 의뢰서 — 목적·타겟·활용방안. AI 판단 컨텍스트로 사용 (plan 0009)."""
    objective: str | None = Field(default=None, max_length=2000)   # 조사 목적
    target: str | None = Field(default=None, max_length=1000)      # 타겟 소비자
    use_case: str | None = Field(default=None, max_length=2000)    # 결과 활용 방안


class ResearchProjectCreate(BaseModel):
    """프로젝트 생성 입력. title 미입력 시 백엔드가 자동 생성."""
    title: str | None = Field(default=None, max_length=200)
    brief: ProjectBrief | None = None


class ResearchProjectUpdate(BaseModel):
    """PATCH 부분 갱신. 전달된 필드만 반영."""
    title: str | None = Field(default=None, max_length=200)
    status: str | None = Field(default=None, pattern="^(draft|active|archived)$")
    brief: ProjectBrief | None = None


class ResearchProjectOut(BaseModel):
    id: str
    user_id: str
    title: str | None
    status: str
    brief: ProjectBrief | None = None
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
    age_range: str | None = None  # 인구통계 필터용 (scratch 에서 추출)
    gender: str | None = None
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


# ── FGI (다자 회의, plan 0008) ───────────────────────────────────────────────

class SuggestedRound(BaseModel):
    round: int
    subtopic: str
    goal_question: str
    # 자유토론(Phase C)이 수렴할 때 의견을 갈라 재점화할 쟁점 (plan 0012).
    probes: list[str] = Field(default_factory=list)


class CreateFGIRequest(BaseModel):
    """FGI 세션 생성 입력 (project_id 는 경로 파라미터).

    rounds: '라운드별 질문 AI 제안'으로 확정한 라운드 플랜. 진행 엔진이 이 플랜을
    그대로 토론 라운드로 사용한다(plan 0010). 길이가 곧 라운드 수가 된다.
    """
    topic: str = Field(min_length=1)
    agent_ids: list[str] = Field(min_length=1, max_length=6)
    rounds: list[SuggestedRound] = Field(min_length=1, max_length=10)
    allow_user_intervention: bool = True


class SuggestRoundsRequest(BaseModel):
    """회의 주제 → 라운드별 질문 제안 입력 (plan 0009 · item 6)."""
    topic: str = Field(min_length=1)
    n_rounds: int = Field(default=5, ge=1, le=10)


class SuggestRoundsResponse(BaseModel):
    rounds: list[SuggestedRound]


class FGITurnOut(BaseModel):
    id: str
    round: int
    order_in_round: int
    role: str                 # 'moderator' | 'agent' | 'user'
    agent_id: str | None
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class FGISessionOut(BaseModel):
    id: str
    project_id: str
    topic: str
    agent_ids: list[str]
    status: str               # 'running' | 'completed' | 'cancelled'
    minutes_md: str | None
    started_at: datetime
    ended_at: datetime | None = None

    model_config = {"from_attributes": True}


class FGISessionDetailOut(FGISessionOut):
    """세션 메타 + 전체 turn (재로드용)."""
    turns: list[FGITurnOut] = []


class InterveneRequest(BaseModel):
    """user_turn_required 구간의 사용자(기업 관계자) 개입 발언."""
    content: str = Field(min_length=1)


class FGIControlRequest(BaseModel):
    """수동 제어 — 'next_round'(다음 주제로) | 'end_session'(토론 종료)."""
    action: str = Field(pattern="^(next_round|end_session)$")


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
