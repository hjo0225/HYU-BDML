/* 빅마랩 API 호출 유틸리티 */
import type {
  ResearchBrief,
  ResearchResponse,
  AgentRequest,
  AgentSchema,
  PersonaProfile,
  MeetingRequest,
  MeetingMessage,
  MinutesRequest,
  MarketReport,
  RefinedResearch,
  ReportSection,
  ReportSource,
} from './types';

// 개발환경: Next.js 프록시 30초 타임아웃 우회를 위해 백엔드 직접 연결
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

function ensureSource(value: unknown): ReportSource | null {
  if (typeof value === 'string') {
    const label = value.trim();
    return label ? { label } : null;
  }

  if (!isRecord(value)) return null;

  const label =
    toText(value.label) ||
    toText(value.title) ||
    toText(value.name) ||
    toText(value.url);

  if (!label.trim()) return null;

  const source: ReportSource = { label: label.trim() };
  const url = toText(value.url).trim();
  const publisher = toText(value.publisher).trim();
  const publishedAt = toText(value.published_at || value.publishedAt).trim();
  const note = toText(value.note).trim();

  if (url) source.url = url;
  if (publisher) source.publisher = publisher;
  if (publishedAt) source.published_at = publishedAt;
  if (note) source.note = note;

  return source;
}

function parseLegacySources(value: unknown): ReportSource[] {
  if (Array.isArray(value)) {
    return value.map(ensureSource).filter((item): item is ReportSource => item !== null);
  }

  if (typeof value !== 'string') return [];

  return value
    .split(/\n+/)
    .map((line) => line.replace(/^[-*•\d.\s]+/, '').trim())
    .filter(Boolean)
    .map((label) => ({ label }));
}

function normalizeReportSection(sectionValue: unknown, fallbackSources: ReportSource[]): ReportSection {
  if (isRecord(sectionValue)) {
    const content = toText(sectionValue.content || sectionValue.summary || sectionValue.text).trim();
    const rawSources = Array.isArray(sectionValue.sources) ? sectionValue.sources : [];
    const sources = rawSources
      .map(ensureSource)
      .filter((item): item is ReportSource => item !== null);

    return {
      content,
      sources: sources.length > 0 ? sources : fallbackSources,
    };
  }

  return {
    content: toText(sectionValue).trim(),
    sources: fallbackSources,
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
  const fallbackSources = parseLegacySources(report.sources);

  return {
    market_overview: normalizeReportSection(report.market_overview, fallbackSources),
    competitive_landscape: normalizeReportSection(report.competitive_landscape, fallbackSources),
    target_analysis: normalizeReportSection(report.target_analysis, fallbackSources),
    trends: normalizeReportSection(report.trends, fallbackSources),
    implications: normalizeReportSection(report.implications, fallbackSources),
  };
}

function formatReportSource(source: ReportSource): string {
  return [
    source.label,
    source.publisher,
    source.published_at,
    source.url,
    source.note,
  ]
    .filter(Boolean)
    .join(' | ');
}

function serializeMarketReportForBackend(report: MarketReport) {
  const allSources = [
    ...report.market_overview.sources,
    ...report.competitive_landscape.sources,
    ...report.target_analysis.sources,
    ...report.trends.sources,
    ...report.implications.sources,
  ];

  const uniqueSources = allSources.filter((source, index, array) => {
    const key = formatReportSource(source);
    return key && array.findIndex((item) => formatReportSource(item) === key) === index;
  });

  return {
    market_overview: report.market_overview.content,
    competitive_landscape: report.competitive_landscape.content,
    target_analysis: report.target_analysis.content,
    trends: report.trends.content,
    implications: report.implications.content,
    sources: uniqueSources.map(formatReportSource).join('\n'),
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

/** Phase 2: 시장조사 */
export async function fetchResearch(brief: ResearchBrief): Promise<ResearchResponse> {
  try {
    const res = await fetch(`${API_BASE}/research`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(buildLegacyResearchPayload(brief)),
    });

    const json = await parseJsonResponse<JsonRecord>(res, '시장조사 실패');
    return {
      refined: normalizeRefined(json.refined, brief),
      report: normalizeReport(json.report),
    };
  } catch (error) {
    if (error instanceof Error) throw error;
    throw new Error('시장조사 중 네트워크 오류가 발생했습니다.');
  }
}

/** Phase 2-1: 연구 정보 정제 */
export async function fetchRefinedResearch(brief: ResearchBrief): Promise<RefinedResearch> {
  const result = await fetchResearch(brief);
  return result.refined;
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

/** Phase 2-2: 정제된 연구 정보 기반 시장조사 보고서 생성 */
export async function fetchMarketReportFromRefined(
  brief: ResearchBrief,
  refined: RefinedResearch,
): Promise<MarketReport> {
  const result = await fetchResearch(buildBriefFromRefined(brief, refined));
  return result.report;
}

/** Phase 3: 에이전트 추천 */
export async function fetchAgents(data: AgentRequest): Promise<AgentSchema[]> {
  try {
    const res = await fetch(`${API_BASE}/agents`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...data,
        report: serializeMarketReportForBackend(data.report),
      }),
    });

    return await parseJsonResponse<AgentSchema[]>(res, '에이전트 추천 실패');
  } catch (error) {
    if (error instanceof Error) throw error;
    throw new Error('에이전트 추천 중 네트워크 오류가 발생했습니다.');
  }
}

/** SSE 이벤트 타입 */
export interface SSEStartEvent {
  type: 'start';
  role: 'moderator' | 'agent';
  agent_id: string | null;
  agent_name: string;
  agent_emoji: string;
  color: string | null;
}

/** Phase 4: 회의 시뮬레이션 (SSE 토큰 스트리밍) */
export async function fetchMeeting(
  data: MeetingRequest,
  onStart: (meta: SSEStartEvent) => void,
  onDelta: (delta: string) => void,
  onEnd: (msg: MeetingMessage) => void,
  onDone: () => void,
  onTopicRefined?: (topic: string) => void,
): Promise<void> {
  let res: Response;

  try {
    res = await fetch(`${API_BASE}/meeting`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
  } catch {
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
    const { done, value } = await reader.read();
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
          // 파싱 실패 무시
        }
      }
    }
  }

  onDone();
}

/** Phase 5: 회의록 생성 */
export async function fetchMinutes(data: MinutesRequest): Promise<string> {
  try {
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
