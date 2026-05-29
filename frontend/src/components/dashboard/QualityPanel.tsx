'use client';

// 품질 평가 탭 (plan 0013 → 0023 + v7): 프로젝트 전체 에이전트의 사전계산된 v7 유사도 대시보드.
// V3 산점도/군집 시대를 끝내고, 각 에이전트의 "그 사람과 얼마나 닮았나" 를 자동 노출한다.
// V1/V3 "품질 평가 실행" 버튼 제거 — 사전계산이 SSOT.
import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Spinner } from '@/components/ui/Spinner';
import { SimilarityDashboard } from '@/components/dashboard/SimilarityDashboard';
import {
  HoldoutEvalCinematic,
  type OverallAgentRow,
  type OverallSamplePair,
} from '@/components/dashboard/HoldoutEvalCinematic';
import { agents as agentsApi } from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';
import type { Agent, HoldoutPair, HoldoutResult, ScatterResponse } from '@/lib/types';
import { lensTone, LENS_TONE_TEXT } from '@/lib/lensTone';

const pctText = (v: number | null | undefined) => (v == null ? '—' : `${Math.round(v * 100)}%`);

// 시네마틱은 진입·새로고침·카드 클릭마다 매번 재생한다 (세션 게이팅 없음).
// 접근성 prefers-reduced-motion 만 존중해 즉시 대시보드로 전환.
function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <p className="text-2xs font-medium text-text-muted">{label}</p>
      <p className="mt-1 text-2xl font-bold text-text-primary">{value}</p>
      {hint && <p className="mt-0.5 text-2xs text-text-muted">{hint}</p>}
    </div>
  );
}

