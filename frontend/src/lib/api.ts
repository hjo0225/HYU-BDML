/* 빅마랩 API 호출 유틸리티 */
import type {
  ResearchBrief,
  ResearchResponse,
  AgentRequest,
  AgentSchema,
  MeetingRequest,
  MeetingMessage,
  MinutesRequest,
} from './types';

const API_BASE = '/api';

/** Phase 2: 시장조사 (SSE) */
export async function fetchResearch(
  brief: ResearchBrief,
  onStatus: (step: number, total: number, message: string) => void,
  onDone: (result: ResearchResponse) => void,
): Promise<void> {
  const res = await fetch(`${API_BASE}/research`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(brief),
  });

  if (!res.ok) throw new Error(`연구조사 실패: ${res.status}`);
  if (!res.body) throw new Error('SSE 스트림 없음');

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finalResult: ResearchResponse | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6);
        if (data === '[DONE]') {
          if (finalResult) onDone(finalResult);
          return;
        }
        try {
          const parsed = JSON.parse(data);
          if (parsed.type === 'status') {
            onStatus(parsed.step, parsed.total, parsed.message);
          } else if (parsed.type === 'result') {
            finalResult = parsed.data;
          }
          // type === 'chunk'는 무시 (진행 표시만 사용)
        } catch {
          // 파싱 실패 무시
        }
      }
    }
  }

  if (finalResult) onDone(finalResult);
}

/** Phase 3: 에이전트 추천 */
export async function fetchAgents(data: AgentRequest): Promise<AgentSchema[]> {
  const res = await fetch(`${API_BASE}/agents`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });

  if (!res.ok) throw new Error(`에이전트 추천 실패: ${res.status}`);
  return res.json();
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
): Promise<void> {
  const res = await fetch(`${API_BASE}/meeting`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });

  if (!res.ok) throw new Error(`회의 시뮬레이션 실패: ${res.status}`);
  if (!res.body) throw new Error('SSE 스트림 없음');

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
  const res = await fetch(`${API_BASE}/minutes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });

  if (!res.ok) throw new Error(`회의록 생성 실패: ${res.status}`);
  const json = await res.json();
  return json.minutes;
}
