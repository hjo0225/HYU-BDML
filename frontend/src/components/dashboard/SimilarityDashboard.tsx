'use client';

// 홀드아웃 유사도 대시보드 v7 (plan 0023 + 인터뷰 보강).
// 5섹션 스토리텔링: HERO → 직접맞히기 → 증거 → 89% 헤드라인 → 6-Lens 막대·설명 → Takeaway.
// 단 하나의 질문에 답한다: "이 에이전트는 우리가 조사한 사람과 정말 그 사람처럼 답할 수 있는가?"

import { useMemo, useState } from 'react';
import type { HoldoutPair, HoldoutResult } from '@/lib/types';
import { lensTone, LENS_TONE_GRADIENT, LENS_TONE_TEXT } from '@/lib/lensTone';

interface Props {
  result: HoldoutResult;
}

// ── Lens 메타 (v7 설명문 — 청중·심사위원 발표용) ──────────────────────────
const LENS_META: Record<
  string,
  { name: string; sub: string; desc: string; scales: string; rank: number }
> = {
  L6: {
    name: '시간선호',
    sub: '미래를 위해 기다릴 수 있는 사람인가?',
    desc: '할인율, 현재 편향, 성실성을 측정합니다. 이 점수가 높으면 즉각적 보상보다 장기적 이익을 선호하고, 계획적이고 성실한 행동 패턴을 보이는 사람입니다.',
    scales: '척도: 할인율 · 현재 편향 · 성실성',
    rank: 6,
  },
  L3: {
    name: '동기 구조',
    sub: '무엇이 이 사람을 움직이게 하는가?',
    desc: '조절초점(예방/촉진), 자기지향 vs 타인지향 가치, 독특성 욕구를 측정합니다. 이 렌즈의 일치가 높다면 에이전트가 그 사람이 ‘왜’ 행동하는지의 내적 동기를 정확히 파악하고 있다는 의미입니다.',
    scales: '척도: 조절초점 · Agentic/Communal 가치 · 독특성 욕구',
    rank: 3,
  },
  L5: {
    name: '가치 사슬',
    sub: '이 사람의 소비와 삶의 철학은?',
    desc: '소비자 미니멀리즘과 친환경 가치를 측정합니다. 높은 일치는 에이전트가 이 사람의 라이프스타일 가치관 — 무엇을 사고, 무엇을 거부하는지 — 을 정확히 반영하고 있다는 뜻입니다.',
    scales: '척도: 소비자 미니멀리즘 · 친환경 가치',
    rank: 5,
  },
  L2: {
    name: '의사결정 스타일',
    sub: '이 사람은 결정을 어떻게 내리는가?',
    desc: '극대화 성향, 인지 종결 욕구, 인지 욕구, 인지 반사를 측정합니다. 최선을 끝까지 찾는 사람인지, 빠르게 결론짓는 사람인지를 구분합니다.',
    scales: '척도: 극대화 · 인지 종결 욕구 · 인지 욕구 · CRT',
    rank: 2,
  },
  L4: {
    name: '사회적 영향',
    sub: '타인과 사회가 이 사람에게 미치는 영향은?',
    desc: '자기 감시, 개인/집단주의, 공감, 사회적 바람직성, 잘못된 합의, 독재자 게임을 측정합니다. 사회적 맥락에서 사람의 행동은 가장 예측하기 어렵습니다.',
    scales: '척도: 자기 감시 · 개인/집단주의 · 공감 · 사회적 바람직성',
    rank: 4,
  },
  L1: {
    name: '경제적 합리성',
    sub: '돈 앞에서 이 사람은 합리적인가?',
    desc: '위험/손실 회피, 심적 회계, 소비 습관, 프레이밍 효과를 측정합니다. 인간은 경제적 의사결정에서 체계적으로 비합리적이지만, LLM은 "합리적 경제인"에 가까운 기본값을 갖고 있어 이 영역에서 가장 큰 괴리가 발생합니다.',
    scales: '척도: 위험 회피 · 손실 회피 · 심적 회계 · 프레이밍',
    rank: 1,
  },
};

