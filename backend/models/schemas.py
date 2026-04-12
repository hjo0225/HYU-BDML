"""프론트엔드와 백엔드가 공유하는 핵심 데이터 스키마."""
from typing import Literal
from pydantic import BaseModel, Field

# ── 연구 정보 ──
class ResearchBrief(BaseModel):
    """사용자가 입력하는 원본 연구 브리프."""
    background: str
    objective: str
    usage_plan: str
    category: str
    target_customer: str

class RefinedResearch(BaseModel):
    """시장조사 전에 AI가 다듬은 연구 정보."""
    refined_background: str
    refined_objective: str
    refined_usage_plan: str

class EvidenceItem(BaseModel):
    """시장조사 섹션을 뒷받침하는 개별 근거 문서."""
    source_type: Literal["news", "webkr", "blog", "cafearticle", "doc"]
    source_engine: Literal["naver", "openai_web"] | None = None
    title: str
    url: str
    publisher: str | None = None
    published_at: str | None = None
    snippet: str
    relevance_score: float = 0.0

class ReportSection(BaseModel):
    """시장조사 보고서의 개별 섹션."""
    summary: str
    key_claims: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "low"

    @property
    def content(self) -> str:
        """이전 응답 포맷과 호환되도록 `summary`의 별칭을 제공한다."""
        return self.summary

    @property
    def sources(self) -> list[EvidenceItem]:
        """이전 응답 포맷과 호환되도록 `evidence`의 별칭을 제공한다."""
        return self.evidence

class MarketReport(BaseModel):
    """정제된 브리프를 바탕으로 생성된 최종 시장조사 보고서."""
    market_overview: ReportSection
    competitive_landscape: ReportSection
    target_analysis: ReportSection
    trends: ReportSection
    implications: ReportSection

class ResearchResponse(BaseModel):
    """연구 정제 결과와 시장조사 보고서를 함께 반환하는 응답."""
    refined: RefinedResearch
    report: MarketReport

# ── RAG 에이전트 ──

class AgentDemographics(BaseModel):
    """프론트엔드에 공개되는 요약 인구통계 (raw scratch/memories 미포함)."""
    age_group: str    # 예: "40대"
    gender: str       # 예: "남성"
    occupation: str   # 예: "생산/기술직"
    region: str       # 예: "경기"

class AgentBuildProgressEvent(BaseModel):
    """Phase 3 패널 빌드 SSE 이벤트."""
    type: Literal["build_progress"] = "build_progress"
    step: Literal["selecting", "building", "embedding", "done", "error"]
    current: int
    total: int
    panel_id: str | None = None
    message: str
    agents: list[dict] | None = None  # step=="done"일 때만

class DiscussionQuestion(BaseModel):
    """회의 설계의 단일 토론 질문."""
    order: int
    question: str
    focus_area: str
    rationale: str

class MeetingDesign(BaseModel):
    """Phase 4 회의 시작 전 생성되는 구조화 토론 프레임워크."""
    session_objective: str
    discussion_questions: list[DiscussionQuestion]
    key_themes: list[str]
    moderator_notes: str

# ── 에이전트 ──
class PersonaProfile(BaseModel):
    """참여자 캐릭터를 system prompt로 바꾸기 위한 구조화 프로필."""
    age: int
    gender: Literal["male", "female", "other"]
    occupation: str
    personality: str
    consumption_style: str
    experience: str
    pain_points: str
    communication_style: str

class AgentSchema(BaseModel):
    """회의 참여자 한 명의 최종 정의."""
    id: str
    type: Literal["customer", "expert", "custom"]
    name: str
    emoji: str
    description: str
    tags: list[str]
    system_prompt: str
    color: str
    persona_profile: PersonaProfile | None = None
    # RAG 기반 실제 패널 필드 (panel_id가 있으면 RAG 모드)
    panel_id: str | None = None
    demographics: AgentDemographics | None = None
    memory_count: int | None = None

class AgentRequest(BaseModel):
    """에이전트 추천에 필요한 전체 입력 묶음."""
    brief: ResearchBrief
    refined: RefinedResearch
    report: MarketReport

class AgentStreamRequest(BaseModel):
    """주제 인식 에이전트 스트림 요청 — RAG 패널 / LLM 가상 모드 분기."""
    brief: ResearchBrief
    refined: RefinedResearch
    report: MarketReport
    topic: str = ""
    mode: Literal["rag", "llm"] = "rag"

class SynthesizePromptRequest(BaseModel):
    """저장된 페르소나를 다시 system prompt로 합성할 때 사용하는 요청."""
    name: str
    type: Literal["customer", "expert", "custom"]
    persona_profile: PersonaProfile

# ── 회의 ──
class MeetingRequest(BaseModel):
    """회의 시뮬레이션 시작 요청."""
    agents: list[AgentSchema]
    topic: str
    research_context: str
    max_rounds: int = 5
    # RAG 모드: {agent.id: panel_id} 맵 (에이전트별 분기에 사용)
    panel_ids: dict[str, str] = Field(default_factory=dict)

class MeetingMessage(BaseModel):
    """회의 로그에 저장되는 개별 발언."""
    role: Literal["moderator", "agent"]
    agent_id: str | None = None
    agent_name: str
    agent_emoji: str
    content: str
    color: str | None = None
    # RAG 에이전트 발화 시 검색된 메모리 수 (텍스트 미포함)
    retrieved_memory_count: int | None = None

# ── 회의록 ──
class MinutesRequest(BaseModel):
    """회의 로그를 회의록 문서로 정리하기 위한 입력."""
    messages: list[MeetingMessage]
    brief: ResearchBrief
    agents: list[AgentSchema]
