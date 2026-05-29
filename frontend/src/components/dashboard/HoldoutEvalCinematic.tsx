'use client';

// 품질 평가 시네마틱 (plan 0027).
// 사전계산된 holdout 결과 위에 "지금 평가가 일어나는 것처럼" 단계별 연출을 재생한 뒤
// onComplete 로 부모가 실제 대시보드를 드러낸다. ※ 실제 재평가 아님 — HoldoutResult 데이터만으로 과정을 재현.
//   - mode='overall' : 프로젝트 진입 시. 에이전트별 점수가 순차로 채워지고 평균 일치율 공개.
//   - mode='agent'   : 카드 클릭 시. 샘플 Q&A → Judge 채점 → 6-Lens 집계 → 전체 일치율 공개.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Spinner } from '@/components/ui/Spinner';
import type { HoldoutPair, HoldoutResult, HoldoutVerdict } from '@/lib/types';
import { lensTone, LENS_TONE_GRADIENT } from '@/lib/lensTone';

// ── 공용 훅 ──────────────────────────────────────────────────────────────

/** 고정 단계 타임라인. step 0→len 까지 증가, 마지막+hold 후 finish(). 언마운트/스킵 시 전 타이머 정리. */
function useTimeline(durations: number[], holdMs: number, finish: () => void) {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const timers: ReturnType<typeof setTimeout>[] = [];
    let acc = 0;
    durations.forEach((d, i) => {
      acc += d;
      timers.push(setTimeout(() => setStep(i + 1), acc));
    });
    timers.push(setTimeout(finish, acc + holdMs));
    return () => timers.forEach(clearTimeout);
    // durations/holdMs/finish 는 마운트 시 고정 — 의존성 비움(타임라인 재시작 방지).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return step;
}