// §01·§02 페어 선별 — 포토이즘 인터뷰 (section='INT') 답변만 사용.
// 객관식 척도 답변은 "4 - 어느 정도 동의한다" 같은 raw 라 인간/AI 비대칭이 어색.
// 자유서술 인터뷰만으로 카드 구성해야 demo 임팩트가 살아남.
function selectInterviewMoments(allPairs: HoldoutPair[] | undefined): HoldoutPair[] {
  if (!allPairs || allPairs.length === 0) return [];
  const interview = allPairs.filter((p) => p.section === 'INT' && p.verdict === 'match');
  // confidence 내림차순
  const sorted = [...interview].sort((a, b) => b.confidence - a.confidence);
  // 1차: 적당히 짧은 답변 + 높은 confidence (시각적 비교 임팩트)
  const tight = sorted.filter(
    (p) => p.human_answer.length <= 180 && p.agent_answer.length <= 240 && p.confidence >= 0.8,
  );
  if (tight.length >= 4) return tight.slice(0, 5);
  // 2차: confidence ≥ 0.8 만족 (길이 무관)
  const conf = sorted.filter((p) => p.confidence >= 0.8);
  if (conf.length >= 4) return conf.slice(0, 5);
  // fallback: 인터뷰 match top
  return sorted.slice(0, 5);
}

