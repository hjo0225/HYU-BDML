'use client';

// FGI 구조화 인사이트 보고서 렌더 (plan 0008 v2 · §14 · HTML Tab 4 스타일) — 데모·실앱 공용.
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import type { FGIReport, VerifyDialogue } from '@/lib/types';

// 액션 아이템 우선순위 — title/description 키워드 기반.
type ActionTone = 'success' | 'warning' | 'error';
function actionTone(title: string, desc: string): ActionTone {
  const t = `${title} ${desc}`.toLowerCase();
  if (/(limitation|한계|타깃\s*외|불가|어려움|위험|주의)/i.test(t)) return 'error';
  if (/(보조|선행|전제|분리|차후|점검|개선 필요)/i.test(t)) return 'warning';
  return 'success';
}
const ACTION_BORDER: Record<ActionTone, string> = {
  success: 'border-l-success',
  warning: 'border-l-warning',
  error: 'border-l-error',
};
const ACTION_LABEL_COLOR: Record<ActionTone, string> = {
  success: 'text-success',
  warning: 'text-warning',
  error: 'text-error',
};

// 에이전트 입장(stance) 색 분류 — pro/con/neutral 키워드 기반.
type StanceTone = 'pro' | 'con' | 'neutral';
function stanceTone(stance: string): StanceTone {
  const s = stance.toLowerCase();
  if (/(선호|찬성|긍정|추종|적극|만족|충성)/i.test(stance)) return 'pro';
  if (/(반대|이탈|저관여|부정|불만|기피)/i.test(stance)) return 'con';
  return 'neutral';
}
const STANCE_CLASS: Record<StanceTone, string> = {
  pro: 'bg-success/10 text-success',
  con: 'bg-error/10 text-error',
  neutral: 'bg-bg text-text-muted',
};

// plan 0029 — 인사이트별 1:1 검증 채팅 thread.
// 분석가가 인사이트로부터 도출된 구체 가설을 던지고, 화자가 본인 페르소나로 reaction.
function VerifyThread({ v }: { v: VerifyDialogue }) {
  return (
    <div className="mt-3 rounded-lg border border-success/30 bg-success/5 p-4">
      <div className="mb-2.5 flex items-center gap-2">
        <span className="text-2xs font-bold uppercase tracking-wider text-success">
          ◉ 1:1 후속 검증
        </span>
        <span className="text-2xs text-text-muted">→ {v.with} 와(과) 직접 재확인</span>
      </div>
      <div className="flex flex-col gap-2">
        {v.turns.map((t, i) => (
          <div
            key={i}
            className={`max-w-[88%] rounded-lg px-3 py-2 text-xs leading-relaxed ${
              t.role === 'analyst'
                ? 'self-start border border-border bg-surface text-text-primary'
                : 'self-end bg-ditto-indigo text-white shadow-card'
            }`}
          >
            <span
              className={`mb-1 block text-[9px] font-bold uppercase tracking-wider ${
                t.role === 'analyst' ? 'text-text-muted' : 'text-white/70'
              }`}
            >
              {t.role === 'analyst' ? '분석가' : v.with}
            </span>
            {t.text}
          </div>
        ))}
      </div>
      {v.conclusion && (
        <p className="mt-3 rounded-r-md border-l-[3px] border-success bg-surface px-3 py-2 text-xs font-semibold text-text-primary">
          <span className="mr-1.5 font-bold text-success">✓</span>
          {v.conclusion}
        </p>
      )}
    </div>
  );
}

// 영상 촬영용 임시: 회의 종료 보고서를 docs/slides/insight-report-v10.html 그대로 출력.
// public/reports/insight-report-v10.html 을 iframe 으로 띄워 스타일·스크립트까지 동일하게 렌더.
// (실 데이터 기반 렌더는 아래 _FGIReportViewDynamic 에 보존 — 복원 시 export 만 교체)
export function FGIReportView({ onDashboard }: { report: FGIReport; onDashboard?: () => void }) {
  return (
    <div className="space-y-3">
      {onDashboard && (
        <div className="flex justify-end">
          <button
            onClick={onDashboard}
            className="rounded-lg bg-ditto-indigo px-3 py-1.5 text-xs font-medium text-white hover:bg-ditto-indigo-hover"
          >
            대시보드에서 보기
          </button>
        </div>
      )}
      <iframe
        src="/reports/insight-report-v10.html"
        title="FGI 인사이트 보고서 v10"
        className="w-full rounded-xl border border-border bg-white shadow-card"
        style={{ height: '85vh', minHeight: 720 }}
      />
    </div>
  );
}

