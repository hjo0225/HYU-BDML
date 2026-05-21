'use client';

// 인앱 FGI 페이지 (plan 0008 v2 · item 0) — 실서비스 라우트. 데모 투어도 이 화면을 거친다.
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';
import { AuthGuard } from '@/components/auth/AuthGuard';
import { AppShell } from '@/components/layout/AppShell';
import { PageContainer } from '@/components/layout/PageContainer';
import { PageHeader } from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/Button';
import { LoadingState } from '@/components/ui/Spinner';
import { EmptyState } from '@/components/ui/EmptyState';
import { DemoFGIStep } from '@/components/demo/DemoFGIStep';
import { useAuth } from '@/contexts/AuthContext';
import { useProjectContext } from '@/contexts/ProjectContext';
import { agents as agentsApi } from '@/lib/api';
import type { Agent, FGIReport } from '@/lib/types';

function FGIView() {
  const params = useParams<{ id: string }>();
  const projectId = params?.id;
  const { token } = useAuth();
  const { selectedAgentIds } = useProjectContext();
  const [agents, setAgents] = useState<Agent[] | null>(null);
  const [doneSessionId, setDoneSessionId] = useState<string | null>(null);

  // AI 소비자에서 저장한 선택만 참여 (선택 순서 보존). 미선택 시 빈 목록.
  useEffect(() => {
    if (!token || !projectId) return;
    if (selectedAgentIds.length === 0) { setAgents([]); return; }
    agentsApi.list(token, projectId, { limit: 100 })
      .then((all) => {
        const byId = new Map(all.map((a) => [a.id, a]));
        setAgents(selectedAgentIds.map((id) => byId.get(id)).filter((a): a is Agent => !!a).slice(0, 6));
      })
      .catch(() => setAgents([]));
  }, [token, projectId, selectedAgentIds]);

  // 보고서는 회의 페이지에 바로 띄우지 않고, 다음 페이지에서 보여준다.
  const onComplete = useCallback((sid: string, _rep: FGIReport) => setDoneSessionId(sid), []);

  if (!token || !projectId) return null;
  if (agents === null) return <PageContainer><LoadingState label="에이전트를 불러오는 중…" /></PageContainer>;

  return (
    <PageContainer width="wide">
      <PageHeader
        title="FGI 진행"
        subtitle="선택된 에이전트로 AI 모더레이터 진행 다자 토론을 실행하고, 인사이트 보고서를 생성합니다."
        backHref={`/projects/${projectId}/agents`}
        backLabel="에이전트 카탈로그"
      />
      {agents.length === 0 ? (
        <EmptyState
          icon="🧑‍🤝‍🧑"
          title="참여할 AI 소비자가 없습니다"
          description="'AI 소비자' 탭에서 참여자를 선택·저장한 뒤 FGI를 시작하세요."
          action={<Button href={`/projects/${projectId}/agents`} variant="primary" size="sm">AI 소비자로 이동 →</Button>}
        />
      ) : (
        <div className="space-y-6" data-tour="fgi">
          <DemoFGIStep token={token} projectId={projectId} agents={agents} onComplete={onComplete} />
          {doneSessionId && (
            <div className="rounded-2xl border border-success/40 bg-surface p-5 text-center">
              <p className="mb-1 text-sm font-semibold text-text-primary">회의가 종료되었습니다.</p>
              <p className="mb-4 text-sm text-text-muted">대화를 분석한 인사이트 보고서가 준비됐어요.</p>
              <Button href={`/projects/${projectId}/fgi/report/${doneSessionId}`} variant="primary">
                인사이트 보고서 보기 →
              </Button>
            </div>
          )}
        </div>
      )}
    </PageContainer>
  );
}

export default function FGIPage() {
  return (
    <AuthGuard>
      <AppShell>
        <FGIView />
      </AppShell>
    </AuthGuard>
  );
}
