"""Pydantic 데이터 모델."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class InputA(BaseModel):
    """사용자 최소 입력."""

    project_name: str = Field(..., description="프로젝트명 (raw/ 하위 폴더명)")
    topic: str = Field(..., description="조사 주제")
    purpose: str = Field(..., description="용도: interview_prep | report_context")
    target_audience: Optional[str] = Field(None, description="인터뷰 대상 / 타겟 세그먼트")
    constraints: Optional[str] = Field(None, description="범위 제한")
    known_info: Optional[str] = Field(None, description="이미 아는 정보")
    gaps: Optional[list[str]] = Field(None, description="알고 싶은 것 (최우선 검색 대상)")


class InputB(BaseModel):
    """LLM이 보강한 구조화된 입력."""

    topic: str
    purpose: str
    context: dict = Field(default_factory=dict)
    research_frame: list[str] = Field(default_factory=list)
    constraints: dict = Field(default_factory=dict)


class SourceInfo(BaseModel):
    """수집된 출처."""

    url: str
    title: str
    snippet: str
    content: Optional[str] = None
    reliability: str = "unverified"


class ResearchOutput(BaseModel):
    """최종 출력."""

    topic: str
    purpose: str
    research_frame: dict = Field(default_factory=dict)
    gaps_remaining: list[str] = Field(default_factory=list)
    sources: list[SourceInfo] = Field(default_factory=list)
    summary_report: str = ""


class ApproveRequest(BaseModel):
    """승인/수정 요청."""

    approved: bool = False
    feedback: Optional[str] = None