// 실 데이터 기반 동적 렌더 (복원용). 현재 화면엔 미연결.
export function FGIReportViewDynamic({ report, onDashboard }: { report: FGIReport; onDashboard?: () => void }) {
  const { meta } = report;
  // 인사이트 title 로 verify 빠른 lookup.
  const verifyByTitle: Record<string, VerifyDialogue> = Object.fromEntries(
    (report.verifications ?? []).map((v) => [v.insight_title, v]),
  );

  function exportPdf() {
    window.print();
  }

  return (
    <div className="space-y-5">
      {/* 헤더 — 가운데 정렬 + 메타 chip */}
      <Card>
        <div className="text-center">
          <h2 className="text-2xl font-bold text-text-primary">FGI 인사이트 보고서</h2>
          <p className="mt-1 text-sm text-text-secondary">{report.topic}</p>
          <div className="mt-4 flex flex-wrap items-center justify-center gap-x-6 gap-y-1 text-2xs text-text-muted">
            <span>📅 {meta.date}</span>
            <span>👥 참여 에이전트 {meta.n_agents}명</span>
            <span>⏱ 총 {meta.n_rounds}라운드{meta.duration_min != null && ` · 소요 ${meta.duration_min}분`}</span>
          </div>
          <div className="mt-4 flex justify-center gap-2">
            <button onClick={exportPdf} className="rounded-lg border border-border bg-surface px-3 py-1.5 text-xs font-medium text-text-secondary hover:border-ditto-indigo hover:text-ditto-indigo">
              PDF 내보내기
            </button>
            {onDashboard && (
              <button onClick={onDashboard} className="rounded-lg bg-ditto-indigo px-3 py-1.5 text-xs font-medium text-white hover:bg-ditto-indigo-hover">
                대시보드에서 보기
              </button>
            )}
          </div>
        </div>
      </Card>

      {/* 핵심 인사이트 — 좌측 보더 강조 */}
      <Card>
        <h3 className="mb-3 inline-block border-b-[2px] border-ditto-indigo pb-1.5 text-lg font-bold text-text-primary">
          핵심 인사이트
        </h3>
        <ol className="space-y-2.5">
          {report.key_insights.map((ins, i) => {
            const v = verifyByTitle[ins.title];
            return (
              <li key={i} className="flex items-start gap-3.5 rounded-lg border-l-[4px] border-ditto-indigo bg-bg p-4">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-ditto-indigo text-xs font-bold text-white">
                  {i + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="font-bold text-text-primary">{ins.title}</p>
                  <p className="mt-1 text-sm leading-relaxed text-text-secondary">{ins.description}</p>
                  {ins.sources?.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {ins.sources.map((s) => <Badge key={s} variant="neutral" size="sm">{s}</Badge>)}
                    </div>
                  )}
                  {v && <VerifyThread v={v} />}
                </div>
              </li>
            );
          })}
        </ol>
      </Card>

      {/* 에이전트별 관점 — stance 색 구분 */}
      <Card>
        <h3 className="mb-3 inline-block border-b-[2px] border-ditto-indigo pb-1.5 text-lg font-bold text-text-primary">
          에이전트별 관점 요약
        </h3>
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-bg text-left text-2xs font-bold uppercase tracking-wider text-text-muted">
                <th className="px-3.5 py-2.5">에이전트</th>
                <th className="px-3.5 py-2.5">입장</th>
                <th className="px-3.5 py-2.5">핵심 발언</th>
              </tr>
            </thead>
            <tbody>
              {report.agent_perspectives.map((p, i) => {
                const tone = stanceTone(p.stance);
                return (
                  <tr key={i} className="border-b border-border/60 align-top last:border-b-0">
                    <td className="whitespace-nowrap px-3.5 py-2.5 font-bold text-text-primary">{p.name}</td>
                    <td className="whitespace-nowrap px-3.5 py-2.5">
                      <span className={`rounded-sm px-1.5 py-0.5 text-2xs font-medium ${STANCE_CLASS[tone]}`}>
                        {p.stance}
                      </span>
                    </td>
                    <td className="px-3.5 py-2.5 text-text-secondary">&ldquo;{p.key_quote}&rdquo;</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {/* 라운드별 토론 분석 — bg 강조 박스 */}
      <Card>
        <h3 className="mb-3 inline-block border-b-[2px] border-ditto-indigo pb-1.5 text-lg font-bold text-text-primary">
          라운드별 토론 분석
        </h3>
        <div className="space-y-2.5">
          {report.round_analysis.map((r) => (
            <div key={r.round} className="rounded-lg bg-bg p-5">
              <h4 className="mb-2 text-base font-bold text-text-primary">
                라운드 {r.round}: {r.title}
              </h4>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-text-muted">{r.summary}</p>
            </div>
          ))}
        </div>
      </Card>

      {/* 추천 액션 아이템 — 좌측 색 보더 (success/warning/error 우선순위) */}
      <Card>
        <h3 className="mb-3 inline-block border-b-[2px] border-ditto-indigo pb-1.5 text-lg font-bold text-text-primary">
          추천 액션 아이템
        </h3>
        <div className="space-y-2.5">
          {report.action_items.map((a, i) => {
            const tone = actionTone(a.title, a.description);
            return (
              <div
                key={i}
                className={`rounded-r-lg border-l-[4px] bg-bg p-4 ${ACTION_BORDER[tone]}`}
              >
                <p className={`text-2xs font-bold ${ACTION_LABEL_COLOR[tone]}`}>
                  {tone === 'error' ? '⚠ LIMITATION' : `ACTION ${i + 1}`}
                </p>
                <p className="mt-1 font-bold text-text-primary">{a.title}</p>
                <p className="mt-1 text-xs leading-relaxed text-text-secondary">{a.description}</p>
                {a.expected_effect && (
                  <p className="mt-2 text-2xs text-success">예상 효과: {a.expected_effect}</p>
                )}
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
