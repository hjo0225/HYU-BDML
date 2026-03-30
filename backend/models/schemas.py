"""Pydantic 스키마 정의"""
from pydantic import BaseModel
from typing import Literal

# ── 연구 정보 ──
class ResearchBrief(BaseModel):
    """Phase 1: 사용자 입력 연구 정보"""
    background: str
    objective: str
    usage_plan: str
    category: str
    target_customer: str

class RefinedResearch(BaseModel):
    """Phase 2: AI 고도화된 연구 정보"""
    refined_background: str
    refined_objective: str
    refined_usage_plan: str

class MarketReport(BaseModel):
    """Phase 2: 시장조사 보고서"""
    market_overview: str
    competitive_landscape: str
    target_analysis: str
    trends: str
    implications: str
    sources: str

class ResearchResponse(BaseModel):
    """Phase 2: 시장조사 전체 응답"""
    refined: RefinedResearch
    report: MarketReport

# ── 에이전트 ──
class AgentSchema(BaseModel):
    """Phase 3: 에이전트 정보"""
    id: str
    type: Literal["customer", "expert", "custom"]
    name: str
    emoji: str
    description: str
    tags: list[str]
    system_prompt: str
    color: str

class AgentRequest(BaseModel):
    """Phase 3: 에이전트 추천 요청"""
    refined: RefinedResearch
    report: MarketReport

# ── 회의 ──
class MeetingRequest(BaseModel):
    """Phase 4: 회의 시뮬레이션 요청"""
    agents: list[AgentSchema]
    topic: str
    research_context: str

class MeetingMessage(BaseModel):
    """Phase 4: 회의 메시지"""
    role: Literal["moderator", "agent"]
    agent_id: str | None = None
    agent_name: str
    agent_emoji: str
    content: str
    color: str | None = None

# ── 회의록 ──
class MinutesRequest(BaseModel):
    """Phase 5: 회의록 생성 요청"""
    messages: list[MeetingMessage]
    brief: ResearchBrief
    agents: list[AgentSchema]