export function SimilarityDashboard({ result }: Props) {
  const bigPct = Math.round(result.agreement_score * 100);
  // §01·§02 는 포토이즘 인터뷰(section='INT') match 페어만 사용. 객관식은 비대칭이라 제외.
  // §01 hookPair = 인터뷰 페어 중 가장 잘 나온 1개 (=정렬 top), §02 evidence = 그 다음 4개.
  const interviewMoments = useMemo(
    () => selectInterviewMoments(result.all_pairs),
    [result.all_pairs],
  );
  const hookPair = interviewMoments[0] ?? null;
  const evidence = useMemo(
    () => interviewMoments.slice(1, 5),
    [interviewMoments],
  );

  // by_lens 를 rank(시간선호→동기→가치→의사결정→사회→경제) 순으로 정렬해 무너지는 흐름 연출
  const lensSorted = useMemo(() => {
    return [...result.by_lens].sort((a, b) => b.agreement - a.agreement);
  }, [result.by_lens]);

  // takeaway 숫자 — 76% 같이 "본인에게 묻지 않아도 시뮬레이션 가능" 의 prop
  const sourceLabel = result.agent_source_ref ?? '실제 응답자';

  return (
    <div className="space-y-12">
      {/* ===== HERO ===== */}
      <div
        className="relative overflow-hidden rounded-lg px-12 py-14"
        style={{ background: 'var(--auth-gradient)' }}
      >
        <div
          className="pointer-events-none absolute -right-10 -top-40 h-[500px] w-[500px] rounded-full"
          style={{
            background: 'radial-gradient(circle, rgba(139,92,246,0.15) 0%, transparent 70%)',
          }}
        />
        <div className="relative z-10">
          <p className="mb-5 text-[11px] font-medium tracking-[0.18em] text-white/55">
            MIND-BRIDGE · PERSONA TWIN
          </p>
          <h1 className="mb-4 text-[clamp(28px,4vw,44px)] font-bold leading-[1.1] tracking-tight text-white">
            이 에이전트는<br />
            진짜 <span className="font-normal">{result.agent_display_name ?? '그 사람'}</span>처럼
            답할 수 있을까?
          </h1>
          <p className="whitespace-nowrap text-base text-white/65">
            실제 사람 1명과, 그 사람의 페르소나로 만든 AI 에이전트에게 동일한 {result.n_total}개 질문을 던졌습니다.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Chip>n = {result.n_total} 응답</Chip>
            <Chip>6-Lens Framework</Chip>
            <Chip>Single-subject validation</Chip>
          </div>
        </div>
      </div>

      {/* ===== §01 — 직접 맞혀보세요 ===== */}
      {hookPair && (
        <Section num="01" title="먼저, 직접 맞혀보세요">
          <HookGame pair={hookPair} />
        </Section>
      )}

      {/* ===== §02 — 증거 ===== */}
      {evidence.length > 0 && (
        <Section num="02" title="나란히 비교해 보세요">
          <div className="flex flex-col gap-5">
            {evidence.map((p) => (
              <EvidenceBlock key={p.question_id} pair={p} />
            ))}
          </div>
        </Section>
      )}

      {/* ===== §03 — THE NUMBER ===== */}
      <Section num="03" title="전체 일치율">
        <div className="rounded-lg border border-border bg-surface px-6 py-12 text-center shadow-card">
          <div className="mb-4 text-[clamp(96px,16vw,180px)] font-bold leading-[0.9] tracking-[-0.05em] text-text-primary">
            {bigPct}
            <sup className="ml-1 align-super text-[0.3em] text-ditto-indigo">%</sup>
          </div>
          <p className="mb-7 whitespace-nowrap text-lg text-text-muted">
            에이전트 응답의 {bigPct}%가 실제 사람의 응답과 의미적으로 일치했습니다
          </p>
          <div className="inline-flex flex-wrap items-center justify-center gap-5 rounded-full border border-border px-5 py-2.5 text-xs text-text-muted">
            <CountChip color="success" n={result.n_match} label="일치" />
            <span className="text-border">·</span>
            <CountChip color="warning" n={result.n_partial} label="부분" />
            <span className="text-border">·</span>
            <CountChip color="error" n={result.n_no_match} label="불일치" />
            <span className="border-l border-border pl-4 text-text-muted">
              전체 <span className="font-bold text-text-primary">{result.n_total}</span>
            </span>
          </div>
        </div>
      </Section>

      {/* ===== §04 — 6-LENS 분석 ===== */}
      <Section num="04" title="6-Lens 영역별 분석">
        <div className="overflow-hidden rounded-lg border border-border bg-surface shadow-card">
          <LensChart lensSorted={lensSorted} />
          <div>
            {lensSorted.map((b) => (
              <LensDescItem key={b.lens} lens={b.lens} agreement={b.agreement} n={b.n} />
            ))}
          </div>
        </div>
      </Section>

      {/* ===== TAKEAWAY ===== */}
      <div
        className="relative overflow-hidden rounded-lg px-8 py-14 text-center"
        style={{ background: 'var(--auth-gradient)' }}
      >
        <div
          className="pointer-events-none absolute -bottom-32 -left-10 h-[400px] w-[400px] rounded-full"
          style={{
            background: 'radial-gradient(circle, rgba(139,92,246,0.2) 0%, transparent 70%)',
          }}
        />
        <p className="relative z-10 mx-auto max-w-[700px] text-[clamp(20px,3vw,32px)] font-bold leading-[1.3] tracking-tight text-white">
          이 사람의 미래 의사결정 중<br />
          <span className="text-white/50">~{bigPct}%</span>는<br />
          본인에게 묻지 않아도 시뮬레이션할 수 있습니다.
        </p>
      </div>

      {/* ===== FOOTER ===== */}
      <div className="flex justify-between border-t border-border pt-6 text-[11px] tracking-[0.04em] text-text-muted">
        <span>MIND-BRIDGE · PERSONA TWIN · {sourceLabel}</span>
        <span>
          HUMAN ↔ AI · n = {result.n_total} · {result.judge_model}
        </span>
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// 서브 컴포넌트
// ──────────────────────────────────────────────────────────────────────────

function Section({
  num,
  title,
  children,
}: {
  num: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <div className="mb-6 flex items-baseline gap-3">
        <span className="text-xs font-bold tracking-[0.1em] text-ditto-indigo">
          {num}
        </span>
        <h2 className="text-[22px] font-bold tracking-tight text-text-primary">{title}</h2>
      </div>
      {children}
    </section>
  );
}

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-full border border-white/15 bg-white/10 px-3 py-1 text-[11px] font-medium tracking-[0.02em] text-white/75">
      {children}
    </span>
  );
}

function CountChip({
  color,
  n,
  label,
}: {
  color: 'success' | 'warning' | 'error';
  n: number;
  label: string;
}) {
  const dot =
    color === 'success' ? 'bg-success' : color === 'warning' ? 'bg-warning' : 'bg-error';
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`inline-block h-1.5 w-1.5 rounded-full ${dot}`} />
      <span className="font-bold text-text-primary">{n}</span> {label}
    </span>
  );
}

