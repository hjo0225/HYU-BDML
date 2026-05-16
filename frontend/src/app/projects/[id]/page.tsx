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
import { V3Scatter } from '@/components/dashboard/V3Scatter';
import { useAuth } from '@/contexts/AuthContext';
import { useProjectContext } from '@/contexts/ProjectContext';
import { evaluations as evalApi, projects as projectsApi } from '@/lib/api';
import type { ResearchProject, ScatterResponse } from '@/lib/types';

const STATUS_OPTIONS = [
  { value: 'draft', label: '준비 중 (draft)' },
  { value: 'active', label: '진행 중 (active)' },
  { value: 'archived', label: '보관 (archived)' },
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
  const [scatter, setScatter] = useState<ScatterResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [titleDraft, setTitleDraft] = useState('');
  const [statusDraft, setStatusDraft] = useState<ResearchProject['status']>('draft');
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // 진입 시 ProjectContext 동기화 (다른 프로젝트면 선택 초기화됨)
  useEffect(() => {
    if (projectId) setProjectId(projectId);
  }, [projectId, setProjectId]);

  const reload = useCallback(async () => {
    if (!token || !projectId) return;
    setLoading(true);
    setError(null);
    try {
      const [p, sc] = await Promise.all([
        projectsApi.get(token, projectId),
        evalApi.scatter(token, projectId).catch(() => null),
      ]);
      setProject(p);
      setScatter(sc);
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
    return (
      <div className="p-8 max-w-5xl mx-auto">
        <p className="text-sm text-text-muted">불러오는 중…</p>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="p-8 max-w-5xl mx-auto">
        <Card padding="lg">
          <p className="text-sm text-error mb-3">{error || '프로젝트를 찾을 수 없습니다.'}</p>
          <Link href="/projects" className="text-sm text-ditto-indigo hover:underline">← 프로젝트 목록으로</Link>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-6">
        <Link href="/projects" className="text-xs text-text-muted hover:text-ditto-indigo">← 프로젝트 목록</Link>
      </div>

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
              <Button variant="ghost" onClick={() => { setEditing(false); setTitleDraft(project.title || ''); setStatusDraft(project.status); }}>
                취소
              </Button>
              {error && <span className="text-xs text-error">{error}</span>}
            </div>
          </div>
        ) : (
          <div>
            <CardHeader
              title={project.title || '(제목 없음)'}
              subtitle={`상태: ${project.status} · 에이전트 ${project.agent_count}명`}
              action={
                <Button size="sm" variant="secondary" onClick={() => setEditing(true)}>편집</Button>
              }
            />
            {error && <p className="text-xs text-error">{error}</p>}
          </div>
        )}
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <Card padding="md">
          <CardHeader title="에이전트 카탈로그" subtitle="Twin-2K-500 기반 30명 + 6-Lens 필터" />
          <p className="text-sm text-text-muted mb-4">
            프로젝트에 사용할 에이전트를 선택합니다. 다음 단계로 N명이 전달됩니다.
          </p>
          <Link href={`/projects/${project.id}/agents`}>
            <Button variant="primary" size="md">에이전트 보기 →</Button>
          </Link>
        </Card>

        <Card padding="md">
          <CardHeader title="평가 (V1·V3)" subtitle="에이전트 상세에서 실행 — 같은 프로젝트 전체가 함께 평가됩니다" />
          <p className="text-sm text-text-muted mb-4">
            V1 응답 동기화율 · V3 페르소나 독립성. 결과는 본 페이지의 산점도와
            각 에이전트 상세의 시계열에 누적됩니다.
          </p>
          <Link href={`/projects/${project.id}/agents`}>
            <Button variant="secondary" size="md">에이전트 상세에서 실행 →</Button>
          </Link>
        </Card>
      </div>

      {(scatter && scatter.n_points > 0) ? (
        <Card padding="md" className="mb-6">
          <V3Scatter
            points={scatter.points}
            distinct={scatter.distinct}
            height={360}
          />
        </Card>
      ) : (
        <Card padding="md" className="mb-6 border-dashed">
          <p className="text-sm text-text-muted">
            V3 페르소나 독립성 산점도는 평가를 1회 이상 실행하면 표시됩니다.
            에이전트 카탈로그 → 에이전트 상세 → &quot;V1·V3 실행&quot;.
          </p>
        </Card>
      )}

      <Card padding="md" className="border-error/30">
        <CardHeader title="위험 영역" subtitle="삭제하면 에이전트·메모리·평가까지 모두 사라집니다 (복구 불가)" />
        {confirmDelete ? (
          <div className="flex items-center gap-2">
            <Button variant="danger" onClick={onDelete} loading={deleting}>
              정말 삭제
            </Button>
            <Button variant="ghost" onClick={() => setConfirmDelete(false)} disabled={deleting}>
              취소
            </Button>
          </div>
        ) : (
          <Button variant="secondary" onClick={() => setConfirmDelete(true)} className="text-error border-error/40">
            프로젝트 삭제
          </Button>
        )}
      </Card>
    </div>
  );
}
