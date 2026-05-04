/* 빅마랩 타입 정의 — backend schemas.py와 동기화 */

export interface ThinkingEvent {
  agent: 'researcher' | 'fact_checker';
  query: string;
}

// ── 연구 정보 ──
export interface ResearchBrief {
  background: string;
  objective: string;
  usage_plan: string;
  category: string;
  target_customer: string;
}

export interface RefinedResearch {
  refined_background: string;
  refined_objective: string;
  refined_usage_plan: string;
}

export interface EvidenceItem {
  source_type: 'news' | 'webkr' | 'blog' | 'cafearticle' | 'doc';
  source_engine?: 'naver' | 'openai_web';
  title: string;
  url: string;
  publisher?: string;
  published_at?: string;
  snippet: string;
  relevance_score: number;
}

export interface ReportSection {
  summary: string;
  key_claims: string[];
  evidence: EvidenceItem[];
  confidence: 'high' | 'medium' | 'low';
}

export interface MarketReport {
  market_overview: ReportSection;
  competitive_landscape: ReportSection;
  target_analysis: ReportSection;
  trends: ReportSection;
  implications: ReportSection;
}

export interface ResearchResponse {
  refined: RefinedResearch;
  report: MarketReport;
}

// ── 에이전트 ──
export interface PersonaProfile {
  age: number;
  gender: 'male' | 'female' | 'other';
  occupation: string;
  personality: string;
  consumption_style: string;
  experience: string;
  pain_points: string;
  communication_style: string;
}

/** agent_project 기반 실제 패널 데이터 — UI에 공개할 요약 인구통계 */
export interface AgentDemographics {
  age_group: string;   // 예: "40대"
  gender: string;      // 예: "여성"
  occupation: string;  // 예: "자영업"
  region: string;      // 예: "서울"
}

/** agent_project memory_builder 산출물 — 에피소드 기억 단위 */
export interface Memory {
  text: string;
  importance: number;  // 0~10
}

export interface AgentSchema {
  id: string;
  type: 'customer' | 'expert' | 'custom';
  name: string;
  emoji: string;
  description: string;
  tags: string[];
  system_prompt: string;
  color: string;
  // 기존 LLM 생성 페르소나 (하위 호환)
  persona_profile?: PersonaProfile | null;
  // agent_project 기반 실제 패널 데이터
  panel_id?: string;
  cluster_id?: string;
  demographics?: AgentDemographics;
  memories?: Memory[];
  memory_count?: number;
  data_categories?: string[];
}

export interface AgentRequest {
  brief: ResearchBrief;
  refined: RefinedResearch;
  report: MarketReport;
}

/** 에이전트 생성 모드: RAG 실제 패널 / LLM 가상 에이전트 */
export type AgentMode = 'rag' | 'llm';

export interface AgentStreamRequest {
  brief: ResearchBrief;
  refined: RefinedResearch;
  report: MarketReport;
  topic: string;
  mode: AgentMode;
}

// ── 회의 설계 ──
export interface DiscussionQuestion {
  order: number;
  question: string;
  focus_area: string;
  rationale: string;
}

export interface MeetingDesign {
  session_objective: string;
  discussion_questions: DiscussionQuestion[];
  key_themes: string[];
  moderator_notes: string;
}

// ── 회의 ──
export interface MeetingRequest {
  agents: AgentSchema[];
  topic: string;
  research_context: string;
  max_rounds?: number;
  panel_ids?: Record<string, string>;
}

export interface MeetingMessage {
  role: 'moderator' | 'agent';
  agent_id: string | null;
  agent_name: string;
  agent_emoji: string;
  content: string;
  color: string | null;
  /** RAG 검색에서 활성화된 메모리 개수 */
  retrieved_memory_count?: number;
  /** RAG 발언의 근거 데이터 카테고리 */
  activated_categories?: string[];
}

// ── 회의록 ──
export interface MinutesRequest {
  messages: MeetingMessage[];
  brief: ResearchBrief;
  agents: AgentSchema[];
  topic?: string;
}

// ── 실험실 (Lab) — Twin-2K-500 1:1 메신저 ──
export interface LabTwinBig5 {
  openness: number | null;
  conscientiousness: number | null;
  extraversion: number | null;
  agreeableness: number | null;
  neuroticism: number | null;
}

/** 사전 계산된 트윈 충실도 (eval_lab_faithfulness 결과) */
export interface LabFaithfulness {
  overall: number;                       // 0~1
  by_category: Record<string, number>;
  n_eval: number;
  evaluated_at?: string | null;
}

/** 설문 카테고리 기반 한국어 probe 질문 (사이드바 클릭용) */
export interface LabProbeQuestion {
  category: string;
  question: string;
}

export interface LabTwin {
  twin_id: string;
  name: string;
  emoji: string;
  age: number | null;
  age_range: string | null;
  gender: string | null;
  occupation: string | null;
  region: string | null;
  intro: string;
  race: string | null;
  education: string | null;
  marital_status: string | null;
  religion: string | null;
  income: string | null;
  household_size: string | null;
  political_views: string | null;
  political_affiliation: string | null;
  big5: LabTwinBig5 | null;
  traits: string[];
  tags: string[];
  aspire: string | null;
  aspire_ko: string | null;
  actual: string | null;
  actual_ko: string | null;
  faithfulness?: LabFaithfulness | null;
  probe_questions?: LabProbeQuestion[];
}

export interface LabTwinsResponse {
  twins: LabTwin[];
}

/**
 * 단일 Twin 상세 — 카드 + 풀 페르소나 원본(JSON 텍스트).
 *
 * `persona_full`은 Toubia 풀-프롬프트로 시스템 프롬프트에 그대로 주입된
 * persona_json 문자열(~170k chars). 채팅 페이지 우측 "에이전트 입력값"
 * 패널이 JSON.parse 후 사람이 읽기 좋은 섹션으로 펼쳐 보여준다.
 */
export interface LabTwinDetail extends LabTwin {
  persona_full: string | null;
}

export type LabChatRole = 'me' | 'twin';

export interface LabChatTurn {
  role: LabChatRole;
  content: string;
}

export interface LabChatRequest {
  twin_id: string;
  history: LabChatTurn[];
  message: string;
}

export interface LabChatStartEvent {
  type: 'start';
  twin_id: string;
  name: string;
}

export type LabConfidence = 'direct' | 'inferred' | 'guess' | 'unknown';
export type LabCitationVia = 'llm_self_cite' | 'embedding' | 'both';

/** 답변 한 턴의 인용 근거 (A+B 하이브리드 결과) */
export interface MemoryCitation {
  category: string;
  snippet_en: string;
  snippet_ko: string | null;
  score: number;
  via: LabCitationVia;
}

/** SSE end 페이로드 — 본문 + 인용 + 신뢰도 */
export interface LabChatEndPayload {
  content: string;
  citations: MemoryCitation[];
  confidence: LabConfidence;
}

// ── 프로젝트 전체 상태 ──
export interface ProjectData {
  brief: ResearchBrief | null;
  refined: RefinedResearch | null;
  marketReport: MarketReport | null;
  agents: AgentSchema[];
  agentMode: AgentMode | null;
  meetingTopic: string | null;
  messages: MeetingMessage[];
  minutes: string | null;
  currentPhase: number;
}
