'use client';

import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { AuthGuard } from '@/components/auth/AuthGuard';
import { AppShell } from '@/components/layout/AppShell';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { LoadingState } from '@/components/ui/Spinner';
import { PageContainer } from '@/components/layout/PageContainer';
import { useAuth } from '@/contexts/AuthContext';
import { useProjectContext } from '@/contexts/ProjectContext';
import { projects as projectsApi } from '@/lib/api';
import type { ResearchProject } from '@/lib/types';

const STATUS_OPTIONS = [
  { value: 'draft', label: '준비 중 (draft)' },
  { value: 'active', label: '진행 중 (active)' },
  { value: 'archived', label: '보관 (archived)' },
];

// 대시보드 → 사이드바 세부 탭으로 이동하는 큰 카드들.
const NAV_CARDS = [
  { key: 'questions', tour: 'card-questions', icon: '✎', title: '질문 관리',
    desc: '생성된 공통·도메인 설문과 인터뷰 질문지를 확인·편집합니다.', sub: (id: string) => `/projects/${id}/questions` },
  { key: 'quality', tour: 'card-quality', icon: '◐', title: '품질 평가',
    desc: '모든 에이전트의 닮음·다양성 품질 통계와 분포도를 봅니다.', sub: (id: string) => `/projects/${id}/quality` },
  { key: 'agents', tour: 'card-agents', icon: '👥', title: 'AI 소비자',
    desc: '필터로 AI 소비자를 골라 저장하면 1:1 채팅·FGI에 등장합니다.', sub: (id: string) => `/projects/${id}/agents` },
  { key: 'chat', tour: 'card-chat', icon: '💬', title: '1:1 채팅',
    desc: '저장한 AI 소비자와 메신저처럼 1:1로 대화합니다.', sub: (id: string) => `/projects/${id}/chat` },
  { key: 'fgi', tour: 'card-fgi', icon: '🗣', title: 'FGI 토론',
    desc: '저장한 AI 소비자들이 모더레이터 진행으로 다자 토론을 합니다.', sub: (id: string) => `/projects/${id}/fgi` },
];

export default function ProjectDetailPage() {
  return (
    <AuthGuard>
      <AppShell>
        <ProjectDetailView />
      </AppShell>
    </AuthGuard>
  );
}

function ProjectDetailView() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { token } = useAuth();
  const { setProjectId } = useProjectContext();
  const projectId = params?.id;

  const [project, setProject] = useState<ResearchProject | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [editing, setEditing] = useState(false);
  const [titleDraft, setTitleDraft] = useState('');
  const [statusDraft, setStatusDraft] = useState<ResearchProject['status']>('draft');
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (projectId) setProjectId(projectId);
  }, [projectId, setProjectId]);

  const reload = useCallback(async () => {
    if (!token || !projectId) return;
    setLoading(true);
    setError(null);
    try {
      const p = await projectsApi.get(token, projectId);
      setProject(p);
      setTitleDraft(p.title || '');
      setStatusDraft(p.status);
    } catch (e) {
      setError(e instanceof Error ? e.message : '불러오기 실패');
    } finally {
      setLoading(false);
    }
  }, [token, projectId]);

  useEffect(() => { reload(); }, [reload]);

  const onSave = useCallback(async () => {
    if (!token || !projectId || saving) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await projectsApi.update(token, projectId, {
        title: titleDraft.trim() || undefined,
        status: statusDraft,
      });
      setProject(updated);
      setEditing(false);
      setConfirmDelete(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : '저장 실패');
    } finally {
      setSaving(false);
    }
  }, [token, projectId, saving, titleDraft, statusDraft]);

  const onDelete = useCallback(async () => {
    if (!token || !projectId || deleting) return;
    setDeleting(true);
    setError(null);
    try {
      await projectsApi.remove(token, projectId);
      router.push('/projects');
    } catch (e) {
      setError(e instanceof Error ? e.message : '삭제 실패');
      setDeleting(false);
    }
  }, [token, projectId, deleting, router]);

  if (loading) {
    return <PageContainer><LoadingState /></PageContainer>;
  }

  if (!project) {
    return (
      <PageContainer>
        <Card padding="lg">
          <p className="text-sm text-error mb-3">{error || '프로젝트를 찾을 수 없습니다.'}</p>
          <Link href="/projects" className="text-sm text-ditto-indigo hover:underline">← 프로젝트 목록으로</Link>
        </Card>
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <div className="mb-6">
        <Link href="/projects" className="text-xs text-text-muted hover:text-ditto-indigo">← 프로젝트 목록</Link>
      </div>

      {/* 헤더 — 편집 모드 안에 삭제까지 편입 */}
      <Card padding="md" className="mb-6">
        {editing ? (
          <div className="space-y-3">
            <Input
              label="프로젝트 제목"
              name="title"
              value={titleDraft}
              onChange={e => setTitleDraft(e.target.value)}
              maxLength={200}
            />
            <Select
              label="상태"
              name="status"
              options={STATUS_OPTIONS}
              value={statusDraft}
              onChange={e => setStatusDraft(e.target.value as ResearchProject['status'])}
            />
            <div className="flex items-center gap-2 pt-1">
              <Button onClick={onSave} loading={saving}>저장</Button>
              <Button variant="ghost" onClick={() => { setEditing(false); setConfirmDelete(false); setTitleDraft(project.title || ''); setStatusDraft(project.status); }}>
                취소
              </Button>
              {error && <span className="text-xs text-error">{error}</span>}
            </div>

            {/* 삭제 — 편집 모드 하단으로 편입 */}
            <div className="mt-2 border-t border-border pt-3">
              <p className="mb-2 text-2xs text-text-muted">
                삭제하면 에이전트·메모리·평가까지 모두 사라집니다 (복구 불가).
              </p>
              {confirmDelete ? (
                <div className="flex items-center gap-2">
                  <Button variant="danger" size="sm" onClick={onDelete} loading={deleting}>정말 삭제</Button>
                  <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(false)} disabled={deleting}>취소</Button>
                </div>
              ) : (
                <button
                  onClick={() => setConfirmDelete(true)}
                  className="text-xs font-medium text-error hover:underline"
                >
                  프로젝트 삭제
                </button>
              )}
            </div>
          </div>
        ) : (
          <div>
            <CardHeader
              title={project.title || '(제목 없음)'}
              subtitle={`상태: ${project.status} · 에이전트 ${project.agent_count}명`}
              action={<Button size="sm" variant="secondary" onClick={() => setEditing(true)}>편집</Button>}
            />
            {error && <p className="text-xs text-error">{error}</p>}
          </div>
        )}
      </Card>

      {/* 큰 카드 — 사이드바 세부 탭으로 이동 */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {NAV_CARDS.map((c) => (
          <Link
            key={c.key}
            href={c.sub(project.id)}
            data-tour={c.tour}
            className="group block rounded-2xl focus:outline-none focus:ring-2 focus:ring-ditto-indigo"
          >
            <Card padding="lg" className="h-full transition-colors group-hover:border-ditto-indigo">
              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-ditto-indigo-light text-2xl text-ditto-indigo">
                {c.icon}
              </div>
              <h3 className="mb-1 text-lg font-bold text-text-primary">{c.title}</h3>
              <p className="text-sm text-text-secondary">{c.desc}</p>
              <span className="mt-4 inline-block text-sm font-semibold text-ditto-indigo group-hover:underline">
                바로가기 →
              </span>
            </Card>
          </Link>
        ))}
      </div>
    </PageContainer>
  );
}
