'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { AuthGuard } from '@/components/auth/AuthGuard';
import { AppShell } from '@/components/layout/AppShell';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Badge } from '@/components/ui/Badge';
import { PageContainer } from '@/components/layout/PageContainer';
import { PageHeader } from '@/components/layout/PageHeader';
import { useAuth } from '@/contexts/AuthContext';
import { useProjectContext } from '@/contexts/ProjectContext';
import { agents as agentsApi } from '@/lib/api';
import { personaKeywords } from '@/lib/persona';
import type { Agent } from '@/lib/types';
import type { SeedTwinEvent } from '@/lib/api';

// 6-Lens 범위 필터 — 2축(위험회피·선택신중함)만 노출. 사용자 친화 라벨.
interface RangeFilter {
  key: string;
  label: string;
  min: number;
  max: number;
  step: number;
}

const RANGE_FILTERS: RangeFilter[] = [
  { key: 'l1.risk_aversion', label: '위험 회피 성향', min: 0, max: 1, step: 0.05 },
  { key: 'l2.maximization', label: '선택 신중함(극대화)', min: 1, max: 5, step: 0.1 },
];

// 인구통계 필터 옵션을 로드된 목록에서 동적으로 도출 (실데이터 표기 변동 흡수).
function distinctOptions(values: (string | null)[]): { value: string; label: string }[] {
  const seen = new Set<string>();
  const out: { value: string; label: string }[] = [];
  for (const v of values) {
    const s = (v ?? '').trim();
    if (!s || seen.has(s)) continue;
    seen.add(s);
    out.push({ value: s, label: s });
  }
  out.sort((a, b) => a.label.localeCompare(b.label, 'ko'));
  return out;
}

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
  const { token } = useAuth();
  const { projectId, selectedAgentIds, toggleAgent, clearSelection, setSelectedAgents, setProjectId } = useProjectContext();
  const routeProjectId = params?.id;

  const [list, setList] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [ageFilter, setAgeFilter] = useState('');
  const [genderFilter, setGenderFilter] = useState('');
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

  // 성향(persona_params) 범위는 서버 필터, 연령대·성별은 클라이언트 필터(로드 후 적용).
  const queryOpts = useMemo(() => ({
    params: buildParamsQS(ranges),
    limit: 200,
  }), [ranges]);

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

  // 인구통계 옵션은 로드된 목록에서 도출, 필터는 클라이언트 측 적용.
  const ageOptions = useMemo(() => distinctOptions(list.map(a => a.age_range)), [list]);
  const genderOptions = useMemo(() => distinctOptions(list.map(a => a.gender)), [list]);
  const filtered = useMemo(
    () => list.filter(a =>
      (!ageFilter || a.age_range === ageFilter) &&
      (!genderFilter || a.gender === genderFilter),
    ),
    [list, ageFilter, genderFilter],
  );

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

  const visibleIds = useMemo(() => new Set(filtered.map(a => a.id)), [filtered]);
  // 필터 적용 후에도 컨텍스트에 남아있는(현재 보이지 않는) 선택은 유지 — UX 의도
  const selectedCount = selectedAgentIds.length;
  const visibleSelectedCount = useMemo(
    () => selectedAgentIds.filter(id => visibleIds.has(id)).length,
    [selectedAgentIds, visibleIds],
  );

  // 선택은 ProjectContext(sessionStorage)에 자동 저장됨 — '저장'은 확정 피드백 + 다음 흐름 안내.
  const [saved, setSaved] = useState(false);
  useEffect(() => { setSaved(false); }, [selectedAgentIds]);
  const onSave = useCallback(() => {
    setSelectedAgents(selectedAgentIds);  // 현재 선택 확정 (멱등)
    setSaved(true);
  }, [setSelectedAgents, selectedAgentIds]);

  return (
    <PageContainer width="wide" className="pb-32">
      <PageHeader
        title="AI 소비자"
        subtitle="조건으로 필터링해 AI 소비자를 고르고 저장하세요. 저장한 소비자가 1:1 채팅·FGI 토론에 등장합니다."
        backHref={`/projects/${routeProjectId}`}
        backLabel="프로젝트 개요"
      />

      <Card padding="md" className="mb-4" data-tour="agents">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-4">
          <Select
            label="연령대"
            name="age_range"
            options={[{ value: '', label: '전체 연령' }, ...ageOptions]}
            value={ageFilter}
            onChange={e => setAgeFilter(e.target.value)}
          />
          <Select
            label="성별"
            name="gender"
            options={[{ value: '', label: '전체 성별' }, ...genderOptions]}
            value={genderFilter}
            onChange={e => setGenderFilter(e.target.value)}
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
          <span>
            {loading
              ? '불러오는 중…'
              : (ageFilter || genderFilter)
                ? `${filtered.length}명 일치 (전체 ${list.length}명)`
                : `${list.length}명`}
          </span>
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
            아직 등록된 AI 소비자가 없습니다. 샘플 30명으로 흐름을 미리 체험할 수 있습니다.
          </p>
          {seedError && <p className="text-xs text-error mb-3">{seedError}</p>}
          <Button onClick={startSeed} loading={seeding} disabled={!token}>
            샘플 30명 불러오기
          </Button>
        </Card>
      )}

      {!loading && list.length > 0 && filtered.length === 0 && (
        <Card padding="lg" className="text-center mb-4">
          <p className="text-sm text-text-muted">
            선택한 조건에 맞는 AI 소비자가 없습니다. 필터를 조정해보세요.
          </p>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map(a => {
          const selected = selectedAgentIds.includes(a.id);
          const demo = [a.age_range, a.gender].filter(Boolean) as string[];
          return (
            <Card
              key={a.id}
              padding="md"
              className={`h-full ${selected ? 'border-ditto-indigo bg-ditto-indigo-light/40 ring-2 ring-ditto-indigo' : 'hover:border-ditto-indigo/40'}`}
            >
              <div className="flex items-start gap-3">
                <div className="text-2xl leading-none shrink-0">{a.emoji || '👤'}</div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Link
                      href={`/projects/${routeProjectId}/agents/${a.id}`}
                      className="text-sm font-bold text-text-primary truncate hover:text-ditto-indigo focus:outline-none focus:underline"
                    >
                      {a.display_name || `AI 소비자 ${a.id.slice(0, 6)}`}
                    </Link>
                    {demo.map(d => (
                      <Badge key={d} variant="neutral" size="sm" className="shrink-0">{d}</Badge>
                    ))}
                  </div>
                  {(() => {
                    const kws = personaKeywords(a.persona_params, 3);
                    return kws.length > 0 ? (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {kws.map((k) => (
                          <Badge key={k} variant="violet" size="sm">{k}</Badge>
                        ))}
                      </div>
                    ) : null;
                  })()}
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
          {saved && selectedCount > 0 && (
            <>
              <span className="text-xs font-medium text-success">✓ 저장됨</span>
              <Button href={`/projects/${routeProjectId}/chat`} variant="secondary" size="sm">1:1 채팅 →</Button>
              <Button href={`/projects/${routeProjectId}/fgi`} variant="secondary" size="sm">FGI 토론 →</Button>
            </>
          )}
          <Button variant="ghost" onClick={clearSelection} disabled={selectedCount === 0}>
            선택 해제
          </Button>
          <Button variant="primary" onClick={onSave} disabled={selectedCount === 0}>
            선택 저장
          </Button>
        </div>
      </div>
    </PageContainer>
  );
}
