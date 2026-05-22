'use client';

// 데모 4단계 (plan 0008): 실제 6 에이전트 + 성능 평가(V1·V3) + 1:1 대화 임베드.
import { useCallback, useRef, useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { ChatBubble } from '@/components/chat/ChatBubble';
import { V1Gauge } from '@/components/dashboard/V1Gauge';
import { V3Scatter } from '@/components/dashboard/V3Scatter';
import { conversations as convApi, evaluations as evalApi } from '@/lib/api';
import { personaKeywords } from '@/lib/persona';
import type { Agent, ConversationTurn, ScatterResponse } from '@/lib/types';

interface Props {
  token: string;
  projectId: string;
  agents: Agent[];
}

export function DemoAgentsStep({ token, projectId, agents }: Props) {
  // ── 평가 ──
  const [evalRunning, setEvalRunning] = useState(false);
  const [evalMsg, setEvalMsg] = useState<string | null>(null);
  const [scatter, setScatter] = useState<ScatterResponse | null>(null);
  const [v1byAgent, setV1byAgent] = useState<Record<string, number>>({});

  const runEval = useCallback(async () => {
    if (!agents.length || evalRunning) return;
    setEvalRunning(true);
    setEvalMsg('평가 시작…');
    try {
      for await (const ev of evalApi.trigger(token, agents[0].id, { metrics: ['v1', 'v3'] })) {
        if (ev.type === 'agent_done') setEvalMsg(`평가 중… (${ev.current}/${ev.total})`);
        else if (ev.type === 'v3_done') setEvalMsg(`다양성(V3) 산출 완료 · ${ev.n_agents}명`);
      }
      const sc = await evalApi.scatter(token, projectId);
      setScatter(sc);
      const entries = await Promise.all(
        agents.map(async (a) => {
          const latest = await evalApi.latest(token, a.id).catch(() => null);
          return [a.id, latest?.identity_stats?.sync ?? 0] as const;
        }),
      );
      setV1byAgent(Object.fromEntries(entries));
      setEvalMsg('평가 완료 — 아래 지표를 확인하세요.');
    } catch (e) {
      setEvalMsg(e instanceof Error ? e.message : '평가 실패');
    } finally {
      setEvalRunning(false);
    }
  }, [token, projectId, agents, evalRunning]);

  // ── 1:1 대화 ──
  const [chatAgent, setChatAgent] = useState<Agent | null>(null);

  return (
    <div className="space-y-4">
      <p className="text-sm text-text-secondary">
        Twin-2K-500 한국화 6-Lens 설문·인터뷰 응답으로 <b>{agents.length}명의 AI 페르소나 에이전트</b>가
        구성되었습니다. 성능 평가로 복제 충실도를 확인하고, 한 명과 1:1 대화를 나눠볼 수 있어요.
      </p>

      {/* 에이전트 그리드 */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {agents.map((a) => (
          <Card key={a.id} padding="sm">
            <div className="flex items-start gap-3">
              <span className="text-2xl">{a.emoji ?? '👤'}</span>
              <div className="min-w-0 flex-1">
                <p className="truncate font-semibold text-text-primary">{a.display_name ?? '에이전트'}</p>
                {[a.age_range, a.gender].filter(Boolean).length > 0 && (
                  <div className="mt-0.5 flex flex-wrap gap-1">
                    {([a.age_range, a.gender].filter(Boolean) as string[]).map((d) => (
                      <Badge key={d} variant="neutral" size="sm">{d}</Badge>
                    ))}
                  </div>
                )}
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {personaKeywords(a.persona_params, 3).map((k) => (
                    <Badge key={k} variant="violet" size="sm">{k}</Badge>
                  ))}
                </div>
              </div>
            </div>
            <div className="mt-3 flex items-center justify-between">
              {a.id in v1byAgent ? (
                <Badge variant="indigo" size="sm">V1 {Math.round(v1byAgent[a.id] * 100)}%</Badge>
              ) : (
                <span className="text-2xs text-text-muted">평가 전</span>
              )}
              <Button variant="ghost" size="sm" onClick={() => setChatAgent(a)}>
                1:1 대화
              </Button>
            </div>
          </Card>
        ))}
      </div>

      {/* 성능 평가 */}
      <Card>
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-text-primary">성능 평가 (V1 응답 동기화 · V3 페르소나 다양성)</h3>
            <p className="text-xs text-text-muted">{evalMsg ?? '에이전트가 실제 응답을 얼마나 충실히 복제하는지 측정합니다.'}</p>
          </div>
          <Button onClick={runEval} loading={evalRunning} disabled={evalRunning}>
            성능 평가 실행
          </Button>
        </div>
        {scatter && (
          <div className="grid items-center gap-4 md:grid-cols-2">
            <div>
              <p className="mb-1 text-xs font-medium text-text-secondary">V3 페르소나 다양성 (산점도)</p>
              <V3Scatter points={scatter.points} distinct={scatter.distinct} height={260} />
            </div>
            <div className="flex flex-col items-center">
              <p className="mb-1 text-xs font-medium text-text-secondary">V1 동기화율 (에이전트 1)</p>
              <V1Gauge sync={v1byAgent[agents[0]?.id] ?? 0} size={200} />
            </div>
          </div>
        )}
      </Card>

      {/* 1:1 대화 패널 */}
      {chatAgent && (
        <DemoChatPanel
          key={chatAgent.id}
          token={token}
          agent={chatAgent}
          onClose={() => setChatAgent(null)}
        />
      )}
    </div>
  );
}

// ── 임베드 1:1 대화 패널 ─────────────────────────────────────────────────────
function DemoChatPanel({ token, agent, onClose }: { token: string; agent: Agent; onClose: () => void }) {
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [streamText, setStreamText] = useState('');
  const convIdRef = useRef<string | null>(null);

  const send = useCallback(async () => {
    const content = input.trim();
    if (!content || streaming) return;
    setInput('');
    setTurns((p) => [...p, { id: `local-${Date.now()}`, role: 'user', content, created_at: new Date().toISOString() }]);
    setStreaming(true);
    setStreamText('');
    try {
      if (!convIdRef.current) {
        const conv = await convApi.create(token, agent.id);
        convIdRef.current = conv.id;
      }
      let acc = '';
      for await (const ev of convApi.sendMessage(token, convIdRef.current, content)) {
        if (ev.type === 'delta') {
          acc += ev.delta;
          setStreamText(acc);
        } else if (ev.type === 'end') {
          setTurns((p) => [...p, { id: ev.turn_id, role: 'agent', content: ev.content, created_at: new Date().toISOString() }]);
          setStreamText('');
        }
      }
    } catch {
      /* 데모: 에러는 조용히 무시 */
    } finally {
      setStreaming(false);
    }
  }, [input, streaming, token, agent.id]);

  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xl">{agent.emoji ?? '👤'}</span>
          <span className="font-semibold text-text-primary">{agent.display_name ?? '에이전트'}와 1:1 대화</span>
        </div>
        <button onClick={onClose} className="text-sm text-text-muted hover:text-text-primary">닫기 ✕</button>
      </div>
      <div className="mb-3 h-64 space-y-3 overflow-y-auto rounded-xl border border-border bg-bg p-3">
        {turns.length === 0 && !streaming && (
          <p className="py-8 text-center text-sm text-text-muted">첫 메시지를 보내 대화를 시작하세요.</p>
        )}
        {turns.map((t) => (
          <ChatBubble key={t.id} role={t.role} author={t.role === 'agent' ? agent.display_name ?? undefined : undefined}>
            {t.content}
          </ChatBubble>
        ))}
        {streaming && <ChatBubble role="agent" author={agent.display_name ?? undefined}>{streamText || '…'}</ChatBubble>}
      </div>
      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); void send(); }}>
        <Input value={input} onChange={(e) => setInput(e.target.value)} placeholder="메시지를 입력하세요…" disabled={streaming} className="flex-1" />
        <Button type="submit" loading={streaming} disabled={!input.trim()}>전송</Button>
      </form>
    </Card>
  );
}
