/* 빅마랩 타입 정의 — backend schemas.py와 동기화 */

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

export interface MarketReport {
  market_overview: string;
  competitive_landscape: string;
  target_analysis: string;
  trends: string;
  implications: string;
  sources: string;
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

export interface AgentSchema {
  id: string;
  type: 'customer' | 'expert' | 'custom';
  name: string;
  emoji: string;
  description: string;
  tags: string[];
  system_prompt: string;
  color: string;
  persona_profile?: PersonaProfile | null;
}

export interface AgentRequest {
  brief: ResearchBrief;
  refined: RefinedResearch;
  report: MarketReport;
}

export interface FitnessCheck {
  label: string;
  status: 'good' | 'warning' | 'poor';
  detail: string;
}

export interface FitnessResult {
  overall: 'good' | 'warning' | 'poor';
  checks: FitnessCheck[];
}

export interface FitnessAIResult {
  score: number;
  summary: string;
  strengths: string[];
  warnings: string[];
  suggestions: string[];
}

export interface FitnessCheckRequest {
  agents: AgentSchema[];
  brief: ResearchBrief;
  report: MarketReport;
}

// ── 회의 ──
export interface MeetingRequest {
  agents: AgentSchema[];
  topic: string;
  research_context: string;
  max_rounds?: number;
}

export interface MeetingMessage {
  role: 'moderator' | 'agent';
  agent_id: string | null;
  agent_name: string;
  agent_emoji: string;
  content: string;
  color: string | null;
}

// ── 회의록 ──
export interface MinutesRequest {
  messages: MeetingMessage[];
  brief: ResearchBrief;
  agents: AgentSchema[];
}

// ── 프로젝트 전체 상태 ──
export interface ProjectData {
  brief: ResearchBrief | null;
  refined: RefinedResearch | null;
  marketReport: MarketReport | null;
  agents: AgentSchema[];
  messages: MeetingMessage[];
  minutes: string | null;
  currentPhase: number;
}
