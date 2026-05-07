'use client';

import { AuthGuard } from '@/components/auth/AuthGuard';
import { AppShell } from '@/components/layout/AppShell';
import { useAuth } from '@/contexts/AuthContext';

export default function DashboardPage() {
  const { user } = useAuth();

  return (
    <AuthGuard>
      <AppShell>
        <div className="p-8">
          <div className="mb-8">
            <h1 className="text-2xl font-bold text-text-primary">대시보드</h1>
            <p className="text-text-secondary text-sm mt-1">
              안녕하세요, <span className="font-medium">{user?.name || user?.email}</span> 님
            </p>
          </div>

          {/* 통계 카드 */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
            {[
              { label: '리서치 프로젝트', value: '0', color: 'indigo', desc: '진행 중인 프로젝트' },
              { label: '에이전트', value: '0', color: 'violet', desc: '생성된 AI 에이전트' },
              { label: '대화 세션', value: '0', color: 'indigo', desc: '누적 대화 수' },
            ].map(({ label, value, desc }) => (
              <div key={label} className="card">
                <p className="text-sm text-text-muted mb-1">{label}</p>
                <p className="text-3xl font-bold text-text-primary mb-1">{value}</p>
                <p className="text-xs text-text-muted">{desc}</p>
              </div>
            ))}
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
        </div>
      </AppShell>
    </AuthGuard>
  );
}