// ── §01 Hook 게임 (정답 가린 2 카드 → 클릭 → reveal) ──────────────────
function HookGame({ pair }: { pair: HoldoutPair }) {
  // 인간/AI 답변을 무작위로 A·B 에 배치 (seed 는 question_id 해시로 결정적)
  const humanFirst = useMemo(() => {
    const h = pair.question_id.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0);
    return h % 2 === 0;
  }, [pair.question_id]);

  const [revealed, setRevealed] = useState<'A' | 'B' | null>(null);
  const aIsHuman = humanFirst;
  const humanAnswer = pair.human_answer_display ?? pair.human_answer;
  const agentAnswer = pair.agent_answer_display ?? pair.agent_answer;
  const cardA = aIsHuman ? humanAnswer : agentAnswer;
  const cardB = aIsHuman ? agentAnswer : humanAnswer;
  const correct: 'A' | 'B' = aIsHuman ? 'A' : 'B';

  const onPick = (choice: 'A' | 'B') => {
    if (revealed) return;
    setRevealed(choice);
  };

  return (
    <div>
      <p className="my-4 text-center text-[clamp(22px,3vw,36px)] font-bold tracking-tight text-text-primary">
        <span className="text-ditto-indigo">&quot;</span>둘 중 어느 쪽이 사람일까요?
        <span className="text-ditto-indigo">&quot;</span>
      </p>
      <div className="mx-auto mb-6 max-w-[640px] rounded-md border border-border bg-bg/60 px-5 py-3">
        <p className="flex items-start gap-2 text-sm leading-[1.6] text-text-secondary">
          <span className="mt-[1px] flex-shrink-0 text-xs font-bold text-ditto-indigo">Q.</span>
          <span>{pair.question}</span>
        </p>
      </div>

      <div className="mb-3 grid grid-cols-1 gap-5 md:grid-cols-2">
        <HookCard
          label="응답 A"
          quote={cardA}
          revealed={revealed}
          isCorrect={correct === 'A'}
          onClick={() => onPick('A')}
        />
        <HookCard
          label="응답 B"
          quote={cardB}
          revealed={revealed}
          isCorrect={correct === 'B'}
          onClick={() => onPick('B')}
        />
      </div>

      {!revealed && (
        <p className="text-center text-xs font-medium text-text-muted">카드를 클릭해보세요</p>
      )}

      {revealed && (
        <div className="mt-4 rounded-md border border-ditto-indigo/20 bg-ditto-indigo-light px-7 py-5 text-center">
          <p className="mb-1 text-[11px] font-medium tracking-[0.14em] text-ditto-indigo">ANSWER</p>
          <p className="text-base font-bold text-text-primary">
            {correct} = 실제 사람 · {correct === 'A' ? 'B' : 'A'} = AI 에이전트
          </p>
        </div>
      )}
    </div>
  );
}

function HookCard({
  label,
  quote,
  revealed,
  isCorrect,
  onClick,
}: {
  label: string;
  quote: string;
  revealed: 'A' | 'B' | null;
  isCorrect: boolean;
  onClick: () => void;
}) {
  let stateClass =
    'border-border hover:-translate-y-0.5 hover:border-ditto-indigo hover:shadow-elevated';
  if (revealed) {
    stateClass = isCorrect
      ? 'border-success shadow-[0_0_16px_rgba(16,185,129,0.12)]'
      : 'border-error opacity-50';
  }
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={revealed !== null}
      className={`rounded-lg border bg-surface p-7 text-left shadow-card transition-all ${stateClass} ${
        revealed ? 'cursor-default' : 'cursor-pointer'
      }`}
    >
      <p className="mb-3.5 flex items-center gap-2 text-[11px] font-medium tracking-[0.12em] text-text-muted">
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-ditto-indigo" />
        {label}
      </p>
      <p className="text-[17px] leading-[1.55] text-text-primary">&quot;{quote}&quot;</p>
    </button>
  );
}

