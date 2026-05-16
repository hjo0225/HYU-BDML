'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';
import { AuthGuard } from '@/components/auth/AuthGuard';
import { AppShell } from '@/components/layout/AppShell';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { V1Gauge } from '@/components/dashboard/V1Gauge';
import { useAuth } from '@/contexts/AuthContext';
import { agents as agentsApi, evaluations as evalApi } from '@/lib/api';
import type { AgentDetail, EvaluateEvent, EvaluationSnapshot } from '@/lib/types';

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
            // 본 agent 의 v1 점수가 도착하면 보조 표시
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
        </div>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <Card padding="md" className="md:col-span-1">
          <CardHeader title="최신 평가" subtitle={latest ? `v${latest.version} · ${new Date(latest.evaluated_at).toLocaleString('ko-KR')}` : '아직 없음'} />
          <V1Gauge sync={latest?.identity_stats?.sync ?? null} nEval={latest?.identity_stats?.v1_n_eval ?? null} />
          {latest?.identity_stats?.distinct != null && (
            <p className="text-xs text-text-muted mt-3 text-center">
              V3 distinct = <span className="text-text-primary font-medium">{latest.identity_stats.distinct.toFixed(2)}</span>
              <span className="text-text-muted"> · n={latest.identity_stats.v3_n_agents ?? '?'} 명</span>
            </p>
          )}
        </Card>

        <Card padding="md" className="md:col-span-2">
          <CardHeader
            title="평가 실행"
            subtitle="V1·V3 — 프로젝트의 모든 에이전트가 함께 평가됩니다 (V3 가 프로젝트 지표)"
          />
          <Button onClick={onRun} loading={running}>
            {running ? '평가 중…' : 'V1 · V3 실행'}
          </Button>
          {progress && (
            <div className="mt-4">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-text-muted">
                  {progress.current} / {progress.total}
                  {progress.v1 != null && <span className="ml-2">· 본인 V1 sync = <span className="text-text-primary font-medium">{progress.v1.toFixed(3)}</span></span>}
                </span>
                <span className="text-xs text-text-muted">
                  {Math.round((progress.current / Math.max(1, progress.total)) * 100)}%
                </span>
              </div>
              <div className="h-1.5 w-full bg-ditto-indigo-light rounded-full overflow-hidden">
                <div className="h-full bg-ditto-indigo transition-all"
                     style={{ width: `${(progress.current / Math.max(1, progress.total)) * 100}%` }} />
              </div>
            </div>
          )}
          {error && <p className="text-xs text-error mt-2">{error}</p>}
        </Card>
      </div>

      {snapshots.length > 0 && (
        <Card padding="md" className="mb-6">
          <CardHeader title="평가 시계열" subtitle={`${snapshots.length}건 (최신순)`} />
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-text-muted border-b border-border">
                  <th className="py-2 pr-3 font-medium">v</th>
                  <th className="py-2 pr-3 font-medium">V1 sync</th>
                  <th className="py-2 pr-3 font-medium">V3 distinct</th>
                  <th className="py-2 pr-3 font-medium">verdict</th>
                  <th className="py-2 pr-3 font-medium">실행 시각</th>
                </tr>
              </thead>
              <tbody>
                {snapshots.map(s => (
                  <tr key={s.id} className="border-b border-border/50 hover:bg-bg">
                    <td className="py-2 pr-3 font-mono text-xs">v{s.version}</td>
                    <td className="py-2 pr-3 font-mono">
                      {s.identity_stats?.sync != null ? s.identity_stats.sync.toFixed(3) : '—'}
                    </td>
                    <td className="py-2 pr-3 font-mono">
                      {s.identity_stats?.distinct != null ? s.identity_stats.distinct.toFixed(2) : '—'}
                    </td>
                    <td className="py-2 pr-3 text-xs">{s.verdict || '—'}</td>
                    <td className="py-2 pr-3 text-xs text-text-muted">
                      {new Date(s.evaluated_at).toLocaleString('ko-KR')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {agent.persona_full_prompt && (
        <Card padding="md">
          <CardHeader title="페르소나 시스템 프롬프트" subtitle="LLM 호출 시 system 메시지로 주입됩니다" />
          <pre className="text-xs text-text-secondary bg-bg p-3 rounded-lg whitespace-pre-wrap break-words max-h-96 overflow-y-auto">
            {agent.persona_full_prompt}
          </pre>
        </Card>
      )}
    </div>
  );
}
