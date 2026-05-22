'use client';

// 데모 가이드의 정적/단순 단계들 (plan 0008): 1 의뢰서 · 2 설문설계 · 3 수집 · 6 보고서 · 7 제공.
import { useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { EmptyState } from '@/components/ui/EmptyState';
import { Spinner } from '@/components/ui/Spinner';
import { FGIReportView } from '@/components/fgi/FGIReportView';
import {
  DEMO_BRIEF,
  DEMO_COLLECTION,
  DEMO_INTERVIEW,
  DEMO_SURVEYS,
  SURVEY_LENS_LABELS,
} from '@/lib/demoScenario';
import type { FGIReport } from '@/lib/types';

type SurveyDef = (typeof DEMO_SURVEYS)[number];
type SurveyItemDef = SurveyDef['items'][number];

// 문항을 렌즈(L1~L6·통제)별로 묶는다. 첫 등장 순서 보존.
function groupSurveyItems(items: readonly SurveyItemDef[]): [string, SurveyItemDef[]][] {
  const map = new Map<string, SurveyItemDef[]>();
  for (const it of items) {
    const k = it.lens || '기타';
    const arr = map.get(k);
    if (arr) arr.push(it); else map.set(k, [it]);
  }
  return Array.from(map.entries());
}

// 설문 카드 (범용/도메인 공용) — 렌즈별 접기 + 척도 + 실제 적용 문항 전체.
function SurveyCard({ survey, generated }: { survey: SurveyDef; generated?: boolean }) {
  const openByDefault = survey.items.length <= 24;
  return (
    <Card>
      <div className="mb-1 flex items-start justify-between gap-2">
        <h3 className="font-semibold text-text-primary">{survey.title}</h3>
        <Badge variant={generated ? 'success' : 'violet'} size="sm">{generated ? '✨ 자동 생성' : '설문'}</Badge>
      </div>
      <p className="text-xs text-text-muted">{survey.desc}</p>
      <p className="mb-1 mt-1 text-2xs text-text-muted">{survey.note}</p>
      <p className="mb-3 text-2xs text-text-muted">총 {survey.items.length}문항 · 렌즈별로 펼쳐 보세요.</p>
      <div className="space-y-2">
        {groupSurveyItems(survey.items).map(([lensKey, items]) => (
          <details key={lensKey} open={openByDefault} className="group rounded-lg border border-border bg-bg/40">
            <summary className="flex cursor-pointer select-none items-center gap-1.5 px-3 py-2 text-sm font-semibold text-text-primary">
              <span className="text-text-muted transition-transform group-open:rotate-90">▸</span>
              {SURVEY_LENS_LABELS[lensKey] ?? lensKey}
              <span className="text-2xs font-normal text-text-muted">({items.length}문항)</span>
            </summary>
            <ul className="space-y-2 px-3 pb-3 text-sm text-text-secondary">
              {items.map((it, i) => (
                <li key={i} className="rounded-lg border border-border bg-surface p-2.5">
                  <div className="mb-1 flex flex-wrap items-center gap-x-2 gap-y-0.5">
                    {it.scaleName && <span className="text-2xs font-medium text-text-secondary">{it.scaleName}</span>}
                    {it.scale && <span className="text-2xs text-text-muted">· {it.scale}</span>}
                  </div>
                  <span>{it.q}</span>
                </li>
              ))}
            </ul>
          </details>
        ))}
      </div>
    </Card>
  );
}

// ── 1단계: 기업 의뢰 접수 ──────────────────────────────────────────────────
export function DemoBriefStep() {
  return (
    <Card>
      <div className="mb-4 flex items-center gap-2">
        <Badge variant="indigo">의뢰 접수</Badge>
        <span className="text-sm text-text-muted">기업 → Mind-Bridge</span>
      </div>
      <h2 className="mb-1 text-xl font-bold text-text-primary">{DEMO_BRIEF.company} 리서치 의뢰서</h2>
      <p className="mb-5 text-sm text-text-secondary">{DEMO_BRIEF.background}</p>
      <dl className="grid gap-3 sm:grid-cols-2">
        {[
          ['의뢰 목적', DEMO_BRIEF.objective],
          ['핵심 주제', DEMO_BRIEF.topic],
          ['타겟 소비자', DEMO_BRIEF.target],
        ].map(([k, v]) => (
          <div key={k} className="rounded-xl border border-border bg-bg p-3">
            <dt className="mb-1 text-2xs font-semibold uppercase tracking-wider text-text-muted">{k}</dt>
            <dd className="text-sm text-text-primary">{v}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}

// ── 2단계: 설문 설계 (범용 공통 + 도메인 자동 생성 시뮬레이션) ────────────────
const SURVEY_PAGES = ['기본 설문', '주제 맞춤 설문', '심층 인터뷰'] as const;

export function DemoSurveyStep() {
  const universal = DEMO_SURVEYS[0];
  const domain = DEMO_SURVEYS[1];
  const [page, setPage] = useState(0); // 0 기본 / 1 맞춤 설문 / 2 인터뷰
  const [input, setInput] = useState(
    `${DEMO_BRIEF.company} · ${DEMO_BRIEF.objective}`,
  );
  const [gen, setGen] = useState<'idle' | 'generating' | 'done'>('idle');

  function generate() {
    if (gen === 'generating') return;
    setGen('generating');
    // 시뮬레이션 리빌 — 실제 생성 대신 사전 준비된 도메인 설문/인터뷰 공개
    setTimeout(() => setGen('done'), 1800);
  }

  return (
    <div className="space-y-4">
      {/* 단계 인디케이터 — 스크롤 대신 페이지 전환 */}
      <div className="flex flex-wrap items-center gap-2">
        {SURVEY_PAGES.map((label, i) => (
          <button
            key={label}
            onClick={() => setPage(i)}
            className={`flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
              page === i
                ? 'border-ditto-indigo bg-ditto-indigo text-white'
                : 'border-border text-text-secondary hover:border-ditto-indigo'
            }`}
          >
            <span className={`flex h-4 w-4 items-center justify-center rounded-full text-2xs ${
              page === i ? 'bg-white/25' : 'bg-bg'
            }`}>{i + 1}</span>
            {label}
          </button>
        ))}
      </div>

      {/* 1단계: 기본 설문 */}
      {page === 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Badge variant="indigo">모든 조사 공통</Badge>
            <span className="text-xs text-text-muted">어떤 조사든 동일하게 사용하는 소비 성향·가치관 기본 문항</span>
          </div>
          <SurveyCard survey={universal} />
        </div>
      )}

      {/* 2단계: 주제 맞춤 설문 (입력 → 생성 시뮬레이션 → 공개) */}
      {page === 1 && (
        <div className="space-y-4">
          <Card>
            <h3 className="mb-1 font-semibold text-text-primary">주제 맞춤 설문 자동 생성</h3>
            <p className="mb-3 text-xs text-text-muted">
              조사 대상(브랜드·목표)을 입력하면 주제에 맞는 설문이 자동으로 생성됩니다.
            </p>
            <div className="flex flex-col gap-2 sm:flex-row">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={gen === 'generating'}
                className="flex-1 rounded-xl border border-border bg-surface px-3 py-2 text-sm text-text-primary focus:border-ditto-indigo focus:outline-none"
              />
              <button
                onClick={generate}
                disabled={gen === 'generating' || !input.trim()}
                className="rounded-lg bg-ditto-indigo px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-ditto-indigo-hover disabled:opacity-50"
              >
                {gen === 'done' ? '다시 생성' : '자동 생성'}
              </button>
            </div>
            {gen === 'generating' && (
              <div className="mt-4 flex items-center gap-2 text-sm text-text-secondary">
                <Spinner size="sm" />
                <span>{DEMO_BRIEF.company} 주제에 맞춰 설문을 생성하는 중…</span>
              </div>
            )}
          </Card>
          {gen === 'done' && <SurveyCard survey={domain} generated />}
        </div>
      )}

      {/* 3단계: 심층 인터뷰 가이드 */}
      {page === 2 && (
        <Card>
          <div className="mb-2 flex items-center justify-between">
            <h3 className="font-semibold text-text-primary">{DEMO_INTERVIEW.title}</h3>
            <Badge variant="success" size="sm">✨ 자동 생성</Badge>
          </div>
          <p className="mb-3 text-xs text-text-muted">{DEMO_INTERVIEW.desc}</p>
          <div className="grid gap-3 sm:grid-cols-2">
            {DEMO_INTERVIEW.parts.map((p) => (
              <div key={p.part} className="rounded-lg border border-border bg-bg p-3">
                <p className="mb-1.5 text-xs font-semibold text-ditto-indigo">파트 {p.part}. {p.title}</p>
                <ul className="space-y-1 text-sm text-text-secondary">
                  {p.questions.map((q, i) => (
                    <li key={i} className="flex gap-1.5">
                      <span className="text-text-muted">·</span>
                      <span>{q}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* 페이지 내비게이션 */}
      <div className="flex items-center justify-between border-t border-border pt-3">
        <button
          onClick={() => setPage((p) => Math.max(0, p - 1))}
          disabled={page === 0}
          className="rounded-lg border border-border px-4 py-1.5 text-sm font-medium text-text-secondary hover:border-ditto-indigo disabled:opacity-40"
        >
          ← 이전
        </button>
        <span className="text-xs text-text-muted">{page + 1} / {SURVEY_PAGES.length}</span>
        <button
          onClick={() => setPage((p) => Math.min(SURVEY_PAGES.length - 1, p + 1))}
          disabled={page === SURVEY_PAGES.length - 1}
          className="rounded-lg bg-ditto-indigo px-4 py-1.5 text-sm font-semibold text-white hover:bg-ditto-indigo-hover disabled:opacity-40"
        >
          다음 →
        </button>
      </div>
    </div>
  );
}

// ── 3단계: 패널 데이터 수집 ─────────────────────────────────────────────────
export function DemoCollectStep() {
  const items = [
    { label: '범용 특성 설문 응답', value: DEMO_COLLECTION.consumptionResponses },
    { label: '포토이즘 도메인 설문 응답', value: DEMO_COLLECTION.domainResponses },
    { label: '심층 인터뷰', value: DEMO_COLLECTION.interviews },
  ];
  return (
    <Card>
      <h2 className="mb-1 text-xl font-bold text-text-primary">패널 데이터 수집 완료</h2>
      <p className="mb-5 text-sm text-text-secondary">{DEMO_COLLECTION.note}</p>
      <div className="grid gap-4 sm:grid-cols-3">
        {items.map((it) => (
          <div key={it.label} className="rounded-xl border border-border bg-bg p-4 text-center">
            <p className="text-score font-bold text-ditto-indigo">{it.value.toLocaleString()}</p>
            <p className="mt-1 text-xs text-text-muted">{it.label}</p>
          </div>
        ))}
      </div>
      <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-bg">
        <div className="h-full w-full bg-ditto-indigo" />
      </div>
      <p className="mt-2 text-right text-2xs text-text-muted">수집 100% 완료</p>
    </Card>
  );
}

// ── 6단계: 인사이트 보고서 (구조화) ─────────────────────────────────────────
export function DemoReportStep({ report }: { report: FGIReport | null }) {
  if (!report) {
    return (
      <Card>
        <EmptyState
          icon="📄"
          title="아직 보고서가 없어요"
          description="5단계 FGI를 끝까지 진행하면 인사이트 보고서가 생성됩니다."
        />
      </Card>
    );
  }
  return <FGIReportView report={report} />;
}

// ── 7단계: 보고서 제공 ──────────────────────────────────────────────────────
export function DemoDeliverStep({ report }: { report: FGIReport | null }) {
  function download() {
    if (!report) return;
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = '포토이즘_인사이트_보고서.json';
    a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <Card>
      <div className="py-6 text-center">
        <div className="mb-3 text-5xl">📬</div>
        <h2 className="mb-2 text-xl font-bold text-text-primary">보고서를 기업에 제공합니다</h2>
        <p className="mx-auto mb-6 max-w-md text-sm text-text-secondary">
          단발성 설문을 넘어, 응답 데이터를 에이전트로 보존하고 1:1 대화·FGI로 심층 인사이트를 도출했습니다.
          이 보고서를 {DEMO_BRIEF.company}에 전달하면 데모가 완료됩니다.
        </p>
        <button
          onClick={download}
          disabled={!report}
          className="rounded-lg bg-ditto-indigo px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-ditto-indigo-hover disabled:cursor-not-allowed disabled:opacity-50"
        >
          보고서 다운로드 (.json)
        </button>
      </div>
    </Card>
  );
}
