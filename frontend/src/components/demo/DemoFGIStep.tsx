'use client';

// 데모 5단계 (plan 0008): 정식 FGI 엔진을 SSE 라이브로 구동 + 실시간 사용자 개입.
import { useCallback, useEffect, useRef, useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ChatBubble } from '@/components/chat/ChatBubble';
import { FGIInterventionInput } from '@/components/chat/FGIInterventionInput';
import { Spinner } from '@/components/ui/Spinner';
import { fgi as fgiApi } from '@/lib/api';
import { personaKeywords } from '@/lib/persona';
import { DEMO_FGI_MAX_ROUNDS, DEMO_FGI_TOPIC } from '@/lib/demoScenario';
import type { Agent, FGIReport, SuggestedRound } from '@/lib/types';

interface Props {
  token: string;
  projectId: string;
  agents: Agent[];
  /** 세션 종료 시 구조화 보고서를 상위로 전달 → 6·7단계에서 사용 */
  onComplete: (sessionId: string, report: FGIReport) => void;
}

interface UiTurn {
  id: string;
  role: 'moderator' | 'agent' | 'user';
  author?: string;
  content: string;
}

export function DemoFGIStep({ token, projectId, agents, onComplete }: Props) {
  const nameById: Record<string, string> = Object.fromEntries(
    agents.map((a) => [a.id, a.display_name ?? '참여자']),
  );

  const [topic, setTopic] = useState(DEMO_FGI_TOPIC);
  const [suggested, setSuggested] = useState<SuggestedRound[] | null>(null);
  const [suggesting, setSuggesting] = useState(false);
  const [phase, setPhase] = useState<'idle' | 'running' | 'done'>('idle');
  const [round, setRound] = useState(0);
  const [turns, setTurns] = useState<UiTurn[]>([]);
  const [streaming, setStreaming] = useState<{ agentId: string; text: string } | null>(null);
  const [interveneAsking, setInterveneAsking] = useState(false);  // 개입 여부 먼저 묻는 단계
  const [interveneActive, setInterveneActive] = useState(false);  // '네' 선택 후 채팅 입력 단계
  const [error, setError] = useState<string | null>(null);

  const sessionIdRef = useRef<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [turns, streaming]);

  const suggest = useCallback(async () => {
    if (suggesting || !topic.trim()) return;
    setSuggesting(true);
    setError(null);
    try {
      const res = await fgiApi.suggestRounds(token, projectId, { topic, n_rounds: DEMO_FGI_MAX_ROUNDS });
      setSuggested(res.rounds);
    } catch (e) {
      setError(e instanceof Error ? e.message : '질문 제안 실패');
    } finally {
      setSuggesting(false);
    }
  }, [suggesting, topic, token, projectId]);

  const start = useCallback(async () => {
    if (phase === 'running' || !agents.length) return;
    // 라운드별 질문 제안을 먼저 확정해야 FGI 를 시작할 수 있다 (plan 0010).
    if (!suggested || suggested.length === 0) {
      setError('먼저 "라운드별 질문 AI 제안"을 눌러 토론 플랜을 만들어주세요.');
      return;
    }
    setPhase('running');
    setError(null);
    setTurns([]);
    try {
      const session = await fgiApi.create(token, projectId, {
        topic,
        agent_ids: agents.map((a) => a.id),
        rounds: suggested,
        allow_user_intervention: true,
      });
      sessionIdRef.current = session.id;

      for await (const ev of fgiApi.run(token, session.id)) {
        switch (ev.type) {
          case 'round_start':
            setRound(ev.round);
            break;
          case 'moderator':
            setTurns((p) => [...p, { id: `mod-${ev.round}-${p.length}`, role: 'moderator', author: '모더레이터', content: ev.content }]);
            break;
          case 'agent_delta':
            setStreaming((s) =>
              s && s.agentId === ev.agent_id
                ? { agentId: ev.agent_id, text: s.text + ev.delta }
                : { agentId: ev.agent_id, text: ev.delta },
            );
            break;
          case 'agent_end':
            setStreaming(null);
            setTurns((p) => [...p, { id: ev.turn_id, role: 'agent', author: nameById[ev.agent_id] ?? '참여자', content: ev.content }]);
            break;
          case 'user_turn_required':
            // 먼저 개입 여부를 묻고(자동 진행 없음), '네'일 때만 채팅 입력을 연다.
            setInterveneAsking(true);
            setInterveneActive(false);
            break;
          case 'round_end':
            // 개입 구간 종료
            setInterveneAsking(false);
            setInterveneActive(false);
            break;
          case 'session_end':
            setPhase('done');
            onComplete(session.id, ev.report);
            break;
          case 'error':
            setError(ev.reason);
            break;
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'FGI 진행 실패');
      setPhase('idle');
    }
  }, [phase, agents, token, projectId, topic, suggested]); // eslint-disable-line react-hooks/exhaustive-deps

  const submitIntervention = useCallback(async (text: string) => {
    const sid = sessionIdRef.current;
    if (!sid) return;
    setInterveneActive(false);
    setTurns((p) => [...p, { id: `user-${p.length}`, role: 'user', author: '나 (기업 관계자)', content: text }]);
    try {
      await fgiApi.intervene(token, sid, text);
    } catch (e) {
      // 개입 전송 실패를 조용히 삼키지 않는다. 엔진은 개입 신호가 올 때까지 대기하므로,
      // 실패 시 (1) 원인을 표면화하고 (2) 대기 창을 풀어 다음 라운드로 진행시킨다(장시간 멈춤 방지).
      setError(e instanceof Error ? `개입 전송 실패: ${e.message}` : '개입 전송에 실패했습니다.');
      try { await fgiApi.skipIntervention(token, sid); } catch { /* 무시 */ }
    }
  }, [token]);

  // '개입 안 함' — 대기 창을 닫고 다음 라운드로 진행(백엔드 skip).
  const declineIntervention = useCallback(async () => {
    setInterveneAsking(false);
    setInterveneActive(false);
    const sid = sessionIdRef.current;
    if (!sid) return;
    try { await fgiApi.skipIntervention(token, sid); } catch { /* 무시 */ }
  }, [token]);

  const control = useCallback(async (action: 'next_round' | 'end_session') => {
    const sid = sessionIdRef.current;
    if (!sid) return;
    try { await fgiApi.control(token, sid, action); } catch { /* 무시 */ }
  }, [token]);

  return (
    <div className="space-y-4">
      {phase === 'idle' && (
        <div className="grid items-start gap-4 lg:grid-cols-[1.6fr_1fr]">
        <Card>
          <h3 className="mb-1 font-semibold text-text-primary">FGI 회의 설정</h3>
          <p className="mb-3 text-xs text-text-muted">
            {agents.length}명의 에이전트가 AI 모더레이터 진행으로 최대 {DEMO_FGI_MAX_ROUNDS}라운드 토론합니다.
            라운드 사이에 기업 관계자(나)가 직접 개입할 수 있어요.
          </p>
          <label className="mb-1 block text-xs font-medium text-text-secondary">토론 주제</label>
          <textarea
            value={topic}
            onChange={(e) => { setTopic(e.target.value); setSuggested(null); }}
            rows={2}
            className="mb-3 w-full resize-none rounded-xl border border-border bg-surface px-3 py-2 text-sm text-text-primary focus:border-ditto-indigo focus:outline-none"
          />

          {/* 라운드별 질문 AI 제안 (plan 0009 · item 6) */}
          <div className="mb-3">
            <button
              onClick={suggest}
              disabled={suggesting || !topic.trim()}
              className="inline-flex items-center gap-1.5 rounded-lg border border-ditto-indigo/40 px-3 py-1.5 text-xs font-semibold text-ditto-indigo transition-colors hover:bg-ditto-indigo-light disabled:opacity-50"
            >
              {suggesting ? <Spinner size="sm" /> : '✨'}
              {suggested ? '질문 다시 제안' : '라운드별 질문 AI 제안'}
            </button>

            {suggesting && (
              <p className="mt-2 text-xs text-text-muted">주제에 맞춰 라운드별 질문을 설계하는 중…</p>
            )}

            {suggested && suggested.length > 0 && (
              <ol className="mt-3 space-y-2">
                {suggested.map((r) => (
                  <li key={r.round} className="rounded-lg border border-border bg-bg p-2.5">
                    <div className="mb-0.5 flex items-center gap-1.5">
                      <Badge variant="indigo" size="sm">R{r.round}</Badge>
                      <span className="text-xs font-semibold text-text-primary">{r.subtopic}</span>
                    </div>
                    <p className="text-sm text-text-secondary">{r.goal_question}</p>
                    {r.probes && r.probes.length > 0 && (
                      <ul className="mt-1.5 space-y-0.5 border-t border-border pt-1.5">
                        {r.probes.map((p, i) => (
                          <li key={i} className="flex gap-1.5 text-2xs text-text-muted">
                            <span className="text-ditto-indigo">쟁점</span>
                            <span>{p}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </li>
                ))}
              </ol>
            )}
          </div>

          <div className="flex items-center gap-2">
            <Button onClick={start} disabled={!topic.trim() || !suggested || suggested.length === 0}>
              FGI 시작
            </Button>
            {(!suggested || suggested.length === 0) && (
              <span className="text-2xs text-text-muted">
                라운드별 질문을 먼저 제안해야 시작할 수 있어요.
              </span>
            )}
          </div>
        </Card>

        <FGIAgentPanel agents={agents} />
        </div>
      )}

      {phase !== 'idle' && (
        <Card>
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Badge variant={phase === 'done' ? 'success' : 'indigo'} dot>
                {phase === 'done' ? '회의 종료' : `진행 중 · Round ${round}`}
              </Badge>
              <span className="text-xs text-text-muted">{agents.length}명 참여</span>
            </div>
            {phase === 'running' && (
              <div className="flex items-center gap-2">
                <button onClick={() => control('next_round')} className="rounded-lg border border-border px-2.5 py-1 text-2xs font-medium text-text-secondary hover:border-ditto-indigo hover:text-ditto-indigo">
                  다음 주제로 →
                </button>
                <button onClick={() => control('end_session')} className="rounded-lg border border-error/40 px-2.5 py-1 text-2xs font-medium text-error hover:bg-red-50">
                  토론 종료
                </button>
              </div>
            )}
          </div>

          <div className="mb-3 h-[420px] space-y-3 overflow-y-auto rounded-xl border border-border bg-bg p-4">
            {turns.map((t) => (
              <ChatBubble key={t.id} role={t.role} author={t.author}>
                {t.content}
              </ChatBubble>
            ))}
            {streaming && (
              <ChatBubble role="agent" author={nameById[streaming.agentId] ?? '참여자'}>
                {streaming.text || '…'}
              </ChatBubble>
            )}
            <div ref={bottomRef} />
          </div>

          {phase === 'running' && (interveneAsking || interveneActive) && (
            <div>
              {interveneAsking ? (
                <div className="flex items-center gap-2 rounded-xl border border-ditto-indigo/30 bg-ditto-indigo-light/40 px-3 py-2.5">
                  <span className="flex-1 text-sm text-text-secondary">
                    라운드가 끝났어요. 지금 토론에 직접 개입하시겠어요? (선택할 때까지 기다립니다)
                  </span>
                  <Button size="sm" onClick={() => { setInterveneAsking(false); setInterveneActive(true); }}>
                    네, 개입할게요
                  </Button>
                  <button
                    onClick={declineIntervention}
                    className="rounded-lg px-2.5 py-1.5 text-xs font-medium text-text-muted hover:text-text-primary"
                  >
                    아니요, 계속
                  </button>
                </div>
              ) : (
                <FGIInterventionInput
                  active={interveneActive}
                  onSubmit={submitIntervention}
                  onYield={declineIntervention}
                />
              )}
            </div>
          )}

          {phase === 'done' && (
            <p className="text-sm text-success">✓ 회의가 종료되었습니다. 다음 단계에서 인사이트 보고서를 확인하세요.</p>
          )}
        </Card>
      )}

      {error && <p className="text-sm text-error">{error}</p>}
    </div>
  );
}

// 플랜 설정 화면 우측 — 이번 토론에 참여하는 AI 소비자 미리보기 패널.
// 빈 우측 공간을 채우고, 시작 전에 누가 토론하는지 한눈에 보여준다.
function FGIAgentPanel({ agents }: { agents: Agent[] }) {
  return (
    <Card className="lg:sticky lg:top-4">
      <h3 className="flex items-center gap-2 text-sm font-bold text-text-primary">
        참여 AI 소비자
        <span className="rounded-full bg-ditto-indigo px-2 py-0.5 text-2xs font-bold text-white">{agents.length}</span>
      </h3>
      <p className="mb-3 mt-0.5 text-2xs text-text-muted">
        이번 토론에 참여하는 소비자입니다. ‘AI 소비자’ 탭에서 변경할 수 있어요.
      </p>
      <div className="space-y-2">
        {agents.map((a, i) => {
          const tint = i % 2 === 0
            ? 'bg-ditto-indigo-light text-ditto-indigo'
            : 'bg-ditto-violet-light text-ditto-violet';
          const demo = [a.age_range, a.gender].filter(Boolean) as string[];
          const kws = personaKeywords(a.persona_params, 2);
          return (
            <div
              key={a.id}
              className="flex items-start gap-3 rounded-xl border border-border bg-bg p-3 transition-colors hover:border-ditto-indigo/40"
            >
              <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-lg ${tint}`}>
                {a.emoji ?? '👤'}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-sm font-bold text-text-primary">{a.display_name ?? '참여자'}</span>
                  {demo.map((d) => (
                    <Badge key={d} variant="neutral" size="sm">{d}</Badge>
                  ))}
                </div>
                {kws.length > 0 && (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {kws.map((k) => (
                      <Badge key={k} variant="violet" size="sm">{k}</Badge>
                    ))}
                  </div>
                )}
                {(a.intro_ko || a.summary) && (
                  <p className="mt-1 line-clamp-2 text-xs text-text-muted">{a.intro_ko ?? a.summary}</p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
