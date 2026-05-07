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
  persona_params: PersonaParams | null;
  persona_full_prompt: string | null;
  cluster: number | null;
  created_at: string;
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
