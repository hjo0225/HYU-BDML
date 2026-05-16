'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { AuthGuard } from '@/components/auth/AuthGuard';
import { AppShell } from '@/components/layout/AppShell';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { useAuth } from '@/contexts/AuthContext';
import { projects as projectsApi } from '@/lib/api';
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

const STATUS_TONE: Record<ResearchProject['status'], string> = {
  draft: 'bg-bg text-text-muted border-border',
  active: 'bg-ditto-indigo-light text-ditto-indigo border-ditto-indigo/30',
  archived: 'bg-bg text-text-muted border-border opacity-70',
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
  const { token } = useAuth();
  const [list, setList] = useState<ResearchProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [newTitle, setNewTitle] = useState('');
  const [creating, setCreating] = useState(false);

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

  const onCreate = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || creating) return;
    setCreating(true);
    setError(null);
    try {
      const trimmed = newTitle.trim();
      await projectsApi.create(token, trimmed ? { title: trimmed } : {});
      setNewTitle('');
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : '생성 실패');
    } finally {
      setCreating(false);
    }
  }, [token, creating, newTitle, reload]);

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-8 flex items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">리서치 프로젝트</h1>
          <p className="text-sm text-text-muted mt-1">
            프로젝트를 만들고 Twin-2K-500 기반 에이전트를 선택해 평가·FGI 를 진행합니다.
          </p>
        </div>
      </div>

      <Card padding="md" className="mb-6">
        <CardHeader title="새 프로젝트" subtitle="비워두면 오늘 날짜로 자동 생성" />
        <form onSubmit={onCreate} className="flex items-end gap-3">
          <div className="flex-1">
            <Input
              name="title"
              placeholder="예: 신규 단백질 음료 컨셉 테스트"
              value={newTitle}
              onChange={e => setNewTitle(e.target.value)}
              disabled={creating}
              maxLength={200}
            />
          </div>
          <Button type="submit" loading={creating} disabled={!token}>
            만들기
          </Button>
        </form>
      </Card>

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
          {loading ? '불러오는 중…' : `${list.length}개`}
        </span>
        {error && <span className="text-xs text-error">· {error}</span>}
      </div>

      {!loading && list.length === 0 && (
        <Card padding="lg" className="text-center">
          <p className="text-sm text-text-muted">
            아직 프로젝트가 없습니다. 위 입력창에서 첫 프로젝트를 만들어보세요.
          </p>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {list.map(p => (
          <Link key={p.id} href={`/projects/${p.id}`} className="block focus:outline-none focus:ring-2 focus:ring-ditto-indigo rounded-xl">
            <Card padding="md" className="hover:border-ditto-indigo/40 transition-colors h-full">
              <div className="flex items-start justify-between gap-3 mb-3">
                <h3 className="text-base font-bold text-text-primary truncate flex-1">
                  {p.title || '(제목 없음)'}
                </h3>
                <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border shrink-0 ${STATUS_TONE[p.status]}`}>
                  {STATUS_LABEL[p.status]}
                </span>
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
    </div>
  );
}
