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
import { PersonaProfile } from '@/components/dashboard/PersonaProfile';
import { SimilarityDashboard } from '@/components/dashboard/SimilarityDashboard';
import { useAuth } from '@/contexts/AuthContext';
import { agents as agentsApi } from '@/lib/api';
import type { AgentDetail, HoldoutResult } from '@/lib/types';


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
  const [holdout, setHoldout] = useState<HoldoutResult | null>(null);
  const [holdoutMissing, setHoldoutMissing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!token || !agentId) return;
    setLoading(true);
    setError(null);
    setHoldoutMissing(false);
    try {
      const a = await agentsApi.get(token, agentId);
      setAgent(a);
      try {
        const h = await agentsApi.holdout(token, agentId);
        setHoldout(h);
      } catch {
        // 404 = 사전계산 미실행. 페이지는 계속 표시.
        setHoldout(null);
        setHoldoutMissing(true);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '불러오기 실패');
    } finally {
      setLoading(false);
    }
  }, [token, agentId]);

  useEffect(() => { reload(); }, [reload]);

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

      {/* 성능 평가 — 홀드아웃 유사도 대시보드 (plan 0023) */}
      {holdout ? (
        <SimilarityDashboard result={holdout} />
      ) : (
        <Card padding="lg">
          <CardHeader
            title="실제 사람과 얼마나 닮았나?"
            subtitle="홀드아웃 유사도 평가"
          />
          <p className="mt-3 text-sm text-text-secondary">
            {holdoutMissing
              ? '아직 사전계산이 실행되지 않았습니다. 백엔드에서 다음을 실행하면 결과가 표시됩니다:'
              : '평가 결과를 불러오는 중입니다.'}
          </p>
          {holdoutMissing && (
            <pre className="mt-2 overflow-x-auto rounded-lg bg-bg p-3 text-xs text-text-primary">
              python -m scripts.run_holdout_eval --agent-ids {agent.id}
            </pre>
          )}
        </Card>
      )}
    </PageContainer>
  );
}
