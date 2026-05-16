'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { AuthGuard } from '@/components/auth/AuthGuard';
import { AppShell } from '@/components/layout/AppShell';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { useAuth } from '@/contexts/AuthContext';
import { useProjectContext } from '@/contexts/ProjectContext';
import { agents as agentsApi } from '@/lib/api';
import type { Agent } from '@/lib/types';
import type { SeedTwinEvent } from '@/lib/api';

const SOURCE_OPTIONS = [
  { value: '', label: '전체 소스' },
  { value: 'twin', label: 'Twin-2K-500' },
  { value: 'survey', label: 'Survey 기반' },
];

const CLUSTER_OPTIONS = [
  { value: '', label: '전체 클러스터' },
  { value: '0', label: '클러스터 0' },
  { value: '1', label: '클러스터 1' },
  { value: '2', label: '클러스터 2' },
  { value: '3', label: '클러스터 3' },
  { value: '4', label: '클러스터 4' },
];

// 6-Lens 범위 필터 — Slice 1.3 에서는 2축(L1·L2)만 노출. 추가 축은 후속.
interface RangeFilter {
  key: string;
  label: string;
  min: number;
  max: number;
  step: number;
}

const RANGE_FILTERS: RangeFilter[] = [
  { key: 'l1.risk_aversion', label: 'L1 위험 회피', min: 0, max: 1, step: 0.05 },
  { key: 'l2.maximization', label: 'L2 극대화 성향', min: 1, max: 5, step: 0.1 },
];

function buildParamsQS(ranges: Record<string, [number, number] | undefined>): string | undefined {
  const tokens: string[] = [];
  for (const f of RANGE_FILTERS) {
    const r = ranges[f.key];
    if (!r) continue;
    const [lo, hi] = r;
    // 기본 범위와 동일하면 필터 생략 (서버 부하 절약 + UX 명확)
    if (lo <= f.min && hi >= f.max) continue;
    tokens.push(`${f.key}:${lo}-${hi}`);
  }
  return tokens.length ? tokens.join(',') : undefined;
}

export default function ProjectAgentsPage() {
  return (
    <AuthGuard>
      <AppShell>
        <AgentsCatalogView />
      </AppShell>
    </AuthGuard>
  );
}