// Props 시그니처 유지 — quality/page.tsx 가 그대로 호출. scatter/onEvaluated 는 무시(레거시 호환).
export function QualityPanel({
  projectId,
  agents,
  scatter: _scatter,
  onEvaluated: _onEvaluated,
}: {
  projectId: string;
  agents: Agent[];
  scatter: ScatterResponse | null;
  onEvaluated?: () => void;
}) {
  const { token } = useAuth();
  const [holdoutByAgent, setHoldoutByAgent] = useState<Record<string, HoldoutResult>>({});
  const [loading, setLoading] = useState(true);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  // 평가 연출(plan 0027) 상태 — 매번 재생 정책이라 세션 기록 없음.
  const [overallPhase, setOverallPhase] = useState<'overall' | 'ready'>('ready');
  const [animatingAgentId, setAnimatingAgentId] = useState<string | null>(null);
  const [reduced, setReduced] = useState(false);

  // 마운트 시 모든 에이전트의 사전계산 holdout 결과를 병렬 fetch. 미적재는 조용히 skip.
  useEffect(() => {
    if (!token || agents.length === 0) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    (async () => {
      const results = await Promise.all(
        agents.map(async (a) => {
          try {
            const h = await agentsApi.holdout(token, a.id);
            return [a.id, h] as const;
          } catch {
            return [a.id, null] as const;
          }
        }),
      );
      if (cancelled) return;
      const map: Record<string, HoldoutResult> = {};
      for (const [id, h] of results) {
        if (h) map[id] = h;
      }
      setHoldoutByAgent(map);
      const first = agents.find((a) => map[a.id]);
      if (first) setSelectedAgentId(first.id);

      // 매번 재생 — reduced-motion 만 즉시 대시보드, 결과가 없으면 보일 게 없으니 ready.
      const rm = prefersReducedMotion();
      const hasResults = Object.keys(map).length > 0;
      setReduced(rm);
      setOverallPhase(rm || !hasResults ? 'ready' : 'overall');

      setLoading(false);
    })();
    return () => { cancelled = true; };
  }, [agents, token, projectId]);

  // 프로젝트 단위 집계 — 평균 닮음 / 최고 / 최저 / 평가 완료 수.
  const stats = useMemo(() => {
    const evaluated = Object.values(holdoutByAgent);
    if (evaluated.length === 0) return null;
    const scores = evaluated.map((h) => h.agreement_score);
    const avg = scores.reduce((s, v) => s + v, 0) / scores.length;
    const max = Math.max(...scores);
    const min = Math.min(...scores);
    const best = evaluated.find((h) => h.agreement_score === max);
    const worst = evaluated.find((h) => h.agreement_score === min);
    return { avg, max, min, evaluated: evaluated.length, best, worst };
  }, [holdoutByAgent]);

  const select = useCallback((id: string) => {
    if (!holdoutByAgent[id]) return;
    setSelectedAgentId(id);
    // reduced-motion 외에는 매번 개별 연출 재생.
    if (!reduced) setAnimatingAgentId(id);
  }, [holdoutByAgent, reduced]);

  // 전체 연출 종료 — 대시보드 노출. 직후 선택된 에이전트는 자동 재생 안 함 (클릭 시에만).
  const finishOverall = useCallback(() => {
    setOverallPhase('ready');
  }, []);

  // 개별 연출 종료 — 대시보드 노출.
  const finishAgent = useCallback(() => {
    setAnimatingAgentId(null);
  }, []);

  // 전체 연출용 에이전트 행 (점수 내림차순, 최대 8개) + 대표 문항 수.
  const agentRows = useMemo<OverallAgentRow[]>(() =>
    agents
      .filter((a) => holdoutByAgent[a.id])
      .map((a) => ({
        id: a.id,
        name: a.display_name || '(이름 없음)',
        emoji: a.emoji ?? '👤',
        score: holdoutByAgent[a.id].agreement_score,
      }))
      .sort((x, y) => y.score - x.score)
      .slice(0, 8),
  [agents, holdoutByAgent]);
  const perAgentN = Object.values(holdoutByAgent)[0]?.n_total ?? 0;

  // 가속 스트림용 샘플 — 에이전트별 페어를 라운드로빈으로 인터리브해 최대 20개. 인접 카드가
  // 같은 에이전트가 아니라 다양성이 자연스럽게 드러난다. verdict 분포는 실제 데이터를 그대로 반영.
  const samplePairs = useMemo<OverallSamplePair[]>(() => {
    if (Object.keys(holdoutByAgent).length === 0) return [];
    const TARGET = 20;
    const toCard = (agent: Agent, pair: HoldoutPair): OverallSamplePair => ({
      agentName: agent.display_name || '(이름 없음)',
      agentEmoji: agent.emoji ?? '👤',
      question: pair.question,
      agentAnswer: pair.agent_answer_display ?? pair.agent_answer,
      verdict: pair.verdict,
    });
    // 각 에이전트의 페어 풀(길이 제한 포함) 을 한 줄에 모은다.
    const lanes: Array<{ agent: Agent; pool: HoldoutPair[] }> = [];
    for (const agent of agents) {
      const h = holdoutByAgent[agent.id];
      if (!h) continue;
      const pool = (h.all_pairs ?? [...h.top_matches, ...h.top_mismatches]).filter(
        (p) => p.question.length > 0,
      );
      if (pool.length > 0) lanes.push({ agent, pool });
    }
    // 라운드로빈 인터리브.
    const collected: OverallSamplePair[] = [];
    let depth = 0;
    while (collected.length < TARGET) {
      let added = false;
      for (const lane of lanes) {
        if (collected.length >= TARGET) break;
        const pair = lane.pool[depth];
        if (!pair) continue;
        collected.push(toCard(lane.agent, pair));
        added = true;
      }
      if (!added) break;
      depth += 1;
    }
    return collected;
  }, [agents, holdoutByAgent]);

  const selectedHoldout = selectedAgentId ? holdoutByAgent[selectedAgentId] : null;
  const selectedAgent = selectedAgentId ? agents.find((a) => a.id === selectedAgentId) : null;

  if (agents.length === 0) {
    return (
      <Card padding="lg" className="border-dashed">
        <p className="mb-1 text-sm text-text-secondary">이 프로젝트에 AI 소비자가 없습니다.</p>
        <Link
          href={`/projects/${projectId}/agents`}
          className="mt-3 inline-block text-sm text-ditto-indigo hover:underline"
        >
          AI 소비자로 이동 →
        </Link>
      </Card>
    );
  }

  if (loading) {
    return (
      <Card padding="lg">
        <div className="flex items-center gap-2 text-sm text-text-muted">
          <Spinner size="sm" /> 사전계산된 평가 결과를 불러오는 중…
        </div>
      </Card>
    );
  }

  if (stats == null) {
    return (
      <Card padding="lg" className="border-dashed">
        <p className="mb-1 text-sm text-text-secondary">아직 사전계산된 평가 결과가 없습니다.</p>
        <p className="mb-3 text-sm text-text-muted">
          백엔드에서 아래 명령으로 평가를 사전계산하면 자동으로 표시됩니다.
        </p>
        <pre className="rounded-lg bg-bg p-3 text-xs text-text-primary">
          python -m scripts.run_holdout_eval --project-id {projectId}
        </pre>
      </Card>
    );
  }

  // 첫 진입 전체 연출 — stat/grid 대신 풀-테이크오버.
  if (overallPhase === 'overall' && agentRows.length > 0) {
    return (
      <HoldoutEvalCinematic
        mode="overall"
        agentRows={agentRows}
        evaluatedCount={stats.evaluated}
        perAgentN={perAgentN}
        avg={stats.avg}
        samplePairs={samplePairs}
        onComplete={finishOverall}
      />
    );
  }

  return (
    <div className="space-y-4">
      {/* 프로젝트 단위 집계 4개 카드 */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat
          label="평균 닮은 정도"
          value={pctText(stats.avg)}
          hint={`${stats.evaluated} / ${agents.length} 명 평가 완료`}
        />
        <Stat
          label="가장 닮은 에이전트"
          value={pctText(stats.max)}
          hint={stats.best?.agent_display_name ?? '—'}
        />
        <Stat
          label="가장 덜 닮은 에이전트"
          value={pctText(stats.min)}
          hint={stats.worst?.agent_display_name ?? '—'}
        />
        <Stat
          label="평가 방식"
          value="홀드아웃 유사도"
          hint="실제 응답 vs AI 답변 LLM-Judge"
        />
      </div>

      {/* 에이전트 그리드 — 닮은정도 */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {agents.map((a) => {
          const h = holdoutByAgent[a.id];
          const isSelected = a.id === selectedAgentId;
          const pct = h ? Math.round(h.agreement_score * 100) : null;
          return (
            <button
              key={a.id}
              type="button"
              onClick={() => select(a.id)}
              disabled={!h}
              className={`block w-full rounded-xl border bg-surface p-3 text-left transition-all hover:shadow-card disabled:opacity-60 ${
                isSelected
                  ? 'border-ditto-indigo shadow-card ring-2 ring-ditto-indigo/20'
                  : 'border-border'
              }`}
            >
              <div className="flex items-start gap-3">
                <span className="text-2xl">{a.emoji ?? '👤'}</span>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-semibold text-text-primary">
                    {a.display_name || '(이름 없음)'}
                  </p>
                  {(a.age_range || a.gender) && (
                    <div className="mt-0.5 flex flex-wrap gap-1">
                      {([a.age_range, a.gender].filter(Boolean) as string[]).map((d) => (
                        <Badge key={d} variant="neutral" size="sm">{d}</Badge>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              <div className="mt-3 border-t border-border pt-2.5">
                {h ? (
                  <>
                    <div className="mb-2 flex items-center justify-between">
                      <span className="text-2xs font-medium text-text-muted">실제 사람과의 닮은 정도</span>
                      <span className={`text-base font-bold tabular-nums ${LENS_TONE_TEXT[lensTone(h.agreement_score)]}`}>
                        {pct}<span className="text-2xs text-text-muted">%</span>
                      </span>
                    </div>
                  </>
                ) : (
                  <span className="text-2xs text-text-muted">평가 결과 없음 (사전계산 필요)</span>
                )}
              </div>
            </button>
          );
        })}
      </div>

      {/* 선택된 에이전트 — 미연출이면 개별 평가 연출, 끝나면 v7 풀 대시보드 */}
      {selectedHoldout && selectedAgent && (
        animatingAgentId === selectedAgentId ? (
          <HoldoutEvalCinematic
            mode="agent"
            result={selectedHoldout}
            onComplete={finishAgent}
          />
        ) : (
          <Card>
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <span className="text-2xs font-bold uppercase tracking-wider text-ditto-indigo">
                선택된 에이전트의 상세 평가
              </span>
              <Badge variant="indigo" size="sm">
                {selectedAgent.emoji ?? '👤'} {selectedAgent.display_name ?? '에이전트'}
              </Badge>
              <span className="ml-auto text-2xs text-text-muted">
                위 카드를 클릭하면 다른 에이전트의 대시보드로 전환됩니다
              </span>
            </div>
            <SimilarityDashboard result={selectedHoldout} />
          </Card>
        )
      )}
    </div>
  );
}
