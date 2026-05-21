'use client';

// 질문 관리 라우트 (plan 0014) — 사이드바 세부 탭. 생성된 질문지 표시·편집.
import { useParams } from 'next/navigation';
import { AuthGuard } from '@/components/auth/AuthGuard';
import { AppShell } from '@/components/layout/AppShell';
import { PageContainer } from '@/components/layout/PageContainer';
import { PageHeader } from '@/components/layout/PageHeader';
import { SurveyManager } from '@/components/dashboard/SurveyManager';

function QuestionsView() {
  const params = useParams<{ id: string }>();
  const projectId = params?.id;
  if (!projectId) return null;
  return (
    <PageContainer width="wide">
      <PageHeader
        title="질문 관리"
        subtitle="조사 주제에 맞춰 생성된 공통·도메인 설문과 인터뷰 질문지"
        backHref={`/projects/${projectId}`}
        backLabel="프로젝트 개요"
      />
      <div data-tour="survey-panel">
        <SurveyManager projectId={projectId} />
      </div>
    </PageContainer>
  );
}

export default function QuestionsPage() {
  return (
    <AuthGuard>
      <AppShell>
        <QuestionsView />
      </AppShell>
    </AuthGuard>
  );
}
