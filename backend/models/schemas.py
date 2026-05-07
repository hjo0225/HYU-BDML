"""Ditto Pydantic 스키마.

frontend/src/lib/types.ts 와 항상 동기화 유지.
Phase 2 — backend 셸 단계: 기본 인증·프로젝트 스키마만 정의.
Phase 3+ 에서 대화·평가 스키마 추가 예정.
"""
from datetime import datetime
from typing import Any
from pydantic import BaseModel, EmailStr


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
    title: str | None = None


class ResearchProjectOut(BaseModel):
    id: str
    user_id: str
    title: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Agent ──────────────────────────────────────────────────────────────────

class AgentOut(BaseModel):
    id: str
    project_id: str
    source_type: str
    source_ref: str | None
    persona_params: dict[str, Any] | None
    persona_full_prompt: str | None
    cluster: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── EvaluationSnapshot ────────────────────────────────────────────────────

class EvaluationSnapshotOut(BaseModel):
    id: str
    agent_id: str
    version: int
    identity_stats: dict[str, Any] | None
    logic_stats: dict[str, Any] | None
    verdict: str | None
    evaluated_at: datetime

    model_config = {"from_attributes": True}
