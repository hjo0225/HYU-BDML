'use client';

// 데모 4단계 (plan 0008 → 0023 + v7): 실제 6 에이전트 + 자동 사전계산 v7 유사도 대시보드 + 1:1 대화.
// V1Gauge/V3Scatter 시대를 끝내고, 사전계산된 holdout 결과로 각 에이전트의 "그 사람과 얼마나 닮았나" 를 즉시 보여준다.
import { useCallback, useEffect, useRef, useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { ChatBubble } from '@/components/chat/ChatBubble';
import { Spinner } from '@/components/ui/Spinner';
import { SimilarityDashboard } from '@/components/dashboard/SimilarityDashboard';
import { agents as agentsApi, conversations as convApi } from '@/lib/api';
import { personaKeywords } from '@/lib/persona';
import { lensTone, LENS_TONE_TEXT } from '@/lib/lensTone';
import type { Agent, ConversationTurn, HoldoutResult } from '@/lib/types';

interface Props {
  token: string;
  projectId: string;
  agents: Agent[];
}

export function DemoAgentsStep({ token, projectId: _projectId, agents }: Props) {
  // ── 사전계산된 v7 유사도 결과 (에이전트별) ──
  const [holdoutByAgent, setHoldoutByAgent] = useState<Record<string, HoldoutResult>>({});
  const [loadingHoldout, setLoadingHoldout] = useState(true);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);

  // 마운트 시 6명 모두 fetch (parallel). 미적재 에이전트는 조용히 skip.
  useEffect(() => {
    if (agents.length === 0) {
      setLoadingHoldout(false);
      return;
    }
    let cancelled = false;
    (async () => {
      const results = await Promise.all(
        agents.map(async (a) => {
          try {
            const h = await agentsApi.holdout(token, a.id);
            return [a.id, h] as const;
          } catch {
            return [a.id, null] as const;
          }
        }),
      );
      if (cancelled) return;
      const map: Record<string, HoldoutResult> = {};
      for (const [id, h] of results) {
        if (h) map[id] = h;
      }
      setHoldoutByAgent(map);
      // 첫 번째 적재된 에이전트를 자동 선택
      const first = agents.find((a) => map[a.id]);
      if (first) setSelectedAgentId(first.id);
      setLoadingHoldout(false);
    })();
    return () => { cancelled = true; };
  }, [agents, token]);

  // ── 1:1 대화 ──
  const [chatAgent, setChatAgent] = useState<Agent | null>(null);

  const selectedHoldout = selectedAgentId ? holdoutByAgent[selectedAgentId] : null;
  const selectedAgent = selectedAgentId ? agents.find((a) => a.id === selectedAgentId) : null;

  return (
    <div className="space-y-4">
      <p className="text-sm text-text-secondary">
        Twin-2K-500 한국화 6-Lens 설문·인터뷰 응답으로 <b>{agents.length}명의 AI 페르소나 에이전트</b>가
        구성되었습니다. 각 에이전트가 실제 응답자와 얼마나 닮았는지 사전계산된 유사도 평가로 즉시 확인할 수 있어요.
      </p>

      {/* 에이전트 그리드 — 닮은정도 % + Lens 미니막대 */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {agents.map((a) => {
          const h = holdoutByAgent[a.id];
          const isSelected = a.id === selectedAgentId;
          return (
            <button
              key={a.id}
              type="button"
              onClick={() => h && setSelectedAgentId(a.id)}
              disabled={!h}
              className={`block w-full rounded-xl border bg-surface p-3 text-left transition-all hover:shadow-card disabled:opacity-60 ${
                isSelected
                  ? 'border-ditto-indigo shadow-card ring-2 ring-ditto-indigo/20'
                  : 'border-border'
              }`}
            >
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

              {/* 닮은정도 */}
              <div className="mt-3 border-t border-border pt-2.5">
                {loadingHoldout ? (
                  <div className="flex items-center gap-2 text-2xs text-text-muted">
                    <Spinner size="sm" /> 평가 결과 불러오는 중…
                  </div>
                ) : h ? (
                  <>
                    <div className="mb-2 flex items-center justify-between">
                      <span className="text-2xs font-medium text-text-muted">실제 사람과의 닮은 정도</span>
                      <span className={`text-base font-bold tabular-nums ${LENS_TONE_TEXT[lensTone(h.agreement_score)]}`}>
                        {Math.round(h.agreement_score * 100)}<span className="text-2xs text-text-muted">%</span>
                      </span>
                    </div>
                  </>
                ) : (
                  <span className="text-2xs text-text-muted">평가 결과 없음 (사전계산 필요)</span>
                )}
              </div>

              {/* 1:1 대화 버튼 */}
              <div className="mt-2 flex justify-end">
                <span
                  role="button"
                  tabIndex={-1}
                  onClick={(e) => { e.stopPropagation(); setChatAgent(a); }}
                  className="cursor-pointer rounded-md border border-border bg-bg px-2.5 py-1 text-2xs font-medium text-text-secondary hover:border-ditto-indigo hover:text-ditto-indigo"
                >
                  1:1 대화 →
                </span>
              </div>
            </button>
          );
        })}
      </div>

      {/* 선택된 에이전트의 v7 풀 대시보드 — 자동 노출 */}
      {selectedHoldout && selectedAgent && (
        <Card>
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <span className="text-2xs font-bold uppercase tracking-wider text-ditto-indigo">
              선택된 에이전트의 상세 평가
            </span>
            <Badge variant="indigo" size="sm">
              {selectedAgent.emoji ?? '👤'} {selectedAgent.display_name ?? '에이전트'}
            </Badge>
            <span className="ml-auto text-2xs text-text-muted">
              위 카드를 클릭하면 다른 에이전트의 대시보드로 전환됩니다
            </span>
          </div>
          <SimilarityDashboard result={selectedHoldout} />
        </Card>
      )}

      {!loadingHoldout && Object.keys(holdoutByAgent).length === 0 && (
        <Card>
          <p className="text-sm text-text-muted">
            사전계산된 유사도 평가가 없습니다. 백엔드에서 <code className="rounded bg-bg px-1.5 py-0.5 font-mono text-xs">python -m scripts.run_holdout_eval</code>
            을 실행하면 결과가 노출됩니다.
          </p>
        </Card>
      )}

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

// ── 카드 내 미니 6-Lens 가로 막대 (3px) ─────────────────────────────────
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
