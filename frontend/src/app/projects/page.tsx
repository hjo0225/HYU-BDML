'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { AuthGuard } from '@/components/auth/AuthGuard';
import { AppShell } from '@/components/layout/AppShell';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import { Select } from '@/components/ui/Select';
import { Badge } from '@/components/ui/Badge';
import { EmptyState } from '@/components/ui/EmptyState';
import { PageContainer } from '@/components/layout/PageContainer';
import { PageHeader } from '@/components/layout/PageHeader';
import { useAuth } from '@/contexts/AuthContext';
import { useTour, TOUR_STEPS } from '@/contexts/TourContext';
import { projects as projectsApi } from '@/lib/api';
import { DEMO_BRIEF } from '@/lib/demoScenario';
import type { ResearchProject } from '@/lib/types';

const STATUS_OPTIONS = [
  { value: '', label: '전체' },
  { value: 'draft', label: '준비 중 (draft)' },
  { value: 'active', label: '진행 중 (active)' },
  { value: 'archived', label: '보관 (archived)' },
];

const STATUS_LABEL: Record<ResearchProject['status'], string> = {
  draft: '준비 중',
  active: '진행 중',
  archived: '보관',
};

const STATUS_VARIANT: Record<ResearchProject['status'], 'neutral' | 'indigo'> = {
  draft: 'neutral',
  active: 'indigo',
  archived: 'neutral',
};

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '-';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '-';
  return d.toLocaleDateString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit' });
}

export default function ProjectsPage() {
  return (
    <AuthGuard>
      <AppShell>
        <ProjectsView />
      </AppShell>
    </AuthGuard>
  );
}

