'use client';

// 데모 5단계 (plan 0008): 정식 FGI 엔진을 SSE 라이브로 구동 + 실시간 사용자 개입.
import { useCallback, useEffect, useRef, useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ChatBubble } from '@/components/chat/ChatBubble';
import { FGIInterventionInput } from '@/components/chat/FGIInterventionInput';
import { ReportBuildingOverlay } from '@/components/fgi/ReportBuildingOverlay';
import { fgi as fgiApi } from '@/lib/api';
import { useProjectContext } from '@/contexts/ProjectContext';
import { personaKeywords } from '@/lib/persona';
import { DEMO_FGI_ROUNDS, DEMO_FGI_TOPIC } from '@/lib/demoScenario';
import type { Agent, FGIReport, SuggestedRound } from '@/lib/types';

// 데모 readonly 라운드 → 가변 SuggestedRound[] 로 변환 (백엔드 페이로드).
const DEMO_ROUNDS_PAYLOAD: SuggestedRound[] = DEMO_FGI_ROUNDS.map((r) => ({
  round: r.round,
  subtopic: r.subtopic,
  goal_question: r.goal_question,
  probes: [...r.probes],
}));

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

/** 발화자 선정 시점의 라이브 관심도 (plan 0022 · 0026 · engagement 이벤트). */
interface EngagementLive {
  scores: Record<string, number>;   // agent_id → 추정 관심도 0~1
  nextAgentId?: string;             // 다음 발화 후보
  phase: 'B' | 'C' | 'followup' | 'intervention';
  probeIndex?: number;
  probeTotal?: number;
  excludedIds?: string[];           // 이번 cycle 후보 제외(cooling) — dim 처리용
}

