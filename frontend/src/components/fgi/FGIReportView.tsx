'use client';

// FGI 구조화 인사이트 보고서 렌더 (plan 0008 v2 · §14) — 데모·실앱 공용.
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import type { FGIReport } from '@/lib/types';

export function FGIReportView({ report, onDashboard }: { report: FGIReport; onDashboard?: () => void }) {
  const { meta } = report;

  function exportPdf() {
    window.print();
  }

  return (
    <div className="space-y-5">
      {/* 헤더 */}
      <Card>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-xl font-bold text-text-primary">FGI 인사이트 보고서</h2>
            <p className="mt-0.5 text-sm text-text-secondary">{report.topic}</p>
            <p className="mt-2 text-xs text-text-muted">
              {meta.date} · 참여 에이전트 {meta.n_agents}명 · 총 {meta.n_rounds}라운드
              {meta.duration_min != null && ` · 소요 ${meta.duration_min}분`}
            </p>
          </div>
          <div className="flex shrink-0 gap-2">
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

      {/* 핵심 인사이트 */}
      <Card>
        <h3 className="mb-3 text-base font-bold text-ditto-indigo">핵심 인사이트</h3>
        <ol className="space-y-3">
          {report.key_insights.map((ins, i) => (
            <li key={i} className="flex gap-3">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-ditto-indigo text-xs font-bold text-white">{i + 1}</span>
              <div>
                <p className="font-semibold text-text-primary">{ins.title}</p>
                <p className="mt-0.5 text-sm text-text-secondary">{ins.description}</p>
                {ins.sources?.length > 0 && (
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {ins.sources.map((s) => <Badge key={s} variant="neutral" size="sm">{s}</Badge>)}
                  </div>
                )}
              </div>
            </li>
          ))}
        </ol>
      </Card>

      {/* 에이전트별 관점 */}
      <Card>
        <h3 className="mb-3 text-base font-bold text-ditto-indigo">에이전트별 관점 요약</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-2xs uppercase tracking-wider text-text-muted">
                <th className="py-2 pr-3">에이전트</th>
                <th className="py-2 pr-3">입장</th>
                <th className="py-2">핵심 발언</th>
              </tr>
            </thead>
            <tbody>
              {report.agent_perspectives.map((p, i) => (
                <tr key={i} className="border-b border-border/60 align-top">
                  <td className="py-2 pr-3 font-medium text-text-primary whitespace-nowrap">{p.name}</td>
                  <td className="py-2 pr-3"><Badge variant="violet" size="sm">{p.stance}</Badge></td>
                  <td className="py-2 text-text-secondary">&ldquo;{p.key_quote}&rdquo;</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* 라운드별 토론 분석 */}
      <Card>
        <h3 className="mb-3 text-base font-bold text-ditto-indigo">라운드별 토론 분석</h3>
        <div className="space-y-3">
          {report.round_analysis.map((r) => (
            <div key={r.round} className="rounded-lg border border-border bg-bg p-3">
              <p className="text-sm font-semibold text-text-primary">라운드 {r.round}: {r.title}</p>
              <p className="mt-1 whitespace-pre-wrap text-xs text-text-secondary">{r.summary}</p>
            </div>
          ))}
        </div>
      </Card>

      {/* 추천 액션 아이템 */}
      <Card>
        <h3 className="mb-3 text-base font-bold text-ditto-indigo">추천 액션 아이템</h3>
        <div className="grid gap-3 sm:grid-cols-2">
          {report.action_items.map((a, i) => (
            <div key={i} className="rounded-lg border border-border bg-bg p-3">
              <p className="text-xs font-bold text-ditto-violet">ACTION {i + 1}</p>
              <p className="mt-0.5 font-semibold text-text-primary">{a.title}</p>
              <p className="mt-1 text-xs text-text-secondary">{a.description}</p>
              {a.expected_effect && (
                <p className="mt-1.5 text-2xs text-success">예상 효과: {a.expected_effect}</p>
              )}
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
