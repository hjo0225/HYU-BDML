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
export interface ResearchProject {
  id: string;
  user_id: string;
  title: string | null;
  status: 'draft' | 'active' | 'archived';
  created_at: string;
  updated_at: string | null;
  agent_count: number;
}

export interface ResearchProjectCreate {
  title?: string;
}

export interface ResearchProjectUpdate {
  title?: string;
  status?: 'draft' | 'active' | 'archived';
}

// ── Agent ──────────────────────────────────────────────────────────────────
export interface PersonaParams {
  [key: string]: number | string | null;
}

export interface Agent {
  id: string;
  project_id: string;
  source_type: 'twin' | 'survey';
  source_ref: string | null;
  display_name: string | null;
  emoji: string | null;
  intro_ko: string | null;
  persona_params: PersonaParams | null;
  cluster: number | null;
  summary: string | null;
  created_at: string;
}

export interface AgentDetail extends Agent {
  persona_full_prompt: string | null;
  scratch: Record<string, unknown> | null;
  updated_at: string | null;
}

export interface AgentListQuery {
  source_type?: 'twin' | 'survey';
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
  n_points: number;
  points: ScatterPoint[];
}

// ── API 응답 ──────────────────────────────────────────────────────────────
export interface ApiError {
  detail: string;
}