export function DemoFGIStep({ token, projectId, agents, onComplete }: Props) {
  const nameById: Record<string, string> = Object.fromEntries(
    agents.map((a) => [a.id, a.display_name ?? '참여자']),
  );

  // 라운드는 hardcoded(데모 안정성), 토픽은 사용자 입력값으로 모더레이터 멘트에 반영.
  // plan 0027: idle 화면을 ask → generating → ready 로 분기해 "AI 가 생성하는 척" 시연.
  const suggested = DEMO_ROUNDS_PAYLOAD;
  const [topic, setTopic] = useState<string>(DEMO_FGI_TOPIC);
  const [planStep, setPlanStep] = useState<'ask' | 'generating' | 'ready'>('ask');
  const [phase, setPhase] = useState<'idle' | 'running' | 'done'>('idle');
  const [round, setRound] = useState(0);
  const [turns, setTurns] = useState<UiTurn[]>([]);
  const [streaming, setStreaming] = useState<{ agentId: string; text: string } | null>(null);
  // 모더레이터 토큰 SSE 누적 버블 (에이전트와 동일 메커니즘, role='user' 우측 표시).
  const [modStreaming, setModStreaming] = useState<string | null>(null);
  const [interveneAsking, setInterveneAsking] = useState(false);  // 개입 여부 먼저 묻는 단계
  const [interveneActive, setInterveneActive] = useState(false);  // '네' 선택 후 채팅 입력 단계
  const [interveneDeadline, setInterveneDeadline] = useState<number | null>(null);  // 백엔드 timeout 가시화 (디버그 + UX)
  const [error, setError] = useState<string | null>(null);
  const [engagement, setEngagement] = useState<EngagementLive | null>(null);
  // 마지막 라운드 종료 후 보고서 생성(build_report) 동안 토론창 위 오버레이 표시.
  const [buildingReport, setBuildingReport] = useState(false);

  const { setFgiRunning } = useProjectContext();

  const sessionIdRef = useRef<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [turns, streaming, modStreaming]);

  // FGI 진행 중에는 전역 플래그를 켜 사이드바 'AI 소비자' 탭 이동을 잠근다(이탈 시 SSE 끊김 방지).
  // 페이지 이탈/언마운트 시 자동 해제.
  useEffect(() => {
    setFgiRunning(phase === 'running');
    return () => setFgiRunning(false);
  }, [phase, setFgiRunning]);

  const start = useCallback(async () => {
    if (phase === 'running' || !agents.length) return;
    setPhase('running');
    setError(null);
    setTurns([]);
    setModStreaming(null);
    setStreaming(null);
    setBuildingReport(false);
    // 첫 engagement 이벤트가 오기 전에도 모든 에이전트가 게이지에 보이도록 baseline 0.5 로 초기화.
    // 이후 'engagement' 이벤트가 오면 merge 로 실측치가 덮어쓴다.
    setEngagement({
      scores: Object.fromEntries(agents.map((a) => [a.id, 0.5])),
      phase: 'C',
    });
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
          case 'moderator_delta':
            // 모더레이터도 에이전트와 동일하게 토큰 SSE 로 누적. role='user' 우측 버블로 표시되어
            // 사용자가 개입 안 할 때 모더레이터가 '나'의 역할을 대신하는 것처럼 보인다(팀 피드백).
            setModStreaming((s) => (s ?? '') + ev.delta);
            break;
          case 'moderator_end':
            setModStreaming(null);
            setTurns((p) => [
              ...p,
              { id: `mod-${ev.round}-${Date.now()}`, role: 'user', author: '모더레이터', content: ev.content },
            ]);
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
          case 'engagement':
            // 발화자 선정 점수 라이브 갱신 — 우측 패널 막대에 반영.
            // LLM engagement 응답이 partial (일부 agent 누락) 인 경우가 있어 매 이벤트마다
            // 덮어쓰면 직전 이벤트에서 받은 다른 agent 점수가 사라져 "1명만 표시" 되는
            // 버그가 생긴다. 직전 scores 와 merge 해서 누적 유지.
            // excluded 는 매 이벤트마다 새로 전송되므로 merge 하지 않고 전체 교체.
            setEngagement((prev) => ({
              scores: { ...(prev?.scores ?? {}), ...ev.scores },
              nextAgentId: ev.next_agent_id,
              phase: ev.phase,
              probeIndex: ev.probe_index,
              probeTotal: ev.probe_total,
              excludedIds: ev.excluded ?? [],
            }));
            break;
          case 'user_turn_required':
            // 먼저 개입 여부를 묻고(자동 진행 없음), '네'일 때만 채팅 입력을 연다.
            setInterveneAsking(true);
            setInterveneActive(false);
            setInterveneDeadline(ev.deadline_seconds);
            break;
          case 'round_end':
            // 개입 구간 종료
            setInterveneAsking(false);
            setInterveneActive(false);
            setInterveneDeadline(null);
            break;
          case 'report_building':
            // 마지막 라운드 종료 → 보고서 생성 시작. 토론창 위 오버레이 켜고 진행 중 스트림 정리.
            setStreaming(null);
            setModStreaming(null);
            setBuildingReport(true);
            break;
          case 'session_end':
            setBuildingReport(false);
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
      setBuildingReport(false);
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
            {planStep === 'ask' && (
              <>
                <div className="mb-3 flex items-center gap-2">
                  <Badge variant="indigo" size="sm">의뢰 작성</Badge>
                  <span className="text-xs text-text-muted">AI 사회자가 토론 플랜을 설계합니다</span>
                </div>
                <h3 className="text-lg font-bold text-text-primary">어떤 주제를 탐색해 볼까요?</h3>
                <p className="mb-4 mt-0.5 text-xs text-text-muted">
                  의뢰 내용을 입력하면 AI 사회자가 라운드를 자동 설계합니다.
                </p>

                <label className="mb-1.5 block text-2xs font-bold uppercase tracking-wider text-ditto-indigo">
                  FGI 의뢰 내용
                </label>
                <textarea
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  rows={3}
                  className="w-full resize-none rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-text-primary outline-none transition-colors focus:border-ditto-indigo"
                  placeholder="예: 포토이즘 재방문율 향상 요인 탐색"
                />

                <button
                  onClick={() => {
                    if (!topic.trim() || !agents.length) return;
                    setPlanStep('generating');
                    setTimeout(() => setPlanStep('ready'), 2500);
                  }}
                  disabled={!agents.length || !topic.trim()}
                  className="mt-4 w-full rounded-lg bg-ditto-indigo px-4 py-3.5 text-base font-bold text-white transition-colors hover:bg-ditto-indigo-hover disabled:opacity-50"
                >
                  AI 사회자에게 분석 의뢰
                </button>
              </>
            )}

            {planStep === 'generating' && (
              <div className="flex flex-col items-center justify-center gap-3 py-16">
                <div className="h-10 w-10 animate-spin rounded-full border-4 border-ditto-indigo border-t-transparent" />
                <p className="text-sm font-bold text-text-primary">AI 사회자가 토론 플랜을 생성하고 있어요…</p>
                <p className="text-xs text-text-muted">의뢰 내용을 바탕으로 라운드를 설계 중</p>
              </div>
            )}

            {planStep === 'ready' && (
              <>
                <div className="mb-3 flex items-center gap-2">
                  <Badge variant="success" size="sm">플랜 생성 완료</Badge>
                  <span className="text-xs text-text-muted">예상 소요 시간: 25~30분 · 3라운드</span>
                </div>
                <h3 className="text-lg font-bold text-text-primary">AI 사회자가 설계한 토론 플랜</h3>
                <p className="mb-4 mt-0.5 text-xs text-text-muted">3개 라운드로 의뢰 내용을 깊게 탐색합니다.</p>

                {/* FGI 의뢰 내용 박스 */}
                <div className="mb-4 rounded-r-lg border-l-[3px] border-ditto-indigo bg-ditto-indigo-light px-4 py-3">
                  <p className="mb-1 text-2xs font-bold uppercase tracking-wider text-ditto-indigo">
                    FGI 의뢰 내용
                  </p>
                  <p className="text-sm leading-relaxed text-text-primary">{topic}</p>
                </div>

                <p className="mb-2.5 text-2xs font-bold uppercase tracking-wider text-text-muted">
                  소주제별 토론 라운드
                </p>

                <ol className="space-y-2.5">
                  {DEMO_FGI_ROUNDS.map((r, idx) => (
                    <li
                      key={r.round}
                      style={{ animationDelay: `${idx * 200}ms` }}
                      className="grid animate-[fadeInUp_0.45s_ease-out_both] grid-cols-[40px_1fr_auto] items-center gap-3 rounded-lg border border-transparent bg-bg p-3.5 transition-colors hover:border-border"
                    >
                      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-ditto-indigo text-2xs font-bold text-white">
                        R{r.round}
                      </div>
                      <div>
                        <p className="text-sm font-bold text-text-primary">{r.subtopic}</p>
                        <p className="mt-0.5 truncate text-xs text-text-muted">
                          목표: {r.goal_summary}
                        </p>
                      </div>
                      <span className="whitespace-nowrap rounded-full border border-border bg-surface px-2.5 py-1 text-2xs font-medium text-text-muted">
                        8~10분
                      </span>
                    </li>
                  ))}
                </ol>

                <button
                  onClick={start}
                  disabled={!agents.length}
                  className="mt-5 w-full rounded-lg bg-ditto-indigo px-4 py-3.5 text-base font-bold text-white transition-colors hover:bg-ditto-indigo-hover disabled:opacity-50"
                >
                  FGI 시작하기
                </button>
              </>
            )}
          </Card>

          <FGIAgentPanel agents={agents} />
        </div>
      )}

      {phase !== 'idle' && (
        <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
        <Card>
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Badge variant={phase === 'done' ? 'success' : 'indigo'} dot>
                {phase === 'done'
                  ? '회의 종료'
                  : buildingReport
                    ? '보고서 생성 중'
                    : `진행 중 · Round ${round}`}
              </Badge>
              <span className="text-xs text-text-muted">{agents.length}명 참여</span>
            </div>
            {phase === 'running' && !buildingReport && (
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

          {/* 토론창 — 보고서 생성 중에는 위에 반복 재생 오버레이를 덮어 '멈춘 듯' 보이지 않게 한다. */}
          <div className="relative mb-3">
            <div className="h-[420px] space-y-3 overflow-y-auto rounded-xl border border-border bg-bg p-4">
              {turns.map((t) => (
                <ChatBubble key={t.id} role={t.role} author={t.author}>
                  {t.content}
                </ChatBubble>
              ))}
              {modStreaming !== null && (
                <ChatBubble role="user" author="모더레이터">
                  {modStreaming || '…'}
                </ChatBubble>
              )}
              {streaming && (
                <ChatBubble role="agent" author={nameById[streaming.agentId] ?? '참여자'}>
                  {streaming.text || '…'}
                </ChatBubble>
              )}
              <div ref={bottomRef} />
            </div>
            {buildingReport && <ReportBuildingOverlay />}
          </div>

          {/* 개입 패널 — 채팅 박스 바로 아래 인라인. 팝업 대신 같은 Card 안에 두어
              위쪽 대화를 자유롭게 스크롤하며 개입 여부를 결정할 수 있게 한다.
              (팀 피드백 2026-05-23 — 빠른 토론 + 팝업 조합 때문에 내용 재확인 불가 문제 해소) */}
          {phase === 'running' && (interveneAsking || interveneActive) && (
            <div className="mb-3 rounded-xl border border-ditto-indigo/40 bg-ditto-indigo-light/40 p-4">
              {interveneAsking ? (
                <>
                  <h4 className="mb-1 text-sm font-bold text-text-primary">✍️ 라운드가 끝났어요</h4>
                  <p className="mb-1 text-sm text-text-secondary">
                    위 대화를 천천히 읽어보시고 개입 여부를 결정하세요. 선택하실 때까지 회의는 기다립니다.
                  </p>
                  {interveneDeadline != null && (
                    <p className="mb-3 text-2xs text-text-muted">
                      최대 대기 시간: {Math.floor(interveneDeadline / 60)}분 {interveneDeadline % 60 > 0 ? `${interveneDeadline % 60}초` : ''}
                    </p>
                  )}
                  <div className="flex items-center justify-end gap-2">
                    <button
                      onClick={declineIntervention}
                      className="rounded-lg px-3 py-1.5 text-sm font-medium text-text-secondary hover:bg-surface hover:text-text-primary"
                    >
                      아니요, 계속
                    </button>
                    <Button size="sm" onClick={() => { setInterveneAsking(false); setInterveneActive(true); }}>
                      네, 개입할게요
                    </Button>
                  </div>
                </>
              ) : (
                <>
                  <h4 className="mb-2 text-sm font-bold text-text-primary">✍️ 개입 발언 입력</h4>
                  <FGIInterventionInput
                    active={interveneActive}
                    onSubmit={submitIntervention}
                    onYield={declineIntervention}
                  />
                </>
              )}
            </div>
          )}

          {phase === 'done' && (
            <p className="text-sm text-success">✓ 회의가 종료되었습니다. 다음 단계에서 인사이트 보고서를 확인하세요.</p>
          )}
        </Card>
        <FGILiveEngagementPanel agents={agents} engagement={engagement} running={phase === 'running'} />
        </div>
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
                {/* 키워드 중심 표현 — 인구통계는 위 배지로 충분하므로 'OO 인터뷰 기반 페르소나' 소개문은 생략. */}
                {kws.length > 0 ? (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {kws.map((k) => (
                      <Badge key={k} variant="violet" size="sm">{k}</Badge>
                    ))}
                  </div>
                ) : (
                  <p className="mt-1 text-2xs text-text-muted">프로파일 분석 준비 중…</p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

// 진행 중 우측 패널 — 발화자 선정 점수(추정 관심도)를 막대로 라이브 표시 (plan 0022).
// engagement 이벤트마다 갱신. Phase A/B(점수 없음) 구간엔 직전 값 유지 + 안내.
function FGILiveEngagementPanel({
  agents,
  engagement,
  running,
}: {
  agents: Agent[];
  engagement: EngagementLive | null;
  running: boolean;
}) {
  // 관심도 내림차순(점수 없으면 원래 순서 유지)
  const ranked = [...agents].sort(
    (a, b) => (engagement?.scores[b.id] ?? -1) - (engagement?.scores[a.id] ?? -1),
  );

  const contextLabel = (() => {
    if (!engagement) return running ? '발화자 분석 대기 중…' : '토론 종료';
    if (engagement.phase === 'B') return '1차 답변';
    if (engagement.phase === 'C') {
      const seg = engagement.probeIndex && engagement.probeTotal
        ? ` · 쟁점 ${engagement.probeIndex}/${engagement.probeTotal}`
        : '';
      return `쟁점 토론${seg}`;
    }
    return engagement.phase === 'followup' ? '추가 질문 응답' : '개입 응답';
  })();

  return (
    <Card className="flex h-full flex-col">
      <h3 className="text-sm font-bold text-text-primary">실시간 관심도</h3>
      <p className="mb-3 mt-0.5 text-2xs text-text-muted">
        발화권은 소주제 관련성·관심도로 매 턴 동적 배분됩니다. (LLM 추정 관심도)
      </p>
      <div className="flex-1 space-y-2 overflow-y-auto">
        {ranked.map((a) => {
          // 점수가 없으면 baseline 0.5 로 폴백 — 첫 engagement 이벤트 전이나 partial 응답
          // 직후에도 막대가 사라지지 않게 한다. 비교/정렬에는 실측치 우선.
          const raw = engagement?.scores[a.id];
          const value = typeof raw === 'number' ? raw : 0.5;
          // 표시 폭은 최소 15% 보장 — backend 가 0 에 가까운 점수를 보내도 막대가 보이게
          // ("1등만 게이지 나옴" 방지). 숫자 칩은 실측치 그대로 노출해 혼동 방지.
          const pct = Math.max(15, Math.round(value * 100));
          const isNext = engagement?.nextAgentId === a.id;
          // 발화 cooling — Phase B 에서 이미 1차 답변 끝낸 사람, Phase C 에서 직전 lock /
          // 라운드 누적 상한 도달자. 카드를 dim 처리 + "쿨다운" 배지로 사용자에게 명확히.
          const isCooling = !isNext && (engagement?.excludedIds?.includes(a.id) ?? false);
          return (
            <div
              key={a.id}
              className={`rounded-xl border p-2.5 transition-all duration-300 ${
                isNext
                  ? 'border-ditto-indigo bg-ditto-indigo-light/50'
                  : isCooling
                    ? 'border-border bg-bg'
                    : 'border-border bg-bg'
              }`}
            >
              <div className={`mb-1.5 flex items-center gap-1.5 ${isCooling ? 'opacity-60' : ''}`}>
                <span className="text-base leading-none">{a.emoji ?? '👤'}</span>
                <span className="min-w-0 flex-1 truncate text-xs font-semibold text-text-primary">
                  {a.display_name ?? '참여자'}
                </span>
                <span className="text-2xs font-semibold tabular-nums text-text-secondary">
                  {value.toFixed(2)}
                </span>
                {isNext && (
                  <span className="rounded-full bg-ditto-indigo px-1.5 py-0.5 text-2xs font-bold text-white">
                    다음 발화
                  </span>
                )}
                {isCooling && (
                  <span className="rounded-full border border-border bg-surface px-1.5 py-0.5 text-2xs font-medium text-text-muted">
                    발화 완료
                  </span>
                )}
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-border/50">
                {/* cooling(발화 완료) 상태에선 막대 progress 를 그리지 않아 "현재 후보 아님" 을
                    시각적으로 분명히. 트랙은 유지해 카드 높이 일관 보장. */}
                {!isCooling && (
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      isNext ? 'bg-ditto-indigo' : 'bg-violet-500'
                    }`}
                    style={{ width: `${pct}%` }}
                  />
                )}
              </div>
            </div>
          );
        })}
      </div>
      <p className="mt-3 border-t border-border pt-2 text-2xs font-medium text-text-muted">
        {contextLabel}
      </p>
    </Card>
  );
}
