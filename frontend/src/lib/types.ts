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
}

// ── 회의록 ──
export interface MinutesRequest {
  messages: MeetingMessage[];
  brief: ResearchBrief;
  agents: AgentSchema[];
  topic?: string;
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