/** easeOutCubic count-up. active 가 true 가 된 순간부터 target 까지 rAF 로 보간. */
function useCountUp(target: number, active: boolean, durationMs = 900) {
  const [val, setVal] = useState(0);
  useEffect(() => {
    if (!active) return;
    let raf = 0;
    let start = 0;
    const tick = (t: number) => {
      if (!start) start = t;
      const p = Math.min(1, (t - start) / durationMs);
      const eased = 1 - Math.pow(1 - p, 3);
      setVal(target * eased);
      if (p < 1) raf = requestAnimationFrame(tick);
      else setVal(target);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [active, target, durationMs]);
  return val;
}

/** active 시 text 를 한 글자씩 드러내는 타이핑 효과 (rAF 기반). */
function useTypewriter(text: string, active: boolean, durationMs = 1100) {
  const [n, setN] = useState(0);
  useEffect(() => {
    if (!active) {
      setN(0);
      return;
    }
    let raf = 0;
    let start = 0;
    const tick = (t: number) => {
      if (!start) start = t;
      const p = Math.min(1, (t - start) / durationMs);
      setN(Math.round(text.length * p));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [active, text, durationMs]);
  return text.slice(0, n);
}

// ── 공용 프레젠테이션 ────────────────────────────────────────────────────

/** 신규 keyframe 없이 state 기반 fade/slide-up 으로 블록을 드러내는 래퍼. */
function Reveal({
  show,
  delay = 0,
  children,
  className,
}: {
  show: boolean;
  delay?: number;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`transition-all duration-500 ease-out ${className ?? ''}`}
      style={{
        opacity: show ? 1 : 0,
        transform: show ? 'none' : 'translateY(14px)',
        transitionDelay: `${delay}ms`,
      }}
    >
      {children}
    </div>
  );
}

/** 진행 단계 라벨 — 현재 단계는 펄스 점 + indigo, 완료 단계는 체크. */
function StageLabel({ active, done, children }: { active: boolean; done: boolean; children: React.ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-2 text-sm font-medium transition-colors ${
        active ? 'text-ditto-indigo' : done ? 'text-text-secondary' : 'text-text-muted'
      }`}
    >
      {done ? (
        <span className="text-success">✓</span>
      ) : active ? (
        <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-ditto-indigo" />
      ) : (
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-border" />
      )}
      {children}
    </span>
  );
}

function SkipButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="absolute bottom-4 right-4 z-20 rounded-full border border-white/20 bg-white/10 px-3.5 py-1.5 text-xs font-medium text-white/80 transition-colors hover:bg-white/20"
    >
      건너뛰기 →
    </button>
  );
}

/** 시네마틱 공용 외곽 — auth-gradient hero 배경 + 글로우. */
function Stage({ children, onSkip }: { children: React.ReactNode; onSkip: () => void }) {
  return (
    <div
      className="relative overflow-hidden rounded-xl px-8 py-12 shadow-card"
      style={{ background: 'var(--auth-gradient)' }}
    >
      <div
        className="pointer-events-none absolute -right-10 -top-40 h-[500px] w-[500px] rounded-full"
        style={{ background: 'radial-gradient(circle, rgba(139,92,246,0.18) 0%, transparent 70%)' }}
      />
      <SkipButton onClick={onSkip} />
      <div className="relative z-10">{children}</div>
    </div>
  );
}

// ── 샘플 페어 선별 (agent 모드) ────────────────────────────────────────────
function pickSamplePair(result: HoldoutResult): HoldoutPair | null {
  const pairs = result.all_pairs ?? [];
  if (pairs.length === 0) return null;
  const interviewMatch = pairs.filter((p) => p.section === 'INT' && p.verdict === 'match');
  const pool = interviewMatch.length > 0 ? interviewMatch : pairs.filter((p) => p.verdict === 'match');
  const sorted = [...(pool.length > 0 ? pool : pairs)].sort((a, b) => b.confidence - a.confidence);
  const tight = sorted.find((p) => (p.agent_answer_display ?? p.agent_answer).length <= 200);
  return tight ?? sorted[0];
}

// ──────────────────────────────────────────────────────────────────────────
// 컴포넌트
// ──────────────────────────────────────────────────────────────────────────

export type OverallAgentRow = { id: string; name: string; emoji: string; score: number };

// 전체 연출 중간 단계에서 "질문 → 답변 → Judge 판정" 흐름을 보여주는 샘플.
// QualityPanel 이 holdout 결과에서 verdict 다양성·짧은 답변 위주로 선별해 넘긴다.
export type OverallSamplePair = {
  agentName: string;
  agentEmoji: string;
  question: string;
  agentAnswer: string;
  verdict: HoldoutVerdict;
};

type Props =
  | {
      mode: 'overall';
      agentRows: OverallAgentRow[];
      evaluatedCount: number;
      perAgentN: number;
      avg: number;
      samplePairs?: OverallSamplePair[];
      onComplete: () => void;
    }
  | {
      mode: 'agent';
      result: HoldoutResult;
      onComplete: () => void;
    };

export function HoldoutEvalCinematic(props: Props) {
  const doneRef = useRef(false);
  const finish = useCallback(() => {
    if (doneRef.current) return;
    doneRef.current = true;
    props.onComplete();
  }, [props]);

  if (props.mode === 'overall') return <OverallCinematic {...props} finish={finish} />;
  return <AgentCinematic {...props} finish={finish} />;
}

// ── 전체(프로젝트) 연출 ────────────────────────────────────────────────────
function OverallCinematic({
  agentRows,
  evaluatedCount,
  perAgentN,
  avg,
  samplePairs,
  finish,
}: Extract<Props, { mode: 'overall' }> & { finish: () => void }) {
  // 샘플 페어가 있으면 4단계(인트로→가속 Semantic Match 스트림→에이전트 바→평균), 없으면 3단계 폴백.
  // 스트림 지속시간은 카드 수·가속도 곡선에 따라 동적 계산.
  const samples = samplePairs ?? [];
  const hasSamples = samples.length > 0;
  const streamMs = hasSamples ? streamDurationMs(Math.min(samples.length, STREAM_TOTAL)) : 0;
  const durations = hasSamples ? [1300, streamMs, 2400, 1500] : [1500, 2400, 1700];
  const step = useTimeline(durations, 900, finish);
  const barsStep = hasSamples ? 2 : 1;
  const avgStep = hasSamples ? 3 : 2;
  const avgVal = useCountUp(avg * 100, step >= avgStep, 1300);

  return (
    <Stage onSkip={finish}>
      <p className="mb-4 text-[11px] font-medium tracking-[0.18em] text-white/55">
        MIND-BRIDGE · PERSONA TWIN · VALIDATION
      </p>
      <Reveal show={step >= 0}>
        <h2 className="mb-2 text-[clamp(22px,3vw,32px)] font-bold leading-tight tracking-tight text-white">
          {evaluatedCount}명의 AI 소비자를<br />실제 사람과 대조하는 중…
        </h2>
        <p className="text-sm text-white/65">
          각 에이전트에게 가려둔 {perAgentN}개 질문을 던지고, LLM-Judge 가 실제 응답과 의미적으로 비교합니다.
        </p>
      </Reveal>

      {/* 진행 단계 */}
      <Reveal show={step >= 1} className="mt-6">
        <div className="flex flex-wrap gap-x-5 gap-y-2">
          {hasSamples && (
            <StageLabel active={step === 1} done={step > 1}>
              샘플 응답 Semantic Match 채점
            </StageLabel>
          )}
          <StageLabel active={step === barsStep} done={step > barsStep}>
            {hasSamples ? '전체 에이전트 일치율 집계' : '응답 생성 & LLM-Judge 채점'}
          </StageLabel>
          <StageLabel active={step === avgStep} done={false}>
            프로젝트 평균 집계
          </StageLabel>
        </div>
      </Reveal>

      {/* 가속도 Semantic Match 스트림 — step 1 동안 노출. 20개 카드가 가속도 곡선으로 떨어짐. */}
      {hasSamples && step >= 1 && step < barsStep && (
        <QAStream pairs={samples} />
      )}

      {/* 에이전트 행 — barsStep 도달 시 stagger 로 점수 채움 */}
      {step >= barsStep && (
        <div className="mt-6 space-y-2">
          {agentRows.map((a, i) => {
            const pct = Math.round(a.score * 100);
            return (
              <Reveal key={a.id} show delay={i * 110}>
                <div className="flex items-center gap-3 rounded-lg border border-white/10 bg-white/5 px-3 py-2">
                  <span className="text-lg">{a.emoji}</span>
                  <span className="w-24 shrink-0 truncate text-sm font-medium text-white/90">{a.name}</span>
                  <div className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-white/15">
                    <div
                      className="h-full rounded-full bg-white/80 transition-all duration-700 ease-out"
                      style={{ width: `${pct}%`, transitionDelay: `${i * 110}ms` }}
                    />
                  </div>
                  <span className="w-10 shrink-0 text-right text-sm font-bold tabular-nums text-white">
                    {pct}%
                  </span>
                </div>
              </Reveal>
            );
          })}
        </div>
      )}

      {/* 평균 일치율 */}
      <Reveal show={step >= avgStep} className="mt-7 text-center">
        <p className="text-xs font-medium tracking-[0.14em] text-white/55">프로젝트 평균 일치율</p>
        <div className="mt-1 text-[clamp(48px,8vw,84px)] font-bold leading-none tracking-tight text-white">
          {Math.round(avgVal)}
          <sup className="ml-1 align-super text-[0.3em] text-white/70">%</sup>
        </div>
      </Reveal>
    </Stage>
  );
}

// ── 가속도 Semantic Match 스트림 ──────────────────────────────────────────
// SimilarityDashboard 의 EvidenceBlock "✓ SEMANTIC MATCH" 배너 스타일을 한 줄 카드로 압축.
// 20개 카드가 처음엔 느긋하게 → 끝엔 빠르게 떨어지면서 채점되는 reel.
// 보이는 윈도우는 5장이고, 새 카드가 들어올 때마다 가장 오래된 카드가 위로 밀려 사라진다.
const STREAM_TOTAL = 20;
const STREAM_VISIBLE = 5;
const STREAM_CARD_PX = 52; // 한 줄 카드 높이(44) + gap(8)
const STREAM_START_MS = 450; // 첫 카드 등장 간격
const STREAM_END_MS = 70;    // 마지막 카드 등장 간격

// 선형 보간한 카드별 등장 시각(절대 timestamp, ms). step1 시작이 t=0.
function streamSchedule(n: number): number[] {
  const ts: number[] = [];
  let acc = 0;
  for (let i = 0; i < n; i++) {
    const interval = STREAM_START_MS - (STREAM_START_MS - STREAM_END_MS) * (i / Math.max(1, n - 1));
    acc += interval;
    ts.push(Math.round(acc));
  }
  return ts;
}

// step1 의 권장 지속시간 — 마지막 카드 후 settle 800ms 추가.
function streamDurationMs(n: number): number {
  const sched = streamSchedule(n);
  return (sched[sched.length - 1] ?? 0) + 800;
}

// ✓ SEMANTIC MATCH / ✗ NO MATCH 의 binary 표현. partial 은 NO MATCH 로 합쳐 보수적으로 표시.
function isSemanticMatch(v: HoldoutVerdict): boolean {
  return v === 'match';
}

function QAStream({ pairs }: { pairs: OverallSamplePair[] }) {
  const limited = useMemo(() => pairs.slice(0, STREAM_TOTAL), [pairs]);
  const schedule = useMemo(() => streamSchedule(limited.length), [limited.length]);
  const [revealed, setRevealed] = useState(0);

  // 절대 timestamp 로 setTimeout 큐. 마운트 시 1회 세팅, 언마운트 시 정리.
  useEffect(() => {
    const timers: ReturnType<typeof setTimeout>[] = [];
    schedule.forEach((t, i) => {
      timers.push(setTimeout(() => setRevealed(i + 1), t));
    });
    return () => timers.forEach(clearTimeout);
  }, [schedule]);

  // 스크롤 오프셋 — STREAM_VISIBLE 초과 시 위로 밀어 올린다.
  const offset = Math.max(0, revealed - STREAM_VISIBLE) * STREAM_CARD_PX;
  const containerHeight = STREAM_VISIBLE * STREAM_CARD_PX;

  return (
    <div className="mt-6">
      <div className="mb-2 flex items-center justify-between text-[11px] font-medium tracking-[0.04em] text-white/55">
        <span>SEMANTIC MATCH · LLM-Judge</span>
        <span className="tabular-nums">{Math.min(revealed, STREAM_TOTAL)} / {STREAM_TOTAL}</span>
      </div>
      <div
        className="relative overflow-hidden rounded-xl border border-white/10 bg-white/[0.03]"
        style={{ height: containerHeight }}
      >
        <div
          className="absolute inset-x-0 top-0 flex flex-col gap-2 p-2 transition-transform duration-300 ease-out"
          style={{ transform: `translateY(${-offset}px)` }}
        >
          {limited.slice(0, revealed).map((p, i) => (
            <StreamCard key={i} pair={p} />
          ))}
        </div>
        {/* 상단 fade — 위로 사라지는 카드를 부드럽게 가린다 */}
        <div
          className="pointer-events-none absolute inset-x-0 top-0 z-10 h-6"
          style={{ background: 'linear-gradient(180deg, rgba(30,27,75,0.85), transparent)' }}
        />
      </div>
    </div>
  );
}

function StreamCard({ pair }: { pair: OverallSamplePair }) {
  const matched = isSemanticMatch(pair.verdict);
  const q = pair.question.length > 70 ? pair.question.slice(0, 68) + '…' : pair.question;
  return (
    <div
      className="flex h-11 shrink-0 items-center gap-2.5 rounded-lg border border-white/10 bg-white/5 px-3"
      style={{
        opacity: 0,
        animation: 'fadeInUp 0.35s ease-out forwards',
      }}
    >
      <span className="shrink-0 text-base leading-none">{pair.agentEmoji}</span>
      <span className="w-20 shrink-0 truncate text-[11px] font-medium text-white/55">
        {pair.agentName}
      </span>
      <span className="min-w-0 flex-1 truncate text-[12px] text-white/85">Q. {q}</span>
      <span
        className={
          'shrink-0 rounded-full px-2.5 py-1 text-[10px] font-bold tracking-[0.04em] text-white ' +
          (matched ? 'bg-success' : 'bg-error')
        }
        style={{
          opacity: 0,
          transform: 'scale(0.5)',
          animation: 'eval-stamp-in 0.4s cubic-bezier(0.34,1.56,0.64,1) 180ms forwards',
        }}
      >
        {matched ? '✓ SEMANTIC MATCH' : '✗ NO MATCH'}
      </span>
    </div>
  );
}

// ── 개별(에이전트) 연출 ────────────────────────────────────────────────────
function AgentCinematic({
  result,
  finish,
}: Extract<Props, { mode: 'agent' }> & { finish: () => void }) {
  const sample = useMemo(() => pickSamplePair(result), [result]);
  const lensSorted = useMemo(
    () => [...result.by_lens].sort((a, b) => b.agreement - a.agreement),
    [result.by_lens],
  );
  const name = result.agent_display_name ?? '이 에이전트';

  // step 0: 질문 투입 / 1: 응답 생성(타이핑) / 2: Judge 채점(카운터) / 3: 6-Lens 집계 / 4: 전체 일치율
  const step = useTimeline([1400, 1500, 1500, 1500, 1600], 800, finish);

  const sampleAnswerFull = sample
    ? (sample.agent_answer_display ?? sample.agent_answer).slice(0, 220)
    : '';
  const typed = useTypewriter(sampleAnswerFull, step === 1, 1200);

  const nMatch = useCountUp(result.n_match, step >= 2, 900);
  const nPartial = useCountUp(result.n_partial, step >= 2, 900);
  const nNoMatch = useCountUp(result.n_no_match, step >= 2, 900);
  const bigPct = useCountUp(result.agreement_score * 100, step >= 4, 1300);

  return (
    <Stage onSkip={finish}>
      <p className="mb-4 text-[11px] font-medium tracking-[0.18em] text-white/55">
        평가 진행 중 · {name}
      </p>

      {/* 진행 단계 */}
      <div className="mb-6 flex flex-wrap gap-x-4 gap-y-2">
        <StageLabel active={step === 0} done={step > 0}>질문 투입</StageLabel>
        <StageLabel active={step === 1} done={step > 1}>응답 생성</StageLabel>
        <StageLabel active={step === 2} done={step > 2}>LLM-Judge 채점</StageLabel>
        <StageLabel active={step === 3} done={step > 3}>6-Lens 집계</StageLabel>
        <StageLabel active={step === 4} done={false}>일치율 산출</StageLabel>
      </div>

      {/* step 0~1: 샘플 Q + 에이전트 응답 타이핑 */}
      {sample && step <= 1 && (
        <Reveal show={step >= 0}>
          <div className="rounded-lg border border-white/10 bg-white/5 p-5">
            <p className="flex items-start gap-2 text-sm leading-relaxed text-white/80">
              <span className="mt-[2px] shrink-0 text-xs font-bold text-white/60">Q.</span>
              <span>{sample.question}</span>
            </p>
            <div className="mt-4 min-h-[3.5rem] border-t border-white/10 pt-4">
              <span className="rounded-sm bg-white/15 px-2 py-0.5 text-[10px] font-bold tracking-[0.06em] text-white/80">
                AI AGENT
              </span>
              {step === 0 ? (
                <p className="mt-2 flex items-center gap-2 text-sm text-white/50">
                  <Spinner size="sm" /> 실제 사람 답변을 가리고 동일 질문을 던지는 중…
                </p>
              ) : (
                <p className="mt-2 text-[15px] leading-relaxed text-white">
                  {typed}
                  <span className="ml-0.5 inline-block h-4 w-[2px] animate-pulse bg-white/70 align-middle" />
                </p>
              )}
            </div>
          </div>
        </Reveal>
      )}

      {/* step 2: Judge 채점 카운터 */}
      {step === 2 && (
        <Reveal show>
          <p className="mb-4 text-sm text-white/65">
            LLM-Judge 가 실제 사람 답변과 에이전트 답변을 {result.n_total}개 문항에서 대조합니다.
          </p>
          <div className="grid grid-cols-3 gap-3">
            <CounterCard label="일치" value={Math.round(nMatch)} tone="success" />
            <CounterCard label="부분" value={Math.round(nPartial)} tone="warning" />
            <CounterCard label="불일치" value={Math.round(nNoMatch)} tone="error" />
          </div>
        </Reveal>
      )}

      {/* step 3: 6-Lens 막대 차오름 */}
      {step === 3 && (
        <Reveal show>
          <p className="mb-4 text-sm text-white/65">6개 렌즈 영역별로 일치도를 집계합니다.</p>
          <div className="flex h-[180px] items-end justify-center gap-3">
            {lensSorted.map((b, i) => {
              const pct = Math.round(b.agreement * 100);
              return (
                <div key={b.lens} className="flex h-full max-w-[80px] flex-1 flex-col items-center justify-end">
                  <div className="mb-1.5 text-xs font-bold tabular-nums text-white">{pct}%</div>
                  <div
                    className="w-full rounded-t-md transition-all duration-700 ease-out"
                    style={{
                      height: `${Math.max(pct, 2)}%`,
                      minHeight: 3,
                      background: LENS_TONE_GRADIENT[lensTone(b.agreement)],
                      transitionDelay: `${i * 90}ms`,
                    }}
                  />
                  <div className="mt-1.5 text-[10px] font-medium tracking-[0.04em] text-white/55">{b.lens}</div>
                </div>
              );
            })}
          </div>
        </Reveal>
      )}

      {/* step 4: 전체 일치율 */}
      {step >= 4 && (
        <Reveal show className="text-center">
          <p className="text-xs font-medium tracking-[0.14em] text-white/55">전체 일치율</p>
          <div className="mt-1 text-[clamp(56px,11vw,120px)] font-bold leading-none tracking-tight text-white">
            {Math.round(bigPct)}
            <sup className="ml-1 align-super text-[0.3em] text-white/70">%</sup>
          </div>
          <p className="mt-3 text-sm text-white/65">
            {name}의 응답 {Math.round(result.agreement_score * 100)}%가 실제 사람과 의미적으로 일치했습니다
          </p>
        </Reveal>
      )}
    </Stage>
  );
}

function CounterCard({ label, value, tone }: { label: string; value: number; tone: 'success' | 'warning' | 'error' }) {
  const dot = tone === 'success' ? 'bg-success' : tone === 'warning' ? 'bg-warning' : 'bg-error';
  return (
    <div className="rounded-lg border border-white/10 bg-white/5 px-4 py-5 text-center">
      <div className="text-3xl font-bold tabular-nums text-white">{value}</div>
      <p className="mt-1 inline-flex items-center gap-1.5 text-xs font-medium text-white/70">
        <span className={`inline-block h-1.5 w-1.5 rounded-full ${dot}`} />
        {label}
      </p>
    </div>
  );
}
