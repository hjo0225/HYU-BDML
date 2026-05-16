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
  v1_response_sync?: number;
  v2_model_stability?: number;
  v3_persona_diversity?: number;
}

export interface LogicStats {
  v4_humanity_score?: number;
  v5_reasoning_delta?: number;
}

export interface EvaluationSnapshot {
  id: string;
  agent_id: string;
  version: number;
  identity_stats: IdentityStats | null;
  logic_stats: LogicStats | null;
  verdict: string | null;
  evaluated_at: string;
}

// ── API 응답 ──────────────────────────────────────────────────────────────
export interface ApiError {
  detail: string;
}
