'use client';

// 품질 평가 탭 (plan 0013) — 모든 에이전트의 품질 통계 + 다양성 분포.
// 집계는 클라이언트에서 scatter(에이전트별 닮음·클러스터) + 에이전트 목록으로 수행(서버 집계 API 불필요).
import Link from 'next/link';
import { useCallback, useMemo, useState } from 'react';
import { Card, CardHeader } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { V3Scatter } from '@/components/dashboard/V3Scatter';
import { useAuth } from '@/contexts/AuthContext';
import { evaluations as evalApi } from '@/lib/api';
import type { Agent, EvaluateEvent, ScatterResponse } from '@/lib/types';

const pct = (v: number | null | undefined) => (v == null ? '—' : `${Math.round(v * 100)}%`);

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <p className="text-2xs font-medium text-text-muted">{label}</p>
      <p className="mt-1 text-2xl font-bold text-text-primary">{value}</p>
      {hint && <p className="mt-0.5 text-2xs text-text-muted">{hint}</p>}
    </div>
  );
}

export function QualityPanel({
  projectId,
  agents,
  scatter,
  onEvaluated,
}: {
  projectId: string;
  agents: Agent[];
  scatter: ScatterResponse | null;
  onEvaluated?: () => void;  // 평가 완료 후 상위에서 scatter·agents 재로드
}) {
  const { token } = useAuth();
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState<{ current: number; total: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  // 한 에이전트로 트리거해도 프로젝트 전체가 함께 평가된다.
  const runEval = useCallback(async () => {
    const agentId = agents[0]?.id;
    if (!token || !agentId || running) return;
    setRunning(true); setProgress(null); setError(null);
    try {
      for await (const ev of evalApi.trigger(token, agentId, { metrics: ['v1', 'v3'] }) as AsyncGenerator<EvaluateEvent>) {
        if (ev.type === 'start') setProgress({ current: 0, total: ev.total });
        else if (ev.type === 'agent_done') setProgress({ current: ev.current, total: ev.total });
        else if (ev.type === 'error') setError(ev.reason);
      }
      onEvaluated?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : '평가 실행 실패');
    } finally {
      setRunning(false);
    }
  }, [token, agents, running, onEvaluated]);

  const runControls = (
    <div className="flex items-center gap-3" data-tour="quality-run">
      <Button onClick={runEval} loading={running} disabled={agents.length === 0}>
        {running ? '평가 중…' : '품질 평가 실행'}
      </Button>
      {progress && (
        <span className="text-2xs text-text-muted tabular-nums">
          {progress.current}/{progress.total} · {Math.round((progress.current / Math.max(1, progress.total)) * 100)}%
        </span>
      )}
      {error && <span className="text-2xs text-error">{error}</span>}
    </div>
  );

  const points = scatter?.points ?? [];
  const syncByAgent = useMemo(
    () => new Map(points.map((p) => [p.agent_id, p.sync])),
    [points],
  );
  const clusterByAgent = useMemo(
    () => new Map(points.map((p) => [p.agent_id, p.cluster])),
    [points],
  );

  const syncs = points.map((p) => p.sync).filter((s): s is number => s != null);
  const avgSync = syncs.length ? syncs.reduce((a, b) => a + b, 0) / syncs.length : null;
  const evaluated = syncByAgent.size;
  const clusters = new Set(points.map((p) => p.cluster).filter((c) => c != null)).size;

  if (!scatter || scatter.n_points === 0) {
    return (
      <Card padding="lg" className="border-dashed">
        <p className="text-sm text-text-secondary mb-1">아직 평가 결과가 없습니다.</p>
        <p className="text-sm text-text-muted mb-4">
          아래 &quot;품질 평가 실행&quot;을 누르면 이 프로젝트의 AI 소비자 전체가 함께 평가되어
          닮음·다양성 통계와 분포도가 여기에 나타납니다.
          {agents.length === 0 && ' 먼저 ‘AI 소비자’에서 소비자를 추가·저장하세요.'}
        </p>
        {runControls}
        {agents.length === 0 && (
          <Link href={`/projects/${projectId}/agents`} className="mt-3 inline-block text-sm text-ditto-indigo hover:underline">
            AI 소비자로 이동 →
          </Link>
        )}
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-text-secondary">이 프로젝트 AI 소비자의 품질 통계입니다.</p>
        {runControls}
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="다양성 (V3 distinct)" value={scatter.distinct != null ? scatter.distinct.toFixed(2) : '—'}
              hint="30명이 서로 얼마나 다른 인격인지" />
        <Stat label="평균 닮음 (V1)" value={pct(avgSync)} hint="진짜 사람과의 평균 일치도" />
        <Stat label="평가 완료" value={`${evaluated} / ${agents.length}`} hint="평가된 에이전트 수" />
        <Stat label="군집 수" value={String(clusters || '—')} hint="성향 클러스터 개수" />
      </div>

      <Card padding="md">
        <CardHeader title="에이전트 다양성 분포" subtitle="가까울수록 비슷한 인격 · 멀수록 다양" />
        <V3Scatter points={scatter.points} distinct={scatter.distinct} height={360} />
      </Card>

      <Card padding="md">
        <CardHeader title="에이전트별 품질" subtitle={`총 ${agents.length}명 · 평가 완료 ${evaluated}명`} />
        <div className="mt-2 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-2xs text-text-muted">
                <th className="py-2 pr-3 font-medium">에이전트</th>
                <th className="py-2 pr-3 font-medium">닮음 (V1)</th>
                <th className="py-2 pr-3 font-medium">군집</th>
                <th className="py-2 font-medium">상태</th>
              </tr>
            </thead>
            <tbody>
              {agents.map((a) => {
                const sync = syncByAgent.get(a.id);
                const cluster = clusterByAgent.get(a.id);
                const done = syncByAgent.has(a.id);
                return (
                  <tr key={a.id} className="border-b border-border/60">
                    <td className="py-2 pr-3">
                      <span className="font-medium text-text-primary">{a.display_name || '(이름 없음)'}</span>
                      {(a.age_range || a.gender) && (
                        <span className="ml-1.5 text-2xs text-text-muted">
                          {[a.age_range, a.gender].filter(Boolean).join(' ')}
                        </span>
                      )}
                    </td>
                    <td className="py-2 pr-3 tabular-nums text-text-secondary">{pct(sync)}</td>
                    <td className="py-2 pr-3 text-text-secondary">{cluster != null ? `C${cluster}` : '—'}</td>
                    <td className="py-2">
                      <Badge variant={done ? 'success' : 'neutral'} size="sm">
                        {done ? '평가완료' : '미평가'}
                      </Badge>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
