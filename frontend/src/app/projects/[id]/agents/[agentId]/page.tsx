'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';
import { AuthGuard } from '@/components/auth/AuthGuard';
import { AppShell } from '@/components/layout/AppShell';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { LoadingState } from '@/components/ui/Spinner';
import { PageContainer } from '@/components/layout/PageContainer';
import { V1Gauge } from '@/components/dashboard/V1Gauge';
import { PersonaProfile } from '@/components/dashboard/PersonaProfile';
import { statusColorVar } from '@/components/dashboard/score';
import { useAuth } from '@/contexts/AuthContext';
import { agents as agentsApi, evaluations as evalApi } from '@/lib/api';
import type { AgentDetail, EvaluationSnapshot } from '@/lib/types';

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

  const latest = snapshots[0] ?? null;
  const sync = latest?.identity_stats?.sync ?? null;
  const distinct = latest?.identity_stats?.distinct ?? null;

  if (loading) {
    return <PageContainer><LoadingState /></PageContainer>;
  }

  if (!agent) {
    return (
      <PageContainer>
        <Card padding="lg">
          <p className="text-sm text-error mb-3">{error || '에이전트를 찾을 수 없습니다.'}</p>
          <Link href={`/projects/${projectId}/agents`} className="text-sm text-ditto-indigo hover:underline">← AI 소비자</Link>
        </Card>
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <div className="mb-4">
        <Link href={`/projects/${projectId}/agents`} className="text-xs text-text-muted hover:text-ditto-indigo">← AI 소비자</Link>
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
            <div className="flex items-center gap-2 mt-2 text-xs text-text-muted">
              {[agent.age_range, agent.gender].filter(Boolean).map((d) => (
                <Badge key={String(d)} variant="neutral" size="sm">{String(d)}</Badge>
              ))}
            </div>
          </div>
          <div className="shrink-0 flex flex-col items-end gap-2 w-44">
            <Button
              href={`/projects/${projectId}/agents/${agent.id}/chat`}
              variant="primary"
              fullWidth
            >
              1:1 대화하기
            </Button>
            {error && <p className="text-2xs text-error">{error}</p>}
          </div>
        </div>
      </Card>

      {/* 6-Lens 페르소나 프로파일 — 키워드 특징 + 렌즈별 수치 */}
      <Card padding="md" className="mb-4">
        <CardHeader
          title="6-Lens 페르소나 프로파일"
          subtitle="설문 응답에서 도출한 심리·행동 척도 (L1~L6)"
        />
        <PersonaProfile params={agent.persona_params} />
      </Card>

      {/* V1 · V3 각각 한 카드씩 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

        {/* ── V1 ───────────────────────────────────────────────────────── */}
        <Card padding="md" className="flex flex-col">
          <CardHeader
            title="진짜 그 사람처럼 답하나?"
            subtitle="실제 응답자와 얼마나 닮았는지"
          />

          <div className="mt-2 flex justify-center items-center h-56">
            <V1Gauge sync={sync} size={420} />
          </div>

          <div className="mt-2 text-sm text-text-secondary leading-relaxed h-24">
            <p>
              에이전트한테 <strong>새로운 질문 몇 개</strong>를 던져봅니다 — 예를 들어
              &quot;최근에 한 큰 소비는?&quot;, &quot;본인 라이프스타일을 한 단어로?&quot; 같은 거요.
              그리고 그 답변을 <strong>실제 그 사람이 한 답변</strong>과 비교합니다.
            </p>
          </div>

          <div className="mt-2 grid grid-cols-3 gap-1.5 text-2xs">
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
            <div className="mt-2 flex flex-col items-center justify-center gap-2 h-56">
              <div className="rounded-2xl border-4 border-dashed border-border flex items-center justify-center w-44 h-36">
                <span className="text-xs text-text-muted">평가 전</span>
              </div>
              <span className="text-xs text-text-muted">아직 측정 안 됨</span>
            </div>
          ) : (
            <div className="mt-2 flex flex-col items-center justify-center h-56">
              <div
                className="text-7xl font-bold tabular-nums leading-none"
                style={{ color: statusColorVar[v3Status(distinct)] }}
              >
                {distinct.toFixed(2)}
              </div>
            </div>
          )}

          <div className="mt-2 text-sm text-text-secondary leading-relaxed h-24">
            <p>
              프로젝트의 30명 에이전트가 <strong>서로 얼마나 다른 인격</strong>인지를 봅니다.
              모두에게 같은 질문을 던졌을 때 답변이 천차만별이면 다양한 사람들이 모인 거고,
              비슷비슷한 답만 나오면 다 똑같은 사람을 30번 복사한 거나 마찬가지죠.
            </p>
          </div>

          <div className="mt-2 grid grid-cols-3 gap-1.5 text-2xs">
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
    </PageContainer>
  );
}
