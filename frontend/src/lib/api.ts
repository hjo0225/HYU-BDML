/**
 * Ditto API 클라이언트
 * 모든 API 호출은 이 모듈을 통해야 한다.
 */
import type {
  Agent,
  AgentDetail,
  AgentListQuery,
  ResearchProject,
  ResearchProjectCreate,
  ResearchProjectUpdate,
} from './types';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

// ── 기본 fetch 래퍼 ───────────────────────────────────────────────────────

interface FetchOptions extends RequestInit {
  token?: string;
}

async function apiFetch<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const { token, ...rest } = options;
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...rest.headers,
  };

  const res = await fetch(`${BACKEND_URL}${path}`, { ...rest, headers, credentials: 'include' });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const err = await res.json();
      detail = err.detail || JSON.stringify(err);
    } catch {}
    throw new Error(detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

// ── SSE / NDJSON 스트리밍 ─────────────────────────────────────────────────

export async function* streamFetch(
  path: string,
  body: object,
  token?: string,
): AsyncGenerator<Record<string, unknown>> {
  const res = await fetch(`${BACKEND_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    credentials: 'include',
    body: JSON.stringify(body),
  });

  if (!res.ok || !res.body) throw new Error(`Stream 오류: ${res.statusText}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';
    for (const line of lines) {
      const trimmed = line.replace(/^data:\s*/, '').trim();
      if (trimmed && trimmed !== '[DONE]') {
        try { yield JSON.parse(trimmed); } catch {}
      }
    }
  }
}

// ── 인증 ──────────────────────────────────────────────────────────────────

export const auth = {
  register: (email: string, password: string, name?: string) =>
    apiFetch<{ access_token: string; user: { id: string; email: string; name: string | null; role: string } }>(
      '/api/auth/register',
      { method: 'POST', body: JSON.stringify({ email, password, name }) },
    ),

  login: (email: string, password: string) =>
    apiFetch<{ access_token: string; user: { id: string; email: string; name: string | null; role: string } }>(
      '/api/auth/login',
      { method: 'POST', body: JSON.stringify({ email, password }) },
    ),

  refresh: () =>
    apiFetch<{ access_token: string; user: { id: string; email: string; name: string | null; role: string } }>(
      '/api/auth/refresh',
      { method: 'POST' },
    ),

  logout: () => apiFetch('/api/auth/logout', { method: 'POST' }),

  googleLogin: () => {
    window.location.href = `${BACKEND_URL}/api/auth/google`;
  },

  me: (token: string) =>
    apiFetch<{ id: string; email: string; name: string | null; role: string }>(
      '/api/auth/me', { token }),
};

// ── 프로젝트 ──────────────────────────────────────────────────────────────

export const projects = {
  list: (token: string, opts?: { limit?: number; offset?: number; status?: 'draft' | 'active' | 'archived' }) => {
    const qs = new URLSearchParams();
    if (opts?.limit !== undefined) qs.set('limit', String(opts.limit));
    if (opts?.offset !== undefined) qs.set('offset', String(opts.offset));
    if (opts?.status) qs.set('status', opts.status);
    const path = qs.toString() ? `/api/projects?${qs}` : '/api/projects';
    return apiFetch<ResearchProject[]>(path, { token });
  },

  create: (token: string, body: ResearchProjectCreate) =>
    apiFetch<ResearchProject>('/api/projects', {
      method: 'POST',
      token,
      body: JSON.stringify(body),
    }),

  get: (token: string, id: string) =>
    apiFetch<ResearchProject>(`/api/projects/${id}`, { token }),

  update: (token: string, id: string, body: ResearchProjectUpdate) =>
    apiFetch<ResearchProject>(`/api/projects/${id}`, {
      method: 'PATCH',
      token,
      body: JSON.stringify(body),
    }),

  remove: (token: string, id: string) =>
    apiFetch<void>(`/api/projects/${id}`, { method: 'DELETE', token }),
};

// ── 에이전트 ──────────────────────────────────────────────────────────────

export const agents = {
  list: (token: string, projectId: string, opts?: AgentListQuery) => {
    const qs = new URLSearchParams();
    if (opts?.source_type) qs.set('source_type', opts.source_type);
    if (opts?.cluster !== undefined) qs.set('cluster', String(opts.cluster));
    if (opts?.params) qs.set('params', opts.params);
    if (opts?.limit !== undefined) qs.set('limit', String(opts.limit));
    if (opts?.offset !== undefined) qs.set('offset', String(opts.offset));
    const base = `/api/projects/${projectId}/agents`;
    const path = qs.toString() ? `${base}?${qs}` : base;
    return apiFetch<Agent[]>(path, { token });
  },

  get: (token: string, agentId: string) =>
    apiFetch<AgentDetail>(`/api/agents/${agentId}`, { token }),
};