function ProjectsView() {
  const { token, user } = useAuth();
  const isDemo = user?.role === 'demo';  // 공용 데모 계정은 프로젝트 생성 불가 (plan 0009)
  const tour = useTour();
  // 데모 투어 단계 — 0='create'(생성 버튼 강조) → 1='brief'(의뢰서 모달 시연).
  const isBriefStep = tour.active && TOUR_STEPS[tour.step]?.key === 'brief';
  // 'projects' 단계 도달 전(생성 버튼·의뢰서)에는 데모 프로젝트를 목록에서 숨긴다.
  // → "아직 생성 안 됨 → 프로젝트 생성 후 나타남" 흐름을 연출.
  const projectsStepIdx = TOUR_STEPS.findIndex((s) => s.key === 'projects');
  const hideDemoProjects = isDemo && tour.active && tour.step < projectsStepIdx;
  const [list, setList] = useState<ResearchProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [creating, setCreating] = useState(false);
  // 새 프로젝트 의뢰서 모달 상태
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ title: '', objective: '', target: '', useCase: '' });

  const filterOpts = useMemo(
    () => (statusFilter ? { status: statusFilter as 'draft' | 'active' | 'archived' } : undefined),
    [statusFilter],
  );

  const reload = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const data = await projectsApi.list(token, filterOpts);
      setList(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : '불러오기 실패');
    } finally {
      setLoading(false);
    }
  }, [token, filterOpts]);

  useEffect(() => { reload(); }, [reload]);

  // 데모 투어 0단계 진입 시 — 포토이즘 의뢰서를 미리 채워 모달을 연다 (시연용).
  // 단계를 벗어나면(다음/종료) 모달을 닫아 다음 스텝 스포트라이트와 충돌하지 않게 한다.
  useEffect(() => {
    if (!isDemo) return;
    if (isBriefStep) {
      setForm({
        title: `${DEMO_BRIEF.company} 재방문율 진단`,
        objective: DEMO_BRIEF.objective,
        target: DEMO_BRIEF.target,
        useCase: DEMO_BRIEF.useCase,
      });
      setShowModal(true);
    } else {
      setShowModal(false);
    }
  }, [isDemo, isBriefStep]);

  const onCreate = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    // 데모: 실제 생성 없이 의뢰서 시연만 — 다음 투어 단계(프로젝트 목록)로 진행.
    if (isDemo) {
      setShowModal(false);
      tour.setStep(tour.step + 1);
      return;
    }
    if (!token || creating) return;
    setCreating(true);
    setError(null);
    try {
      const title = form.title.trim();
      const brief = {
        objective: form.objective.trim() || undefined,
        target: form.target.trim() || undefined,
        use_case: form.useCase.trim() || undefined,
      };
      const hasBrief = brief.objective || brief.target || brief.use_case;
      await projectsApi.create(token, {
        ...(title ? { title } : {}),
        ...(hasBrief ? { brief } : {}),
      });
      setForm({ title: '', objective: '', target: '', useCase: '' });
      setShowModal(false);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : '생성 실패');
    } finally {
      setCreating(false);
    }
  }, [token, creating, form, reload, isDemo, tour]);

  // 투어 'projects' 단계 도달 전에는 데모 프로젝트를 감춰 빈 목록으로 보인다.
  const visibleList = hideDemoProjects ? [] : list;

  return (
    <PageContainer>
      <PageHeader
        title="리서치 프로젝트"
        subtitle="조사 의뢰서를 작성해 프로젝트를 만들고, AI 소비자와 인터뷰·평가를 진행합니다."
        actions={
          !isDemo ? (
            <Button data-tour="create-project" onClick={() => setShowModal(true)} disabled={!token}>
              + 새 프로젝트
            </Button>
          ) : tour.active ? (
            // 데모 투어 중에는 생성 버튼을 노출해 첫 단계('create')에서 직접 누르게 한다.
            // 실제 생성 대신 다음 단계('brief')로 진행 → 의뢰서 모달이 자동으로 열린다.
            <Button data-tour="create-project" onClick={() => tour.setStep(tour.step + 1)}>
              + 새 프로젝트
            </Button>
          ) : (
            <span className="text-xs text-text-muted">
              데모에서는 준비된 프로젝트만 둘러볼 수 있어요. 직접 만들려면 회원가입하세요.
            </span>
          )
        }
      />

      <div className="flex items-center gap-3 mb-4">
        <div className="w-56">
          <Select
            name="status_filter"
            options={STATUS_OPTIONS}
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
          />
        </div>
        <span className="text-xs text-text-muted">
          {loading ? '불러오는 중…' : `${visibleList.length}개`}
        </span>
        {error && <span className="text-xs text-error">· {error}</span>}
      </div>

      {showModal && (
        <div
          className="fixed inset-0 z-[100] flex items-start justify-center overflow-y-auto bg-black/50 p-4 sm:items-center"
          onClick={() => !creating && !isBriefStep && setShowModal(false)}
        >
          <Card
            padding="lg"
            elevated
            data-tour="brief-modal"
            className="w-full max-w-lg my-8"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="mb-1 text-lg font-bold text-text-primary">새 프로젝트 의뢰서</h2>
            <p className="mb-5 text-xs text-text-muted">
              {isBriefStep
                ? '데모: 포토이즘 의뢰서를 미리 채워뒀어요. 내용을 살펴보고 "프로젝트 생성"을 눌러보세요.'
                : '입력한 내용은 AI가 설문·인터뷰·FGI 질문을 설계할 때 참고합니다. 제목 외에는 선택 입력입니다.'}
            </p>
            <form onSubmit={onCreate} className="space-y-4">
              <Input
                label="프로젝트 제목"
                name="title"
                placeholder="예: 신규 단백질 음료 컨셉 테스트"
                value={form.title}
                onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
                disabled={creating}
                maxLength={200}
                hint="비워두면 오늘 날짜로 자동 생성됩니다."
              />
              <Textarea
                label="조사 목적"
                name="objective"
                placeholder="예: 재방문율 하락 원인을 진단하고 회복 액션을 도출하고 싶습니다."
                value={form.objective}
                onChange={e => setForm(f => ({ ...f, objective: e.target.value }))}
                disabled={creating}
                rows={2}
              />
              <Textarea
                label="타겟 소비자"
                name="target"
                placeholder="예: 최근 6개월 내 셀프 사진관을 1회 이상 이용한 20·30대"
                value={form.target}
                onChange={e => setForm(f => ({ ...f, target: e.target.value }))}
                disabled={creating}
                rows={2}
              />
              <Textarea
                label="결과 활용 방안"
                name="use_case"
                placeholder="예: 리텐션 개선 캠페인 기획과 매장 운영 개선에 활용 예정"
                value={form.useCase}
                onChange={e => setForm(f => ({ ...f, useCase: e.target.value }))}
                disabled={creating}
                rows={2}
              />
              <div className="flex items-center justify-end gap-2 pt-1">
                {!isBriefStep && (
                  <Button type="button" variant="ghost" onClick={() => setShowModal(false)} disabled={creating}>
                    취소
                  </Button>
                )}
                <Button type="submit" loading={creating} disabled={!isDemo && !token}>
                  프로젝트 생성
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}

      {!loading && visibleList.length === 0 && (
        <Card padding="lg">
          <EmptyState
            icon="📁"
            title="아직 프로젝트가 없습니다"
            description="위 입력창에서 첫 프로젝트를 만들어보세요."
          />
        </Card>
      )}

      <div data-tour="projects" className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {visibleList.map(p => (
          <Link key={p.id} href={`/projects/${p.id}`} className="block focus:outline-none focus:ring-2 focus:ring-ditto-indigo rounded-xl">
            <Card padding="md" className="hover:border-ditto-indigo/40 transition-colors h-full">
              <div className="flex items-start justify-between gap-3 mb-3">
                <h3 className="text-base font-bold text-text-primary truncate flex-1">
                  {p.title || '(제목 없음)'}
                </h3>
                <Badge variant={STATUS_VARIANT[p.status]} size="sm" className="shrink-0">
                  {STATUS_LABEL[p.status]}
                </Badge>
              </div>
              <div className="flex items-center gap-4 text-xs text-text-muted">
                <span>에이전트 <span className="font-medium text-text-primary">{p.agent_count}</span> 명</span>
                <span>·</span>
                <span>업데이트 {formatDate(p.updated_at || p.created_at)}</span>
              </div>
            </Card>
          </Link>
        ))}
      </div>
    </PageContainer>
  );
}
