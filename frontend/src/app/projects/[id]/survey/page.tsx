'use client';

// 설문 설계 페이지 (plan 0008 v2 · item 0b) — 실서비스 라우트. 데모 투어 2단계가 이 화면을 거친다.
import { useParams } from 'next/navigation';
import { AuthGuard } from '@/components/auth/AuthGuard';
import { AppShell } from '@/components/layout/AppShell';
import { PageContainer } from '@/components/layout/PageContainer';
import { PageHeader } from '@/components/layout/PageHeader';
import { DemoSurveyStep } from '@/components/demo/DemoSimpleSteps';

function SurveyView() {
  const params = useParams<{ id: string }>();
  const projectId = params?.id;
  return (
    <PageContainer width="wide">
      <PageHeader
        title="설문 설계"
        subtitle="전 도메인 공통 설문 + 도메인 특화 설문·인터뷰 자동 생성"
        backHref={`/projects/${projectId}`}
        backLabel="프로젝트 개요"
      />
      <div data-tour="survey">
        <DemoSurveyStep />
      </div>
    </PageContainer>
  );
}

export default function SurveyPage() {
  return (
    <AuthGuard>
      <AppShell>
        <SurveyView />
      </AppShell>
    </AuthGuard>
  );
}
