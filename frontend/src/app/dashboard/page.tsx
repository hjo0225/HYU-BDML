'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { AuthGuard } from '@/components/auth/AuthGuard';
import { AppShell } from '@/components/layout/AppShell';
import { Button } from '@/components/ui/Button';
import { PageContainer } from '@/components/layout/PageContainer';
import { PageHeader } from '@/components/layout/PageHeader';
import { useAuth } from '@/contexts/AuthContext';
import { projects as projectsApi } from '@/lib/api';

export default function DashboardPage() {
  const { user, token } = useAuth();
  const [projectCount, setProjectCount] = useState<number | null>(null);
  const [agentCount, setAgentCount] = useState<number | null>(null);

  useEffect(() => {
    if (!token) return;
    projectsApi.list(token, { limit: 200 })
      .then(list => {
        setProjectCount(list.length);
        setAgentCount(list.reduce((sum, p) => sum + (p.agent_count || 0), 0));
      })
      .catch(() => { setProjectCount(0); setAgentCount(0); });
  }, [token]);

  return (
    <AuthGuard>
      <AppShell>
        <PageContainer width="wide">
          <PageHeader
            title="대시보드"
            subtitle={<>안녕하세요, <span className="font-medium">{user?.name || user?.email}</span> 님</>}
            actions={<Button href="/projects" size="md">+ 새 프로젝트</Button>}
          />

          {/* 통계 카드 */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
            <Link href="/projects" className="card hover:border-ditto-indigo/40 transition-colors">
              <p className="text-sm text-text-muted mb-1">리서치 프로젝트</p>
              <p className="text-3xl font-bold text-text-primary mb-1">{projectCount ?? '—'}</p>
              <p className="text-xs text-text-muted">진행 중인 프로젝트</p>
            </Link>
            <div className="card">
              <p className="text-sm text-text-muted mb-1">에이전트</p>
              <p className="text-3xl font-bold text-text-primary mb-1">{agentCount ?? '—'}</p>
              <p className="text-xs text-text-muted">프로젝트에 속한 에이전트 합계</p>
            </div>
            <div className="card opacity-60">
              <p className="text-sm text-text-muted mb-1">대화 세션</p>
              <p className="text-3xl font-bold text-text-primary mb-1">—</p>
              <p className="text-xs text-text-muted">Slice 3 이후 활성화</p>
            </div>
          </div>

          {/* 시작 가이드 */}
          <div className="card">
            <h2 className="text-base font-semibold text-text-primary mb-4">시작 가이드</h2>
            <div className="space-y-3">
              {[
                { step: '1', title: '응답 데이터 적재', desc: 'Twin-2K-500 설문 응답 JSON을 seed_agent.py로 적재합니다.', done: false },
                { step: '2', title: '에이전트 생성 확인', desc: '6-Lens 채점 → 페르소나 프롬프트 → 임베딩 파이프라인을 검증합니다.', done: false },
                { step: '3', title: '1:1 대화 시작', desc: '에이전트와 대화하며 메모리를 성장시킵니다.', done: false },
                { step: '4', title: '성능 평가', desc: 'V1~V5 지표로 에이전트 신뢰도를 측정합니다.', done: false },
              ].map(({ step, title, desc, done }) => (
                <div key={step} className="flex items-start gap-3 p-3 rounded-lg bg-bg border border-border">
                  <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 mt-0.5 ${
                    done ? 'bg-success text-white' : 'bg-ditto-indigo-light text-ditto-indigo'
                  }`}>
                    {done ? '✓' : step}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-text-primary">{title}</p>
                    <p className="text-xs text-text-muted mt-0.5">{desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </PageContainer>
      </AppShell>
    </AuthGuard>
  );
}
