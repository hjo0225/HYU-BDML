'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { useProject } from '@/contexts/ProjectContext';
import { listProjects, deleteProject, type ProjectSummary } from '@/lib/api';

const PHASE_LABELS: Record<number, string> = {
  1: '브리프 입력',
  2: '시장조사',
  3: '에이전트 설정',
  4: '회의 진행',
  5: '회의록 완료',
};

const PHASE_PATHS: Record<number, string> = {
  1: '/research-input',
  2: '/market-research',
  3: '/agent-setup',
  4: '/meeting',
  5: '/minutes',
};

export default function ProjectListPage() {
  const { user, logout } = useAuth();
  const { resetProject, loadProjectFromBackend } = useProject();
  const router = useRouter();
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const loadProjects = useCallback(async () => {
    try {
      const data = await listProjects();
      setProjects(data);
    } catch {
      // 인증 오류 시 AuthGuard가 처리
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) loadProjects();
  }, [user, loadProjects]);

  const handleNewProject = () => {
    // 새 프로젝트: 상태 초기화 후 브리프 입력으로
    resetProject();
    router.push('/research-input');
  };

  const handleOpenProject = async (project: ProjectSummary) => {
    // 백엔드에서 프로젝트 전체 데이터 로드 → ProjectContext에 복원
    await loadProjectFromBackend(project.id);
    const path = PHASE_PATHS[project.current_phase] ?? '/research-input';
    router.push(path);
  };

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!confirm('이 프로젝트를 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.')) return;
    setDeletingId(id);
    try {
      await deleteProject(id);
      setProjects((prev) => prev.filter((p) => p.id !== id));
    } catch {
      alert('삭제에 실패했습니다.');
    } finally {
      setDeletingId(null);
    }
  };

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString('ko-KR', { month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="project-list-page">
      {/* 헤더 */}
      <header className="project-list-header">
        <div className="project-list-header__inner">
          <div className="project-list-header__brand">
            <span className="project-list-header__logo">HY</span>
            <h1 className="project-list-header__title">AI 정성조사 시뮬레이션</h1>
          </div>
          <div className="project-list-header__user">
            <span className="project-list-header__email">{user?.email}</span>
            <button
              id="logout-btn"
              className="project-list-header__logout"
              onClick={logout}
            >
              로그아웃
            </button>
          </div>
        </div>
      </header>

      <main className="project-list-main">
        <div className="project-list-toolbar">
          <div>
            <h2 className="project-list-toolbar__heading">내 연구 프로젝트</h2>
            <p className="project-list-toolbar__sub">
              {isLoading ? '불러오는 중...' : `총 ${projects.length}개의 프로젝트`}
            </p>
          </div>
          <button
            id="new-project-btn"
            className="project-list-toolbar__new-btn"
            onClick={handleNewProject}
          >
            + 새 연구 시작
          </button>
        </div>

        {/* 프로젝트 목록 */}
        {isLoading ? (
          <div className="project-list-empty">
            <div className="project-list-empty__spinner" />
          </div>
        ) : projects.length === 0 ? (
          <div className="project-list-empty">
            <div className="project-list-empty__icon">📋</div>
            <p className="project-list-empty__text">아직 진행한 연구가 없습니다</p>
            <button className="project-list-toolbar__new-btn" onClick={handleNewProject}>
              첫 번째 연구 시작하기
            </button>
          </div>
        ) : (
          <div className="project-list-grid">
            {projects.map((project) => (
              <div
                key={project.id}
                id={`project-card-${project.id}`}
                className="project-card"
                onClick={() => handleOpenProject(project)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === 'Enter' && handleOpenProject(project)}
              >
                <div className="project-card__header">
                  <span className="project-card__icon">📋</span>
                  <div
                    className={`project-card__badge project-card__badge--phase${project.current_phase}`}
                  >
                    {project.status === 'completed' ? '완료' : PHASE_LABELS[project.current_phase]}
                  </div>
                </div>
                <h3 className="project-card__title">{project.title || '제목 없음'}</h3>
                {project.brief_summary && (
                  <p className="project-card__summary">{project.brief_summary}</p>
                )}
                <div className="project-card__footer">
                  <span className="project-card__date">
                    {formatDate(project.updated_at)}
                  </span>
                  <button
                    className="project-card__delete"
                    onClick={(e) => handleDelete(e, project.id)}
                    disabled={deletingId === project.id}
                    aria-label="프로젝트 삭제"
                  >
                    {deletingId === project.id ? '삭제 중...' : '삭제'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
