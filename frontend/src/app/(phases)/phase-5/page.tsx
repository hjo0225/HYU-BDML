'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useProject } from '@/contexts/ProjectContext';
import { fetchMinutes } from '@/lib/api';

export default function Phase5Page() {
  const router = useRouter();
  const { project, setMinutes, setCurrentPhase } = useProject();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const hasMinutes = !!project.minutes;

  /* 회의록 생성 요청 */
  const generateMinutes = useCallback(async () => {
    if (!project.brief || !project.agents.length || !project.messages.length) {
      setError('회의 데이터가 부족합니다. 이전 단계를 먼저 완료해주세요.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await fetchMinutes({
        messages: project.messages,
        brief: project.brief,
        agents: project.agents,
      });
      setMinutes(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : '회의록 생성 중 오류 발생');
    } finally {
      setLoading(false);
    }
  }, [project.brief, project.agents, project.messages, setMinutes]);

  /* 클립보드 복사 */
  const copyToClipboard = async () => {
    if (!project.minutes) return;
    try {
      await navigator.clipboard.writeText(project.minutes);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setError('클립보드 복사에 실패했습니다.');
    }
  };

  /* Markdown 다운로드 */
  const downloadMarkdown = () => {
    if (!project.minutes) return;
    const blob = new Blob([project.minutes], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = '회의록.md';
    a.click();
    URL.revokeObjectURL(url);
  };

  /* Markdown → HTML 간이 변환 */
  const renderMarkdown = (md: string) => {
    let html = md
      // 테이블
      .replace(/^\|(.+)\|$/gm, (match) => {
        const cells = match.split('|').filter(Boolean).map((c) => c.trim());
        // 구분선 (---) 행 무시
        if (cells.every((c) => /^[-:]+$/.test(c))) return '';
        const tag = 'td';
        return `<tr>${cells.map((c) => `<${tag}>${c}</${tag}>`).join('')}</tr>`;
      })
      // 테이블 래핑
      .replace(/((?:<tr>.*<\/tr>\n?)+)/g, '<table class="minutes-table">$1</table>')
      // 헤더
      .replace(/^### (.+)$/gm, '<h3 class="minutes-h3">$1</h3>')
      .replace(/^## (.+)$/gm, '<h2 class="minutes-h2">$1</h2>')
      .replace(/^# (.+)$/gm, '<h1 class="minutes-h1">$1</h1>')
      // 인용구
      .replace(/^> (.+)$/gm, '<blockquote class="finding-quote">$1</blockquote>')
      // 볼드
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      // 이탤릭
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      // 리스트
      .replace(/^- (.+)$/gm, '<li>$1</li>')
      .replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>')
      // 수평선
      .replace(/^---$/gm, '<hr/>')
      // 줄바꿈
      .replace(/\n\n/g, '<br/><br/>')
      .replace(/\n/g, '<br/>');
    return html;
  };

  /* 네비게이션 */
  const goPrev = () => {
    setCurrentPhase(4);
    router.push('/phase-4');
  };

  /* 데이터 없으면 Phase 4로 안내 */
  if (!project.messages.length && !hasMinutes) {
    return (
      <div className="card">
        <div className="card-header">
          <div className="card-title">📝 회의록 · 내보내기</div>
        </div>
        <p className="text-sm text-text-secondary mb-4">
          회의가 아직 진행되지 않았습니다. Phase 4에서 먼저 회의를 진행해주세요.
        </p>
        <button className="btn btn-primary" onClick={goPrev}>
          ← 회의 시뮬레이션으로
        </button>
      </div>
    );
  }

  return (
    <div>
      {/* 생성 전 / 로딩 */}
      {!hasMinutes && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              📝 회의록 · 내보내기
              {loading && <span className="badge badge-ai">AI 생성 중</span>}
            </div>
          </div>

          {loading ? (
            <div className="spinner-wrap">
              <div className="spinner" />
              <div className="spinner-text">AI가 회의 내용을 분석하여 회의록을 작성하고 있습니다...</div>
            </div>
          ) : (
            <>
              <p className="text-xs text-text-secondary mb-4">
                {project.messages.length}개의 발언을 분석하여 구조화된 회의록을 생성합니다.
              </p>
              {error && (
                <div className="mb-3 p-2.5 rounded-md text-xs" style={{ background: '#fdecea', color: 'var(--red)' }}>
                  {error}
                </div>
              )}
              <button className="btn btn-primary" onClick={generateMinutes}>
                회의록 생성 →
              </button>
            </>
          )}
        </div>
      )}

      {/* 회의록 표시 */}
      {hasMinutes && (
        <>
          <div className="minutes-content" style={{ marginBottom: 16 }}>
            {/* 헤더 */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
              <div>
                <div className="card-title" style={{ fontSize: 16, marginBottom: 4 }}>
                  📝 회의록
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  AI 생성 · 발언 {project.messages.length}개 분석
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn btn-ghost text-[11px]" onClick={generateMinutes} disabled={loading}>
                  🔄 재생성
                </button>
              </div>
            </div>

            {/* Markdown 렌더링 */}
            <div
              className="minutes-body"
              dangerouslySetInnerHTML={{ __html: renderMarkdown(project.minutes!) }}
            />

            {/* 디스클레이머 */}
            <div className="disclaimer">
              ⚠️
              <span>
                본 보고서는 AI 에이전트 시뮬레이션 결과이며, 실제 사용자 대상 정성조사를 대체하지 않습니다.
                가설 수립 및 방향성 검증 용도로 활용하시기 바랍니다.
              </span>
            </div>

            {/* 내보내기 바 */}
            <div className="export-bar">
              <button className="export-btn" onClick={downloadMarkdown}>
                📋 Markdown 다운로드
              </button>
              <button className="export-btn" onClick={copyToClipboard}>
                {copied ? '✅ 복사됨!' : '📎 클립보드 복사'}
              </button>
              <div style={{ flex: 1 }} />
            </div>
          </div>

          {/* 액션 바 */}
          <div className="action-bar">
            <button className="btn btn-secondary" onClick={goPrev}>
              ← 회의 다시보기
            </button>
          </div>
        </>
      )}
    </div>
  );
}
