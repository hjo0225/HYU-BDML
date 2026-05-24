/**
 * Ditto Frontend 타입 정의
 * backend/models/schemas.py 와 항상 동기화 유지
 */

// ── 인증 ──────────────────────────────────────────────────────────────────
export interface User {
  id: string;
  email: string;
  name: string | null;
  role: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

// ── ResearchProject ────────────────────────────────────────────────────────
/** 프로젝트 의뢰서 — 목적·타겟·활용방안 (AI 판단 컨텍스트). */
export interface ProjectBrief {
  objective?: string | null;  // 조사 목적
  target?: string | null;     // 타겟 소비자
  use_case?: string | null;   // 결과 활용 방안
}

export interface ResearchProject {
  id: string;
  user_id: string;
  title: string | null;
  status: 'draft' | 'active' | 'archived';
  brief: ProjectBrief | null;
  created_at: string;
  updated_at: string | null;
  agent_count: number;
}

export interface ResearchProjectCreate {
  title?: string;
  brief?: ProjectBrief;
}

export interface ResearchProjectUpdate {
  title?: string;
  status?: 'draft' | 'active' | 'archived';
  brief?: ProjectBrief;
}

// ── Agent ──────────────────────────────────────────────────────────────────
export interface PersonaParams {
  [key: string]: number | string | null;
}

export interface Agent {
  id: string;
  project_id: string;
  source_type: 'twin' | 'survey' | 'package';
  source_ref: string | null;
  display_name: string | null;
  emoji: string | null;
  intro_ko: string | null;
  persona_params: PersonaParams | null;
  cluster: number | null;
  age_range: string | null;  // 인구통계 필터용 (scratch 에서 추출)
  gender: string | null;
  summary: string | null;
  created_at: string;
}

export interface AgentDetail extends Agent {
  persona_full_prompt: string | null;
  scratch: Record<string, unknown> | null;
  updated_at: string | null;
}

export interface AgentListQuery {
  source_type?: 'twin' | 'survey' | 'package';
  cluster?: number;
  params?: string;  // 'l1.risk_aversion:0.3-0.7,l2.maximization:3.0-5.0'
  limit?: number;
  offset?: number;
}

// ── AgentMemory ───────────────────────────────────────────────────────────
export interface AgentMemory {
  id: number;
  agent_id: string;
  source: 'base' | 'conversation' | 'fgi';
  category: string;
  text: string;
  importance: number;
  created_at: string;
}

// ── EvaluationSnapshot ────────────────────────────────────────────────────
export interface IdentityStats {
  // V1 (Slice 2)
  sync?: number;
  v1_n_eval?: number;
  // V3 (Slice 2)
  distinct?: number;
  v3_n_agents?: number;
  pca_x?: number;
  pca_y?: number;
  // V2 (후속)
  stability?: number;
}

export interface LogicStats {
  humanity?: number;
  reasoning_delta?: number;
}

export type EvaluationVerdict =
  | 'verified_s3'
  | 'verified_partial'
  | 'partial'
  | 'failed'
  | 'pending';

export interface EvaluationSnapshot {
  id: string;
  agent_id: string;
  version: number;
  identity_stats: IdentityStats | null;
  logic_stats: LogicStats | null;
  verdict: EvaluationVerdict | null;
  eval_config: Record<string, unknown> | null;
  evaluated_at: string;
}

// ── 평가 트리거·산점도 ────────────────────────────────────────────────────

export interface EvaluateRequest {
  metrics: ('v1' | 'v3')[];  // Slice 2 범위. v2/v4/v5 는 후속에서 처리.
  mock_llm?: boolean | null;
  synthetic_embeddings?: boolean | null;
}

export type EvaluateEvent =
  | { type: 'trigger_meta'; project_id: string; triggered_by_agent_id: string; metrics: string[] }
  | { type: 'start'; total: number; metrics: string[] }
  | { type: 'agent_start'; current: number; total: number; agent_id: string }
  | { type: 'agent_done'; current: number; total: number; agent_id: string; v1_sync?: number }
  | { type: 'v3_done'; distinct: number; n_agents: number }
  | { type: 'done'; snapshots: number }
  | { type: 'result'; status: string; snapshots: Record<string, string>; distinct?: number }
  | { type: 'error'; agent_id?: string; reason: string };

export interface ScatterPoint {
  agent_id: string;
  display_name: string | null;
  emoji: string | null;
  cluster: number | null;
  x: number;
  y: number;
  sync: number | null;
}

export interface ScatterResponse {
  distinct: number | null;
  /** 0~1 정규화 다양성 점수 (distinct / 0.47 상한). 대시보드 표기용. */
  distinct_norm: number | null;
  n_points: number;
  points: ScatterPoint[];
}

// ── Conversation (1:1 대화, plan 0007) ──────────────────────────────────────
export interface ConversationTurn {
  id: string;
  role: 'user' | 'agent';
  content: string;
  created_at: string;
}

export interface Conversation {
  id: string;
  project_id: string;
  agent_id: string;
  title: string | null;
  started_at: string;
  ended_at: string | null;
}

export interface ConversationDetail extends Conversation {
  turns: ConversationTurn[];
}

export interface ConversationCreate {
  title?: string;
}

export interface MemoryCitation {
  category: string;
  snippet: string;
  score: number;
  via: 'llm_self_cite' | 'embedding' | 'both';
}

/** /api/conversations/{id}/messages SSE 이벤트 (api-spec.md). */
export type ChatStreamEvent =
  | { type: 'start'; conversation_id: string; agent_id: string }
  | { type: 'delta'; delta: string }
  | {
      type: 'end';
      turn_id: string;
      content: string;
      citations: MemoryCitation[];   // PoC: 빈 배열
      confidence: 'direct' | 'inferred' | 'guess' | 'unknown';
    }
  | { type: 'error'; reason: string };

// ── FGI (다자 회의, plan 0008) ───────────────────────────────────────────────
export interface FGITurn {
  id: string;
  round: number;
  order_in_round: number;
  role: 'moderator' | 'agent' | 'user';
  agent_id: string | null;
  content: string;
  created_at: string;
}

export interface FGISession {
  id: string;
  project_id: string;
  topic: string;
  agent_ids: string[];
  status: 'running' | 'completed' | 'cancelled';
  minutes_md: string | null;
  started_at: string;
  ended_at: string | null;
}

export interface FGISessionDetail extends FGISession {
  turns: FGITurn[];
}

export interface CreateFGIRequest {
  topic: string;
  agent_ids: string[];
  rounds: SuggestedRound[];          // 확정된 라운드별 질문 제안 = 토론 플랜 (plan 0010)
  allow_user_intervention?: boolean; // 기본 true
}

export interface InterveneRequest {
  content: string;
}

/** 라운드별 질문 제안 (plan 0009 · item 6). */
export interface SuggestRoundsRequest {
  topic: string;
  n_rounds?: number;  // 기본 5
}

export interface SuggestedRound {
  round: number;
  subtopic: string;
  goal_question: string;
  probes?: string[];  // 자유토론 수렴 시 의견을 가를 쟁점 (plan 0012)
}

export interface SuggestRoundsResponse {
  rounds: SuggestedRound[];
}

/** 구조화 인사이트 보고서 (FGI v2 · plan 0008). minutes_md 에 JSON 문자열로도 저장. */
export interface FGIReport {
  topic: string;
  meta: { date: string; n_agents: number; n_rounds: number; duration_min: number | null };
  key_insights: { title: string; description: string; sources: string[] }[];
  agent_perspectives: { name: string; stance: string; key_quote: string }[];
  round_analysis: { round: number; title: string; summary: string }[];
  action_items: { title: string; description: string; expected_effect: string }[];
}

/** /api/fgi-sessions/{id}/run SSE 이벤트 (api-spec.md). */
export type FGIStreamEvent =
  | { type: 'round_start'; round: number; subtopic?: string; goal_question?: string }
  | { type: 'moderator'; round: number; content: string; follow_up?: boolean }
  | { type: 'agent_delta'; agent_id: string; delta: string }
  | {
      type: 'agent_end';
      agent_id: string;
      turn_id: string;
      content: string;
      citations: MemoryCitation[];
      confidence: string;
      engagement?: Record<string, number>;
    }
  | { type: 'user_turn_required'; round: number; deadline_seconds: number; remaining?: number }
  | { type: 'round_end'; round: number; summary: string }
  | { type: 'session_end'; report: FGIReport; minutes_md: string }
  | { type: 'error'; reason: string };

// ── API 응답 ──────────────────────────────────────────────────────────────
export interface ApiError {
  detail: string;
}