// ── §02 Evidence Q&A 블록 ─────────────────────────────────────────────
function EvidenceBlock({ pair }: { pair: HoldoutPair }) {
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface shadow-card">
      <div className="flex items-start gap-3 border-b border-border px-6 py-5">
        <span className="mt-[5px] flex-shrink-0 text-xs font-bold text-ditto-indigo">Q.</span>
        <span className="flex-1 text-[16px] font-semibold leading-[1.5] text-text-primary">
          {pair.question}
        </span>
        <span className="ml-auto flex-shrink-0 self-center rounded-full border border-border px-2.5 py-1 text-[11px] font-medium tracking-[0.02em] text-text-muted">
          {pair.domain ? '포토이즘 도메인' : LENS_META[pair.lens]?.name ?? pair.lens} · {pair.lens}
        </span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2">
        <div className="border-b border-border p-6 md:border-b-0 md:border-r">
          <p className="mb-3">
            <span className="rounded-sm bg-ditto-indigo/10 px-2 py-0.5 text-[10px] font-bold tracking-[0.06em] text-ditto-indigo">
              HUMAN
            </span>
          </p>
          <p className="text-[15px] leading-[1.6] text-text-primary">
            &quot;{pair.human_answer_display ?? pair.human_answer}&quot;
          </p>
        </div>
        <div className="p-6">
          <p className="mb-3">
            <span className="rounded-sm bg-ditto-violet/10 px-2 py-0.5 text-[10px] font-bold tracking-[0.06em] text-ditto-violet">
              AI AGENT
            </span>
          </p>
          <p className="text-[15px] leading-[1.6] text-text-primary">
            &quot;{pair.agent_answer_display ?? pair.agent_answer}&quot;
          </p>
        </div>
      </div>
      <div className="flex items-center gap-1.5 border-t border-border bg-success/5 px-6 py-2.5 text-[11px] font-medium tracking-[0.04em] text-success">
        <span className="text-[13px]">✓</span> SEMANTIC MATCH
      </div>
    </div>
  );
}

// ── §04 6-Lens 막대 차트 ──────────────────────────────────────────────
function LensChart({
  lensSorted,
}: {
  lensSorted: HoldoutResult['by_lens'];
}) {
  return (
    <div className="px-8 pb-6 pt-9">
      <div className="relative flex h-[260px] items-end justify-center gap-4">
        <div
          className="pointer-events-none absolute inset-0 z-0"
          style={{
            background:
              'repeating-linear-gradient(to bottom, transparent, transparent calc(25% - 1px), var(--border) calc(25% - 1px), var(--border) 25%)',
          }}
        />
        {lensSorted.map((b) => {
          const pct = Math.round(b.agreement * 100);
          const gradient = LENS_TONE_GRADIENT[lensTone(b.agreement)];
          return (
            <div
              key={b.lens}
              className="relative z-10 flex h-full max-w-[110px] flex-1 flex-col items-center justify-end"
            >
              <div className="mb-1.5 text-sm font-bold tabular-nums text-text-primary">{pct}%</div>
              <div
                className="w-full rounded-t-md"
                style={{ height: `${Math.max(pct, 2)}%`, background: gradient, minHeight: 3 }}
              />
            </div>
          );
        })}
      </div>
      <div className="flex justify-center gap-4 px-8 pt-4">
        {lensSorted.map((b) => {
          const meta = LENS_META[b.lens];
          return (
            <div key={b.lens} className="max-w-[110px] flex-1 text-center">
              <div className="text-[13px] font-semibold text-text-primary">
                {meta?.name ?? b.lens}
              </div>
              <div className="text-[10px] font-medium tracking-[0.04em] text-text-muted">{b.lens}</div>
              <div className="text-[10px] tabular-nums text-text-muted">n={b.n}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── §04 Lens 설명 카드 ────────────────────────────────────────────────
function LensDescItem({
  lens,
  agreement,
  n,
}: {
  lens: string;
  agreement: number;
  n: number;
}) {
  const meta = LENS_META[lens];
  if (!meta) return null;
  const pct = Math.round(agreement * 100);
  const pctColor = LENS_TONE_TEXT[lensTone(agreement)];

  return (
    <div className="grid grid-cols-[80px_1fr] items-start gap-4 border-b border-border px-8 py-5 transition-colors last:border-b-0 hover:bg-bg">
      <div className="flex flex-col items-center gap-1 pt-0.5">
        <span className="text-[11px] font-bold tracking-[0.06em] text-text-muted">
          {lens}
        </span>
        <span className={`text-xl font-bold tabular-nums ${pctColor}`}>{pct}%</span>
      </div>
      <div>
        <h4 className="mb-1.5 text-base font-bold text-text-primary">{meta.name}</h4>
        <p className="mb-2 text-[13px] font-medium text-text-secondary">{meta.sub}</p>
        <p className="text-[14px] leading-[1.65] text-text-muted">{meta.desc}</p>
        <p className="mt-2 text-[11px] text-text-muted">
          {meta.scales} · <span className="tabular-nums">n={n}</span>
        </p>
      </div>
    </div>
  );
}
