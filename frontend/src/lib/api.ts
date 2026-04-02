/* 프론트엔드에서 백엔드 API와 스트리밍 응답을 다루는 공통 유틸리티 */
import type {
  ResearchBrief,
  AgentRequest,
  AgentSchema,
  PersonaProfile,
  MeetingRequest,
  MeetingMessage,
  MinutesRequest,
  MarketReport,
  RefinedResearch,
  ReportSection,
  EvidenceItem,
  ThinkingEvent,
} from './types';

// 개발 환경에서는 긴 스트림이 Next.js dev 프록시 제한에 걸릴 수 있어 백엔드를 직접 호출한다.
// 운영 환경에서는 same-origin `/api` 경로를 사용하고 Next.js rewrite가 백엔드로 전달한다.
const API_BASE =
  process.env.NODE_ENV === 'development'
    ? `${process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'}/api`
    : '/api';

type JsonRecord = Record<string, unknown>;

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function toText(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function ensureEvidence(value: unknown): EvidenceItem | null {
  if (!isRecord(value)) return null;
  const url = toText(value.url).trim();
  const title = toText(value.title || value.label || value.name).trim();
  const snippet = toText(value.snippet || value.note || value.description).trim();
  const sourceType = toText(value.source_type).trim();
  const sourceEngine = toText(value.source_engine).trim();
  const publisher = toText(value.publisher).trim();
  const publishedAt = toText(value.published_at || value.publishedAt).trim();
  const relevanceScoreRaw = value.relevance_score;
  const relevanceScore =
    typeof relevanceScoreRaw === 'number' ? relevanceScoreRaw : Number(relevanceScoreRaw || 0);

  if (!url || !title || !sourceType) return null;
  if (!/^https?:\/\//i.test(url)) return null;
  if (!['news', 'webkr', 'blog', 'cafearticle', 'doc'].includes(sourceType)) return null;

  return {
    source_type: sourceType as EvidenceItem['source_type'],
    source_engine:
      sourceEngine === 'naver' || sourceEngine === 'openai_web'
        ? (sourceEngine as EvidenceItem['source_engine'])
        : undefined,
    title,
    url,
    publisher: publisher || undefined,
    published_at: publishedAt || undefined,
    snippet,
    relevance_score: Number.isFinite(relevanceScore) ? relevanceScore : 0,
  };
}


function normalizeReportSection(sectionValue: unknown): ReportSection {
  if (isRecord(sectionValue)) {
    const summary = toText(sectionValue.summary || sectionValue.content || sectionValue.text).trim();
    const rawEvidence = Array.isArray(sectionValue.evidence)
      ? sectionValue.evidence
      : Array.isArray(sectionValue.sources)
      ? sectionValue.sources
      : [];
    const evidence = rawEvidence
      .map(ensureEvidence)
      .filter((item): item is EvidenceItem => item !== null);
    const rawClaims = Array.isArray(sectionValue.key_claims) ? sectionValue.key_claims : [];
    const keyClaims = rawClaims.map(toText).map((item) => item.trim()).filter(Boolean);
    const confidence = toText(sectionValue.confidence).trim();

    return {
      summary,
      key_claims: keyClaims,
      evidence,
      confidence:
        confidence === 'high' || confidence === 'medium' || confidence === 'low'
          ? confidence
          : 'low',
    };
  }

  return {
    summary: toText(sectionValue).trim(),
    key_claims: [],
    evidence: [],
    confidence: 'low',
  };
}

function normalizeRefined(value: unknown, brief: ResearchBrief): RefinedResearch {
  const refined = isRecord(value) ? value : {};

  return {
    refined_background: toText(refined.refined_background).trim() || brief.background,
    refined_objective: toText(refined.refined_objective).trim() || brief.objective,
    refined_usage_plan: toText(refined.refined_usage_plan).trim() || brief.usage_plan,
  };
}

function normalizeReport(value: unknown): MarketReport {
  const report = isRecord(value) ? value : {};

  return {
    market_overview: normalizeReportSection(report.market_overview),
    competitive_landscape: normalizeReportSection(report.competitive_landscape),
    target_analysis: normalizeReportSection(report.target_analysis),
    trends: normalizeReportSection(report.trends),
    implications: normalizeReportSection(report.implications),
  };
}

function buildLegacyResearchPayload(brief: ResearchBrief) {
  return {
    background: brief.background.trim(),
    objective: brief.objective.trim(),
    usage_plan: brief.usage_plan.trim(),
    category: brief.category,
    target_customer: brief.target_customer.trim(),
  };
}

async function parseJsonResponse<T>(res: Response, fallbackMessage: string): Promise<T> {
  const contentType = res.headers.get('content-type') || '';
  const payload = contentType.includes('application/json')
    ? await res.json().catch(() => null)
    : null;

  if (!res.ok) {
    const serverMessage =
      (isRecord(payload) && toText(payload.detail || payload.message || payload.error).trim()) ||
      '';
    throw new Error(serverMessage || `${fallbackMessage}: ${res.status}`);
  }

  if (payload === null) {
    throw new Error(`${fallbackMessage}: 응답 파싱 실패`);
  }

  return payload as T;
}

export type { ThinkingEvent } from './types';

/** Phase 2: 시장조사 스트리밍 — 섹션 완료 시 onSection 콜백 호출 */
export async function fetchResearchStream(
  brief: ResearchBrief,
  onSection: (field: string, content: string) => void,
  onDone: (refined: RefinedResearch, report: MarketReport) => void,
  onThinking?: (event: ThinkingEvent) => void,
  onSectionDelta?: (field: string, delta: string) => void,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/research`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(buildLegacyResearchPayload(brief)),
    });
  } catch {
    throw new Error('시장조사 중 네트워크 오류가 발생했습니다.');
  }

  if (!res.ok) {
    const payload = await res.json().catch(() => null);
    const message =
      (isRecord(payload) && toText(payload.detail || payload.message).trim()) ||
      `시장조사 실패: ${res.status}`;
    throw new Error(message);
  }
  if (!res.body) throw new Error('시장조사 스트림이 비어 있습니다.');

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
      if (!line.trim()) continue;
      let data: JsonRecord;
      try {
        data = JSON.parse(line);
      } catch {
        continue; // 부분적으로 잘린 청크일 수 있으므로 다음 줄을 기다린다.
      }

      if (data.step === 'error') {
        throw new Error(toText(data.message) || '시장조사 오류');
      }
      if (data.step === 'thinking' && onThinking) {
        onThinking({ agent: toText(data.agent) as ThinkingEvent['agent'], query: toText(data.query) });
      }
      if (data.step === 'section_delta' && onSectionDelta) {
        onSectionDelta(toText(data.field), toText(data.delta));
      }
      if (data.step === 'section') {
        onSection(toText(data.field), toText(data.content));
      }
      if (data.step === 'done') {
        onDone(normalizeRefined(data.refined, brief), normalizeReport(data.report));
        return;
      }
    }
  }

  throw new Error('시장조사 실패: 완료 응답을 받지 못했습니다.');
}

/** Phase 2-1: 웹 검색 없이 브리프만 빠르게 정제한다. */
export async function fetchRefinedResearch(brief: ResearchBrief): Promise<RefinedResearch> {
  try {
    const res = await fetch(`${API_BASE}/research/refine`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(buildLegacyResearchPayload(brief)),
    });

    const json = await parseJsonResponse<JsonRecord>(res, '연구 정보 정제 실패');
    return normalizeRefined(json, brief);
  } catch (error) {
    if (error instanceof Error) throw error;
    throw new Error('연구 정보 정제 중 네트워크 오류가 발생했습니다.');
  }
}

function buildBriefFromRefined(brief: ResearchBrief, refined: RefinedResearch): ResearchBrief {
  return {
    background: refined.refined_background.trim(),
    objective: refined.refined_objective.trim(),
    usage_plan: refined.refined_usage_plan.trim(),
    category: brief.category,
    target_customer: brief.target_customer.trim(),
  };
}

/** Phase 2-2: 사용자가 수정한 정제본을 기준으로 시장조사 스트림을 다시 시작한다. */
export async function fetchMarketReportStream(
  brief: ResearchBrief,
  refined: RefinedResearch,
  onSection: (field: string, content: string) => void,
  onDone: (refined: RefinedResearch, report: MarketReport) => void,
  onThinking?: (event: ThinkingEvent) => void,
  onSectionDelta?: (field: string, delta: string) => void,
): Promise<void> {
  return fetchResearchStream(buildBriefFromRefined(brief, refined), onSection, onDone, onThinking, onSectionDelta);
}

/** Phase 3: 에이전트 추천 */
export async function fetchAgents(data: AgentRequest): Promise<AgentSchema[]> {
  try {
    const res = await fetch(`${API_BASE}/agents`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });

    return await parseJsonResponse<AgentSchema[]>(res, '에이전트 추천 실패');
  } catch (error) {
    if (error instanceof Error) throw error;
    throw new Error('에이전트 추천 중 네트워크 오류가 발생했습니다.');
  }
}

/** 회의 스트림에서 새 발언이 시작될 때 전달되는 메타데이터 */
export interface SSEStartEvent {
  type: 'start';
  role: 'moderator' | 'agent';
  agent_id: string | null;
  agent_name: string;
  agent_emoji: string;
  color: string | null;
}

/** Phase 4: SSE를 읽어 start/delta/end 이벤트를 UI 콜백으로 분배한다. */
export async function fetchMeeting(
  data: MeetingRequest,
  onStart: (meta: SSEStartEvent) => void,
  onDelta: (delta: string) => void,
  onEnd: (msg: MeetingMessage) => void,
  onDone: () => void,
  onTopicRefined?: (topic: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  let res: Response;

  try {
    res = await fetch(`${API_BASE}/meeting`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
      signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      return;
    }
    throw new Error('회의 시뮬레이션 중 네트워크 오류가 발생했습니다.');
  }

  if (!res.ok) {
    const contentType = res.headers.get('content-type') || '';
    const payload = contentType.includes('application/json')
      ? await res.json().catch(() => null)
      : null;
    const message =
      (isRecord(payload) && toText(payload.detail || payload.message || payload.error).trim()) ||
      `회의 시뮬레이션 실패: ${res.status}`;
    throw new Error(message);
  }
  if (!res.body) throw new Error('회의 시뮬레이션 스트림이 비어 있습니다.');

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    let done: boolean;
    let value: Uint8Array | undefined;
    try {
      ({ done, value } = await reader.read());
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        return;
      }
      throw error;
    }
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const raw = line.slice(6);
        try {
          const parsed = JSON.parse(raw);
          switch (parsed.type) {
            case 'topic_refined':
              onTopicRefined?.(parsed.topic);
              break;
            case 'start':
              onStart(parsed as SSEStartEvent);
              break;
            case 'delta':
              onDelta(parsed.delta);
              break;
            case 'end':
              onEnd({
                role: parsed.role,
                agent_id: parsed.agent_id ?? null,
                agent_name: parsed.agent_name,
                agent_emoji: parsed.agent_emoji,
                content: parsed.content,
                color: parsed.color ?? null,
              } as MeetingMessage);
              break;
            case 'done':
              onDone();
              return;
          }
        } catch {
          // keepalive나 불완전한 라인은 무시하고 다음 이벤트를 기다린다.
        }
      }
    }
  }

  if (!signal?.aborted) {
    onDone();
  }
}

/** Phase 5: 회의록 생성 */
export async function fetchMinutes(data: MinutesRequest): Promise<string> {
  try {
    // 회의 주제가 있으면 background 앞에 덧붙여 회의록 모델이 현재 논의를 바로 이해하게 한다.
    const brief =
      data.topic?.trim()
        ? {
            ...data.brief,
            background: `회의 주제: ${data.topic.trim()}\n\n${data.brief.background}`,
          }
        : data.brief;

    const res = await fetch(`${API_BASE}/minutes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...data,
        brief,
      }),
    });

    const json = await parseJsonResponse<JsonRecord>(res, '회의록 생성 실패');
    const minutes = toText(json.minutes);
    if (!minutes.trim()) throw new Error('회의록 생성 실패: 응답 본문이 비어 있습니다.');
    return minutes;
  } catch (error) {
    if (error instanceof Error) throw error;
    throw new Error('회의록 생성 중 네트워크 오류가 발생했습니다.');
  }
}

export async function synthesizePrompt(
  name: string,
  type: 'customer' | 'expert' | 'custom',
  persona_profile: PersonaProfile
): Promise<{ system_prompt: string }> {
  try {
    const response = await fetch(`${API_BASE}/agents/synthesize-prompt`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, type, persona_profile }),
    });
    return await parseJsonResponse<{ system_prompt: string }>(response, 'system_prompt 합성 실패');
  } catch (error) {
    if (error instanceof Error) throw error;
    throw new Error('system_prompt 합성 중 네트워크 오류가 발생했습니다.');
  }
}
