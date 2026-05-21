'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';
import { AuthGuard } from '@/components/auth/AuthGuard';
import { AppShell } from '@/components/layout/AppShell';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { V1Gauge } from '@/components/dashboard/V1Gauge';
import { statusColorVar } from '@/components/dashboard/score';
import { useAuth } from '@/contexts/AuthContext';
import { agents as agentsApi, evaluations as evalApi } from '@/lib/api';
import type { AgentDetail, EvaluateEvent, EvaluationSnapshot } from '@/lib/types';

// V3 distinct 임계 → 색상 매핑. EVAL_SPEC.md §3 SSOT.
type V3Status = 'success' | 'warning' | 'error';
function v3Status(d: number): V3Status {
  if (d >= 3.0) return 'success';
  if (d >= 1.5) return 'warning';
  return 'error';
}


export default function AgentDetailPage() {
  return (
    <AuthGuard>
      <AppShell>
        <AgentDetailView />
      </AppShell>
    </AuthGuard>
  );
}

function AgentDetailView() {
  const params = useParams<{ id: string; agentId: string }>();
  const { token } = useAuth();
  const projectId = params?.id;
  const agentId = params?.agentId;

  const [agent, setAgent] = useState<AgentDetail | null>(null);
  const [snapshots, setSnapshots] = useState<EvaluationSnapshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState<{ current: number; total: number; v1?: number } | null>(null);

  const reload = useCallback(async () => {
    if (!token || !agentId) return;
    setLoading(true);
    setError(null);
    try {
      const [a, snaps] = await Promise.all([
        agentsApi.get(token, agentId),
        evalApi.list(token, agentId, 20),
      ]);
      setAgent(a);
      setSnapshots(snaps);
    } catch (e) {
      setError(e instanceof Error ? e.message : '불러오기 실패');
    } finally {
      setLoading(false);
    }
  }, [token, agentId]);

  useEffect(() => { reload(); }, [reload]);

  const onRun = useCallback(async () => {
    if (!token || !agentId || running) return;
    setRunning(true);
    setProgress(null);
    setError(null);
    try {
      for await (const ev of evalApi.trigger(token, agentId, { metrics: ['v1', 'v3'] }) as AsyncGenerator<EvaluateEvent>) {
        if (ev.type === 'start') {
          setProgress({ current: 0, total: ev.total });
        } else if (ev.type === 'agent_done') {
          setProgress(prev => ({
            current: ev.current,
            total: ev.total,
            v1: ev.agent_id === agentId ? ev.v1_sync : prev?.v1,
          }));
        } else if (ev.type === 'error') {
          setError(ev.reason);
        }
      }
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : '평가 실행 실패');
    } finally {
      setRunning(false);
    }
  }, [token, agentId, running, reload]);

  const latest = snapshots[0] ?? null;
  const sync = latest?.identity_stats?.sync ?? null;
  const distinct = latest?.identity_stats?.distinct ?? null;

  if (loading) {
    return <div className="p-8 max-w-5xl mx-auto"><p className="text-sm text-text-muted">불러오는 중…</p></div>;
  }

  if (!agent) {
    return (
      <div className="p-8 max-w-5xl mx-auto">
        <Card padding="lg">
          <p className="text-sm text-error mb-3">{error || '에이전트를 찾을 수 없습니다.'}</p>
          <Link href={`/projects/${projectId}/agents`} className="text-sm text-ditto-indigo hover:underline">← 카탈로그로</Link>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-4">
        <Link href={`/projects/${projectId}/agents`} className="text-xs text-text-muted hover:text-ditto-indigo">← 에이전트 카탈로그</Link>
      </div>

      {/* 헤더 + 평가 실행 — 좌(에이전트 정보) 우(액션) */}
      <Card padding="md" className="mb-6">
        <div className="flex items-start gap-4">
          <div className="text-4xl leading-none shrink-0">{agent.emoji || '👤'}</div>
          <div className="flex-1 min-w-0">
            <h1 className="text-xl font-bold text-text-primary">
              {agent.display_name || `에이전트 ${agent.id.slice(0, 6)}`}
            </h1>
            <p className="text-sm text-text-muted mt-1">{agent.intro_ko || agent.summary || '요약 준비 중'}</p>
            <div className="flex items-center gap-3 mt-2 text-xs text-text-muted">
              <span>소스: <span className="font-mono">{agent.source_type}</span></span>
              {agent.cluster !== null && <span>· cluster <span className="font-mono">C{agent.cluster}</span></span>}
              <span>· id <span className="font-mono">{agent.id.slice(0, 8)}</span></span>
            </div>
          </div>
          <div className="shrink-0 flex flex-col items-end gap-2 min-w-[220px]">
            <Button onClick={onRun} loading={running}>
              {running ? '평가 중…' : '품질 평가 실행'}
            </Button>
            <Link href={`/projects/${projectId}/agents/${agent.id}/chat`} className="w-full">
              <Button variant="secondary" className="w-full">1:1 대화하기</Button>
            </Link>
            <span className="text-[10px] text-text-muted text-right leading-snug">
              프로젝트의 모든 에이전트가<br />함께 평가됩니다 (1~2분 소요)
            </span>
            {latest && (
              <span className="text-[10px] text-text-muted">
                최근 v{latest.version} · {new Date(latest.evaluated_at).toLocaleString('ko-KR')}
              </span>
            )}
            {progress && (
              <div className="w-full">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] text-text-muted">
                    {progress.current} / {progress.total}
                    {progress.v1 != null && <span className="ml-1">· V1 {progress.v1.toFixed(2)}</span>}
                  </span>
                  <span className="text-[10px] text-text-muted">
                    {Math.round((progress.current / Math.max(1, progress.total)) * 100)}%
                  </span>
                </div>
                <div className="h-1 w-full bg-ditto-indigo-light rounded-full overflow-hidden">
                  <div className="h-full bg-ditto-indigo transition-all"
                       style={{ width: `${(progress.current / Math.max(1, progress.total)) * 100}%` }} />
                </div>
              </div>
            )}
            {error && <p className="text-[10px] text-error">{error}</p>}
          </div>
        </div>
      </Card>

      {/* V1 · V3 각각 한 카드씩 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

        {/* ── V1 ───────────────────────────────────────────────────────── */}
        <Card padding="md" className="flex flex-col">
          <CardHeader
            title="진짜 그 사람처럼 답하나?"
            subtitle="실제 응답자와 얼마나 닮았는지"
          />

          <div className="mt-2 flex justify-center items-center" style={{ height: 225 }}>
            <V1Gauge sync={sync} size={420} />
          </div>

          <div className="mt-2 text-sm text-text-secondary leading-relaxed" style={{ height: 92 }}>
            <p>
              에이전트한테 <strong>새로운 질문 몇 개</strong>를 던져봅니다 — 예를 들어
              &quot;최근에 한 큰 소비는?&quot;, &quot;본인 라이프스타일을 한 단어로?&quot; 같은 거요.
              그리고 그 답변을 <strong>실제 그 사람이 한 답변</strong>과 비교합니다.
            </p>
          </div>

          <div className="mt-2 grid grid-cols-3 gap-1.5 text-[10px]">
            <div className="bg-emerald-50 text-success rounded-md px-2 py-1.5 text-center">
              <div className="font-semibold text-xs">80% 이상</div>
              <div className="opacity-80 mt-0.5">거의 똑같이 답함</div>
            </div>
            <div className="bg-amber-50 text-warning rounded-md px-2 py-1.5 text-center">
              <div className="font-semibold text-xs">60~80%</div>
              <div className="opacity-80 mt-0.5">대체로 비슷</div>
            </div>
            <div className="bg-red-50 text-error rounded-md px-2 py-1.5 text-center">
              <div className="font-semibold text-xs">60% 미만</div>
              <div className="opacity-80 mt-0.5">전혀 다름</div>
            </div>
          </div>
        </Card>

        {/* ── V3 ───────────────────────────────────────────────────────── */}
        <Card padding="md" className="flex flex-col">
          <CardHeader
            title="다양한 사람들이 모였나?"
            subtitle="프로젝트 30명이 서로 얼마나 다른 사람인지"
          />

          {distinct == null ? (
            <div className="mt-2 flex flex-col items-center justify-center gap-2" style={{ height: 225 }}>
              <div className="rounded-2xl border-4 border-dashed border-border flex items-center justify-center"
                   style={{ width: 174, height: 138 }}>
                <span className="text-xs text-text-muted">평가 전</span>
              </div>
              <span className="text-xs text-text-muted">아직 측정 안 됨</span>
            </div>
          ) : (
            <div className="mt-2 flex flex-col items-center justify-center" style={{ height: 225 }}>
              <div
                className="text-7xl font-bold tabular-nums leading-none"
                style={{ color: statusColorVar[v3Status(distinct)] }}
              >
                {distinct.toFixed(2)}
              </div>
            </div>
          )}

          <div className="mt-2 text-sm text-text-secondary leading-relaxed" style={{ height: 92 }}>
            <p>
              프로젝트의 30명 에이전트가 <strong>서로 얼마나 다른 인격</strong>인지를 봅니다.
              모두에게 같은 질문을 던졌을 때 답변이 천차만별이면 다양한 사람들이 모인 거고,
              비슷비슷한 답만 나오면 다 똑같은 사람을 30번 복사한 거나 마찬가지죠.
            </p>
          </div>

          <div className="mt-2 grid grid-cols-3 gap-1.5 text-[10px]">
            <div className="bg-emerald-50 text-success rounded-md px-2 py-1.5 text-center">
              <div className="font-semibold text-xs">3.0 이상</div>
              <div className="opacity-80 mt-0.5">다양함</div>
            </div>
            <div className="bg-amber-50 text-warning rounded-md px-2 py-1.5 text-center">
              <div className="font-semibold text-xs">1.5~3.0</div>
              <div className="opacity-80 mt-0.5">보통</div>
            </div>
            <div className="bg-red-50 text-error rounded-md px-2 py-1.5 text-center">
              <div className="font-semibold text-xs">1.5 미만</div>
              <div className="opacity-80 mt-0.5">비슷비슷</div>
            </div>
          </div>
        </Card>

      </div>
    </div>
  );
}
