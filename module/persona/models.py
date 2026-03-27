"""Phase 2 Pydantic 데이터 모델."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class RoleCard(BaseModel):
    """Step A 출력: 역할 1장."""

    id: str = Field(..., description="snake_case 고유 ID")
    role: str = Field(..., description="한글 역할명")
    why_needed: str = Field(..., description="필요한 이유 1~2문장")
    covers_frames: list[str] = Field(default_factory=list, description="커버하는 research_frame 항목")


class RolesOutput(BaseModel):
    """Step A 전체 출력."""

    roles: list[RoleCard] = Field(default_factory=list)


class PersonaCard(BaseModel):
    """Step B 출력: 페르소나 카드 1장."""

    id: str
    role: str
    expertise: list[str] = Field(default_factory=list)
    personality: str = ""
    speech_style: str = ""
    agenda_knowledge: str = ""
    goal_in_meeting: str = ""
    system_prompt: str = ""


class PersonaOutput(BaseModel):
    """Phase 2 최종 출력."""

    project_name: str
    topic: str
    purpose: str
    meeting_agenda: str = ""
    personas: list[PersonaCard] = Field(default_factory=list)
    discussion_seeds: list[str] = Field(default_factory=list)


class PersonaApproveRequest(BaseModel):
    """역할 승인/수정 요청."""

    approved: bool = False
    feedback: Optional[str] = None