function AgentsCatalogView() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { token } = useAuth();
  const { projectId, selectedAgentIds, toggleAgent, clearSelection, setProjectId } = useProjectContext();
  const routeProjectId = params?.id;

  const [list, setList] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [sourceType, setSourceType] = useState('');
  const [cluster, setCluster] = useState('');
  const [ranges, setRanges] = useState<Record<string, [number, number]>>(() =>
    Object.fromEntries(RANGE_FILTERS.map(f => [f.key, [f.min, f.max] as [number, number]])),
  );

  // seed 진행 상태
  const [seeding, setSeeding] = useState(false);
  const [seedProgress, setSeedProgress] = useState<{ current: number; total: number; label?: string } | null>(null);
  const [seedError, setSeedError] = useState<string | null>(null);

  // 컨텍스트 동기화 — URL projectId 가 ctx 와 다르면 ctx 업데이트(선택은 자동 초기화됨)
  useEffect(() => {
    if (routeProjectId && routeProjectId !== projectId) {
      setProjectId(routeProjectId);
    }
  }, [routeProjectId, projectId, setProjectId]);

  const queryOpts = useMemo(() => ({
    source_type: (sourceType || undefined) as 'twin' | 'survey' | undefined,
    cluster: cluster !== '' ? Number(cluster) : undefined,
    params: buildParamsQS(ranges),
    limit: 200,
  }), [sourceType, cluster, ranges]);

  const reload = useCallback(async () => {
    if (!token || !routeProjectId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await agentsApi.list(token, routeProjectId, queryOpts);
      setList(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : '불러오기 실패');
    } finally {
      setLoading(false);
    }
  }, [token, routeProjectId, queryOpts]);

  useEffect(() => { reload(); }, [reload]);

  const startSeed = useCallback(async () => {
    if (!token || !routeProjectId || seeding) return;
    setSeeding(true);
    setSeedError(null);
    setSeedProgress(null);
    try {
      for await (const ev of agentsApi.seedTwin(token, routeProjectId, { limit: 30 }) as AsyncGenerator<SeedTwinEvent>) {
        if (ev.type === 'start') {
          setSeedProgress({ current: 0, total: ev.total });
        } else if (ev.type === 'progress') {
          setSeedProgress({ current: ev.current, total: ev.total, label: ev.display_name });
        } else if (ev.type === 'error') {
          setSeedError(ev.reason);
        }
      }
      await reload();
    } catch (e) {
      setSeedError(e instanceof Error ? e.message : '적재 실패');
    } finally {
      setSeeding(false);
    }
  }, [token, routeProjectId, seeding, reload]);

  const visibleIds = useMemo(() => new Set(list.map(a => a.id)), [list]);
  // 필터 적용 후에도 컨텍스트에 남아있는(현재 보이지 않는) 선택은 유지 — UX 의도
  const selectedCount = selectedAgentIds.length;
  const visibleSelectedCount = useMemo(
    () => selectedAgentIds.filter(id => visibleIds.has(id)).length,
    [selectedAgentIds, visibleIds],
  );

  const onNext = useCallback(() => {
    // 다음 단계는 Slice 2(평가) — 아직 미구현. 임시로 개요로 복귀하면서 ctx 만 유지.
    router.push(`/projects/${routeProjectId}`);
  }, [router, routeProjectId]);

  return (
    <div className="p-8 max-w-6xl mx-auto pb-32">
      <div className="mb-6">
        <Link href={`/projects/${routeProjectId}`} className="text-xs text-text-muted hover:text-ditto-indigo">← 프로젝트 개요</Link>
      </div>

      <div className="mb-6">
        <h1 className="text-2xl font-bold text-text-primary">에이전트 카탈로그</h1>
        <p className="text-sm text-text-muted mt-1">
          6-Lens 범위로 필터링하고 다음 단계에 사용할 에이전트를 선택합니다.
        </p>
      </div>

      <Card padding="md" className="mb-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-4">
          <Select
            label="소스"
            name="source_type"
            options={SOURCE_OPTIONS}
            value={sourceType}
            onChange={e => setSourceType(e.target.value)}
          />
          <Select
            label="클러스터"
            name="cluster"
            options={CLUSTER_OPTIONS}
            value={cluster}
            onChange={e => setCluster(e.target.value)}
          />
          <div className="md:col-span-2 grid grid-cols-2 gap-3">
            {RANGE_FILTERS.map(f => {
              const [lo, hi] = ranges[f.key];
              return (
                <div key={f.key}>
                  <label className="block text-sm font-medium text-text-secondary mb-1">{f.label}</label>
                  <div className="flex items-center gap-2">
                    <Input
                      name={`${f.key}_lo`}
                      type="number"
                      step={f.step}
                      min={f.min}
                      max={f.max}
                      value={lo}
                      onChange={e => setRanges(r => ({ ...r, [f.key]: [Number(e.target.value), r[f.key][1]] }))}
                    />
                    <span className="text-xs text-text-muted">~</span>
                    <Input
                      name={`${f.key}_hi`}
                      type="number"
                      step={f.step}
                      min={f.min}
                      max={f.max}
                      value={hi}
                      onChange={e => setRanges(r => ({ ...r, [f.key]: [r[f.key][0], Number(e.target.value)] }))}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
        <div className="flex items-center gap-3 text-xs text-text-muted">
          <span>{loading ? '불러오는 중…' : `${list.length}명 일치`}</span>
          {error && <span className="text-error">· {error}</span>}
        </div>
      </Card>

      {seeding && seedProgress && (
        <Card padding="md" className="mb-4 border-ditto-indigo/30 bg-ditto-indigo-light/30">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-ditto-indigo">
              적재 중… {seedProgress.current} / {seedProgress.total}
              {seedProgress.label && <span className="text-text-muted font-normal"> · {seedProgress.label}</span>}
            </span>
            <span className="text-xs text-text-muted">
              {Math.round((seedProgress.current / Math.max(1, seedProgress.total)) * 100)}%
            </span>
          </div>
          <div className="h-1.5 w-full bg-ditto-indigo-light rounded-full overflow-hidden">
            <div
              className="h-full bg-ditto-indigo transition-all"
              style={{ width: `${(seedProgress.current / Math.max(1, seedProgress.total)) * 100}%` }}
            />
          </div>
        </Card>
      )}

      {!loading && !seeding && list.length === 0 && (
        <Card padding="lg" className="text-center">
          <p className="text-sm text-text-muted mb-4">
            아직 적재된 에이전트가 없습니다. 실데이터 도착 전까지는 mock 30명(6 archetype × 5명)
            으로 흐름을 검증할 수 있습니다.
          </p>
          {seedError && <p className="text-xs text-error mb-3">{seedError}</p>}
          <Button onClick={startSeed} loading={seeding} disabled={!token}>
            mock 30명 적재 (Twin-2K-500 구조)
          </Button>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {list.map(a => {
          const selected = selectedAgentIds.includes(a.id);
          return (
            <Card
              key={a.id}
              padding="md"
              className={`h-full ${selected ? 'border-ditto-indigo bg-ditto-indigo-light/40 ring-2 ring-ditto-indigo' : 'hover:border-ditto-indigo/40'}`}
            >
              <div className="flex items-start gap-3">
                <div className="text-2xl leading-none shrink-0">{a.emoji || '👤'}</div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <Link
                      href={`/projects/${routeProjectId}/agents/${a.id}`}
                      className="text-sm font-bold text-text-primary truncate hover:text-ditto-indigo focus:outline-none focus:underline"
                    >
                      {a.display_name || `에이전트 ${a.id.slice(0, 6)}`}
                    </Link>
                    {a.cluster !== null && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-ditto-indigo-light text-ditto-indigo font-mono shrink-0">
                        C{a.cluster}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-text-muted mt-1 line-clamp-2">
                    {a.summary || a.intro_ko || '요약 준비 중'}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => toggleAgent(a.id)}
                  aria-label={selected ? '선택 해제' : '선택'}
                  className={`w-6 h-6 rounded border-2 shrink-0 flex items-center justify-center focus:outline-none focus:ring-2 focus:ring-ditto-indigo ${
                    selected ? 'border-ditto-indigo bg-ditto-indigo text-white' : 'border-border hover:border-ditto-indigo'
                  }`}
                >
                  {selected && <span className="text-xs leading-none">✓</span>}
                </button>
              </div>
            </Card>
          );
        })}
      </div>

      {/* 하단 sticky 액션바 */}
      <div className="fixed bottom-0 left-[var(--sidebar-width)] right-0 bg-surface border-t border-border px-8 py-3 flex items-center justify-between shadow-elevated">
        <div className="text-sm">
          <span className="text-text-muted">선택됨</span>{' '}
          <span className="font-bold text-text-primary">{selectedCount}</span>
          <span className="text-text-muted">명</span>
          {selectedCount !== visibleSelectedCount && (
            <span className="text-xs text-text-muted ml-2">
              (현재 필터에 보이는 건 {visibleSelectedCount}명)
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" onClick={clearSelection} disabled={selectedCount === 0}>
            선택 해제
          </Button>
          <Button variant="primary" onClick={onNext} disabled={selectedCount === 0}>
            다음 단계로 →
          </Button>
        </div>
      </div>
    </div>
  );
}
