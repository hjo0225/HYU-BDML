'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useProject } from '@/contexts/ProjectContext';
import { fetchMinutes } from '@/lib/api';

const escapeHtml = (text: string) =>
  text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

export default function Phase5Page() {
  const router = useRouter();
  const { project, setMinutes, setCurrentPhase, resetProject } = useProject();

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
        topic: project.meetingTopic ?? undefined,
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

  /* 인라인 마크다운 처리 (볼드·이탤릭) */
  const processInline = (text: string) =>
    escapeHtml(text)
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>');

  const renderBlock = (block: string): string => {
    const t = block.trim();
    if (!t) return '';
    if (/^-{3,}$/.test(t)) return '<hr class="minutes-hr"/>';

    const lines = t.split('\n');

    if (t.startsWith('### ')) {
      const title = processInline(lines[0].slice(4));
      const body = lines.slice(1).join('\n').trim();
      return (
        `<div class="minutes-subsection">` +
          `<div class="minutes-subsection-title">${title}</div>` +
          (body ? `<div class="minutes-subsection-body">${renderBlocks(body)}</div>` : '') +
        `</div>`
      );
    }
    if (t.startsWith('# ')) {
      return `<h1 class="minutes-h1">${processInline(t.slice(2))}</h1>`;
    }
    if (t.startsWith('> ')) {
      return `<blockquote class="finding-quote">${processInline(t.slice(2))}</blockquote>`;
    }

    if (lines.some((l) => l.trim().startsWith('|'))) {
      const rows = lines
        .filter((l) => l.trim().startsWith('|'))
        .filter((l) => !/^\|[\s:|-]+\|$/.test(l.trim()));
      if (rows.length > 0) {
        const trs = rows
          .map((row, idx) => {
            const cells = row.split('|').filter(Boolean).map((c) => c.trim());
            const tag = idx === 0 ? 'th' : 'td';
            return `<tr>${cells.map((c) => `<${tag}>${processInline(c)}</${tag}>`).join('')}</tr>`;
          })
          .join('');
        return `<div class="minutes-block"><table class="minutes-table">${trs}</table></div>`;
      }
    }

    const olLines = lines.filter((l) => l.trim());
    if (olLines.length > 0 && olLines.every((l) => /^\d+\.\s/.test(l.trim()))) {
      const items = olLines.map((l) => `<li>${processInline(l.trim().replace(/^\d+\.\s/, ''))}</li>`).join('');
      return `<div class="minutes-block"><ol>${items}</ol></div>`;
    }

    const listLines = lines.filter((l) => l.trim());
    if (listLines.length > 0 && listLines.every((l) => l.trim().startsWith('- '))) {
      const items = listLines.map((l) => `<li>${processInline(l.trim().slice(2))}</li>`).join('');
      return `<div class="minutes-block"><ul>${items}</ul></div>`;
    }

    return `<div class="minutes-block"><p class="minutes-p">${lines.map((l) => processInline(l)).join('<br/>')}</p></div>`;
  };

  /* 블록 단위 마크다운 → HTML 변환 */
  const renderBlocks = (md: string): string => {
    const normalizedMd = md.replace(/\n\s*---\s*\n/g, '\n\n---\n\n');
    const blocks = normalizedMd.split(/\n{2,}/);
    return blocks
      .map(renderBlock)
      .filter(Boolean)
      .join('');
  };

  const renderMainContent = (md: string): string => {
    const normalized = md.trim();
    if (!normalized) return '';

    const sectionMatches: Array<{ index: number; title: string; raw: string }> = [];
    const sectionRegex = /^##\s+(.+)$/gm;
    let match: RegExpExecArray | null;
    while ((match = sectionRegex.exec(normalized)) !== null) {
      sectionMatches.push({
        index: match.index,
        title: match[1],
        raw: match[0],
      });
    }
    if (sectionMatches.length === 0) {
      return `<div class="minutes-section"><div class="minutes-section-body">${renderBlocks(normalized)}</div></div>`;
    }

    const htmlParts: string[] = [];
    const firstSectionIndex = sectionMatches[0].index;
    const lead = normalized.slice(0, firstSectionIndex).trim();

    if (lead) {
      htmlParts.push(
        `<div class="minutes-section minutes-section-lead">` +
          `<div class="minutes-section-body">${renderBlocks(lead)}</div>` +
        `</div>`,
      );
    }

    sectionMatches.forEach((match, index) => {
      const title = processInline(match.title);
      const start = match.index + match.raw.length;
      const end = index + 1 < sectionMatches.length ? sectionMatches[index + 1].index : normalized.length;
      const body = normalized.slice(start, end).trim();

      htmlParts.push(
        `<section class="minutes-section">` +
          `<div class="minutes-section-header">` +
            `<h2 class="minutes-h2">${title}</h2>` +
          `</div>` +
          `<div class="minutes-section-body">${renderBlocks(body)}</div>` +
        `</section>`,
      );
    });

    return htmlParts.join('');
  };

  /* Markdown → HTML 변환 (부록 분리 처리) */
  const renderMarkdown = (md: string): string => {
    // 부록 구분선 위치 탐색
    const sepIdx = md.search(/\n{1,2}---\n{1,2}(?=## 부록)/);
    const mainMd = sepIdx >= 0 ? md.slice(0, sepIdx) : md;
    const appendixMd = sepIdx >= 0 ? md.slice(sepIdx).replace(/^-+\n+/, '') : null;

    let html = renderMainContent(mainMd);

    if (appendixMd) {
      // 첫 ## 부록 줄을 summary 텍스트로 사용
      const firstLine = appendixMd.split('\n')[0].replace(/^##\s*/, '');
      const bodyMd = appendixMd.replace(/^##[^\n]*\n/, '');
      html +=
        `<details class="minutes-appendix">` +
        `<summary class="minutes-appendix-summary">📎 회의록 원본</summary>` +
        `<div class="minutes-appendix-body">${renderBlocks(bodyMd)}</div>` +
        `</details>`;
    }

    return html;
  };

  /* 네비게이션 */
  const goPrev = () => {
    setCurrentPhase(4);
    router.push('/meeting');
  };

  const startNewProject = () => {
    resetProject();
    router.push('/research-input');
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
                  <div>{error}</div>
                  <button className="btn btn-ghost text-[11px] mt-1" style={{ color: 'var(--red)' }} onClick={generateMinutes}>
                    다시 시도
                  </button>
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
                  📝 {project.meetingTopic || '회의록'}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  AI 생성 · 발언 {project.messages.length}개 분석
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <button className="btn btn-ghost text-[11px]" onClick={downloadMarkdown}>
                  📋 다운로드
                </button>
                <button className="btn btn-ghost text-[11px]" onClick={copyToClipboard}>
                  {copied ? '✅ 복사됨!' : '📎 복사'}
                </button>
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
          </div>

          {/* 액션 바 */}
          <div className="action-bar">
            <button className="btn btn-secondary" onClick={goPrev}>
              ← 회의 다시보기
            </button>
            <button className="btn btn-ghost" onClick={startNewProject}>
              🔄 새 프로젝트 시작
            </button>
          </div>
        </>
      )}
    </div>
  );
}
