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


# ── 실험실 (Lab) — Twin-2K-500 1:1 메신저 ──

class LabTwinBig5(BaseModel):
    """Big5 성격 5차원 — 0~100 percentile."""
    openness: int | None = None
    conscientiousness: int | None = None
    extraversion: int | None = None
    agreeableness: int | None = None
    neuroticism: int | None = None

class LabFaithfulness(BaseModel):
    """트윈별 사전 계산된 충실도 점수 (eval_lab_faithfulness 결과)."""
    overall: float                              # 0.0 ~ 1.0
    by_category: dict[str, float] = Field(default_factory=dict)
    n_eval: int = 0
    evaluated_at: str | None = None             # ISO8601 UTC

class LabProbeQuestion(BaseModel):
    """설문 카테고리 기반 한국어 probe 질문 (사이드바 클릭용).

    `seed_lab_probe_questions.py`가 카테고리당 1문항씩 생성해
    `Panel.scratch["probe_questions"]`에 캐시한 값.
    """
    category: str            # 예: "social_trust", "personality_big5"
    question: str            # 예: "요즘 처음 만난 사람한테 어디까지 마음 여세요?"

class LabTwin(BaseModel):
    """Lab 페이지에 노출되는 Twin 페르소나 카드 / 모달."""
    twin_id: str
    name: str        # 익명화된 표시 이름 (예: "Olivia")
    emoji: str
    age: int | None = None
    age_range: str | None = None  # "30-49" 등
    gender: str | None = None
    occupation: str | None = None
    region: str | None = None
    intro: str       # 1~2문장 짧은 한국어 소개

    # 모달 상세 정보 (Twin-2K-500 persona_summary에서 추출)
    race: str | None = None
    education: str | None = None
    marital_status: str | None = None
    religion: str | None = None
    income: str | None = None
    household_size: str | None = None  # "1", "2", ..., "More than 4" — Twin-2K-500 원본값 유지
    political_views: str | None = None      # Conservative/Liberal/Moderate
    political_affiliation: str | None = None  # Republican/Democrat/Independent
    big5: LabTwinBig5 | None = None
    traits: list[str] = Field(default_factory=list)  # ["high extraversion", ...]
    tags: list[str] = Field(default_factory=list)    # 카드 미리보기용 한국어 키워드 ["외향적", "보수", "기혼", ...]
    aspire: str | None = None  # 이상적 자아 (영어 원문)
    aspire_ko: str | None = None  # 이상적 자아 (한국어 번역)
    actual: str | None = None  # 실제 자아 (영어 원문)
    actual_ko: str | None = None  # 실제 자아 (한국어 번역)
    faithfulness: LabFaithfulness | None = None  # 사전 계산된 충실도 (Lab L1 카드)
    probe_questions: list[LabProbeQuestion] = Field(default_factory=list)  # 설문 기반 질문 사이드바

class LabTwinsResponse(BaseModel):
    twins: list[LabTwin]

class LabChatTurn(BaseModel):
    """클라이언트가 보내는 직전 채팅 히스토리 한 턴."""
    role: Literal["me", "twin"]
    content: str

class LabChatRequest(BaseModel):
    twin_id: str
    history: list[LabChatTurn] = Field(default_factory=list)
    message: str

# ── 인용 / 검증 / 평가 ──────────────────────────────────────────────────
LabConfidence = Literal["direct", "inferred", "guess", "unknown"]
LabVerdict = Literal["consistent", "partial", "contradicts", "evasive"]

class MemoryCitation(BaseModel):
    """답변 근거가 된 PanelMemory 청크 (A+B 하이브리드 결과)."""
    category: str            # 예: "values_environment"
    snippet_en: str          # 영어 원문(최대 ~400 chars 트리밍)
    snippet_ko: str | None = None  # 한국어 의역(없을 수 있음)
    score: float             # 코사인 유사도 (0~1)
    via: Literal["llm_self_cite", "embedding", "both"] = "embedding"

class LabJudgeResponse(BaseModel):
    verdict: LabVerdict
    reason: str
    matched_categories: list[str] = Field(default_factory=list)
    contradicted_categories: list[str] = Field(default_factory=list)
