'use client';

// FGI 인사이트 보고서 페이지 (plan 0018) — 회의 종료 후 '다음 페이지'에서 보고서를 본다.
// 세션의 minutes_md(보고서 JSON)를 파싱해 렌더.
import { useParams, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { AuthGuard } from '@/components/auth/AuthGuard';
import { AppShell } from '@/components/layout/AppShell';
import { PageContainer } from '@/components/layout/PageContainer';
import { PageHeader } from '@/components/layout/PageHeader';
import { LoadingState } from '@/components/ui/Spinner';
import { Card } from '@/components/ui/Card';
import { FGIReportView } from '@/components/fgi/FGIReportView';
import { useAuth } from '@/contexts/AuthContext';
import { fgi as fgiApi } from '@/lib/api';
import type { FGIReport } from '@/lib/types';

function ReportView() {
  const params = useParams<{ id: string; sessionId: string }>();
  const projectId = params?.id;
  const sessionId = params?.sessionId;
  const router = useRouter();
  const { token } = useAuth();
  const [report, setReport] = useState<FGIReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token || !sessionId) return;
    setLoading(true);
    fgiApi.get(token, sessionId)
      .then((s) => {
        if (!s.minutes_md) { setError('보고서가 아직 생성되지 않았습니다.'); return; }
        try {
          setReport(JSON.parse(s.minutes_md) as FGIReport);
        } catch {
          setError('보고서를 읽을 수 없습니다.');
        }
      })
      .catch((e) => setError(e instanceof Error ? e.message : '불러오기 실패'))
      .finally(() => setLoading(false));
  }, [token, sessionId]);

  if (!token || !projectId) return null;

  return (
    <PageContainer width="wide">
      <PageHeader
        title="인사이트 보고서"
        subtitle="FGI 대화를 분석한 핵심 인사이트·합의·이견"
        backHref={`/projects/${projectId}/fgi`}
        backLabel="FGI 진행"
      />
      {loading ? (
        <LoadingState label="보고서를 불러오는 중…" />
      ) : report ? (
        <FGIReportView report={report} onDashboard={() => router.push(`/projects/${projectId}`)} />
      ) : (
        <Card padding="lg">
          <p className="text-sm text-error">{error || '보고서를 찾을 수 없습니다.'}</p>
        </Card>
      )}
    </PageContainer>
  );
}

export default function FGIReportPage() {
  return (
    <AuthGuard>
      <AppShell>
        <ReportView />
      </AppShell>
    </AuthGuard>
  );
}
