'use client';

// 품질 평가 라우트 (plan 0014) — 사이드바 세부 탭. 모든 에이전트의 품질 통계 + 다양성 분포.
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';
import { AuthGuard } from '@/components/auth/AuthGuard';
import { AppShell } from '@/components/layout/AppShell';
import { PageContainer } from '@/components/layout/PageContainer';
import { PageHeader } from '@/components/layout/PageHeader';
import { LoadingState } from '@/components/ui/Spinner';
import { QualityPanel } from '@/components/dashboard/QualityPanel';
import { useAuth } from '@/contexts/AuthContext';
import { agents as agentsApi, evaluations as evalApi } from '@/lib/api';
import type { Agent, ScatterResponse } from '@/lib/types';

function QualityView() {
  const params = useParams<{ id: string }>();
  const projectId = params?.id;
  const { token } = useAuth();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [scatter, setScatter] = useState<ScatterResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    if (!token || !projectId) return;
    setLoading(true);
    try {
      const [ag, sc] = await Promise.all([
        agentsApi.list(token, projectId, { limit: 100 }).catch(() => [] as Agent[]),
        evalApi.scatter(token, projectId).catch(() => null),
      ]);
      setAgents(ag);
      setScatter(sc);
    } finally {
      setLoading(false);
    }
  }, [token, projectId]);

  useEffect(() => { reload(); }, [reload]);

  if (!projectId) return null;
  return (
    <PageContainer width="wide">
      <PageHeader
        title="품질 평가"
        subtitle="에이전트의 닮음·다양성 품질 통계와 분포"
        backHref={`/projects/${projectId}`}
        backLabel="프로젝트 개요"
      />
      {loading ? (
        <LoadingState />
      ) : (
        <QualityPanel projectId={projectId} agents={agents} scatter={scatter} onEvaluated={reload} />
      )}
    </PageContainer>
  );
}

export default function QualityPage() {
  return (
    <AuthGuard>
      <AppShell>
        <QualityView />
      </AppShell>
    </AuthGuard>
  );
}
