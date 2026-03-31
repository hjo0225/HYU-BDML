'use client';

import { useState, useCallback, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useProject } from '@/contexts/ProjectContext';
import { fetchRefinedResearch, fetchMarketReportFromRefined } from '@/lib/api';
import type { RefinedResearch, ReportSource } from '@/lib/types';

const REFINING_STEPS = [
  '연구 정보 분석 중...',
  '입력 맥락 정리 중...',
  '핵심 목적 정제 중...',
] as const;

const REPORT_STEPS = [
  '시장 현황 수집 중...',
  '경쟁 환경 파악 중...',
  '인사이트 도출 중...',
  '보고서 정리 중...',
] as const;

const REPORT_SECTIONS = [
  { key: 'market_overview', icon: '📈', title: '시장 개요' },
  { key: 'competitive_landscape', icon: '🏢', title: '경쟁 환경' },
  { key: 'target_analysis', icon: '👥', title: '타깃 고객 분석' },
  { key: 'trends', icon: '🔮', title: '관련 트렌드' },
  { key: 'implications', icon: '💡', title: '시사점' },
] as const;

const REFINED_FIELDS = [
  { key: 'refined_background', label: '연구 배경 / 맥락', originalKey: 'background' },
  { key: 'refined_objective', label: '연구 목적 / 목표', originalKey: 'objective' },
  { key: 'refined_usage_plan', label: '연구결과 활용방안', originalKey: 'usage_plan' },
] as const;

function renderSourceMeta(source: ReportSource): string {
  return [source.publisher, source.published_at, source.note].filter(Boolean).join(' · ');
}

export default function Phase2Page() {
  const router = useRouter();
  const { project, setRefined, setMarketReport, setAgents, setMeetingTopic, setMessages, setMinutes, setCurrentPhase } = useProject();

  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState<'idle' | 'refining' | 'refined' | 'reporting' | 'done'>(() => {
    if (project.refined && project.marketReport) return 'done';
    if (project.refined) return 'refined';
    return 'idle';
  });
  const [error, setError] = useState<string | null>(null);
  const [stepIndex, setStepIndex] = useState(0);
  const [editing, setEditing] = useState(false);
  const [editData, setEditData] = useState<RefinedResearch | null>(project.refined ?? null);

  useEffect(() => {
    if (!loading) {
      setStepIndex(0);
      return;
    }
    const totalSteps = stage === 'refining' ? REFINING_STEPS.length : REPORT_STEPS.length;
    const id = setInterval(() => {
      setStepIndex((prev) => Math.min(prev + 1, totalSteps - 1));
    }, 8000);
    return () => clearInterval(id);
  }, [loading, stage]);

  const clearDownstream = useCallback(() => {
    setMarketReport(null);
    setAgents([]);
    setMeetingTopic(null);
    setMessages([]);
    setMinutes(null);
  }, [setAgents, setMarketReport, setMeetingTopic, setMessages, setMinutes]);

  const startRefining = useCallback(async () => {
    if (!project.brief) {
      setError('연구 정보가 없습니다. Phase 1에서 입력해주세요.');
      return;
    }
    if (loading) return;

    setLoading(true);
    setError(null);
    setStage('refining');
    setEditing(false);
    clearDownstream();

    try {
      const refined = await fetchRefinedResearch(project.brief);
      setRefined(refined);
      setEditData(refined);
      setStage('refined');
    } catch (err) {
      setStage('idle');
      setError(err instanceof Error ? err.message : '연구 정보 정제 중 오류 발생');
    } finally {
      setLoading(false);
    }
  }, [clearDownstream, loading, project.brief, setRefined]);

  const generateReport = useCallback(async () => {
    if (!project.brief || !project.refined) {
      setError('정제된 연구 정보가 없습니다. 먼저 정제를 완료해주세요.');
      return;
    }
    if (loading) return;

    const refinedInput = editing ? editData : project.refined;
    if (!refinedInput) {
      setError('시장조사 입력용 정제본이 없습니다.');
      return;
    }

    setLoading(true);
    setError(null);
    setStage('reporting');

    try {
      if (editing) {
        setRefined(refinedInput);
        setEditing(false);
      }
      const report = await fetchMarketReportFromRefined(project.brief, refinedInput);
      setMarketReport(report);
      setAgents([]);
      setMeetingTopic(null);
      setMessages([]);
      setMinutes(null);
      setStage('done');
    } catch (err) {
      setStage('refined');
      setError(err instanceof Error ? err.message : '시장조사 보고서 생성 중 오류 발생');
    } finally {
      setLoading(false);
    }
  }, [editData, editing, loading, project.brief, project.refined, setAgents, setMarketReport, setMeetingTopic, setMessages, setMinutes, setRefined]);

  const toggleEdit = () => {
    if (!editing && project.refined) {
      setEditData({ ...project.refined });
    }
    setEditing((prev) => !prev);
  };

  const saveEdit = () => {
    if (editData) {
      setRefined(editData);
      clearDownstream();
      setStage('refined');
    }
    setEditing(false);
  };

  const goNext = () => {
    setCurrentPhase(3);
    router.push('/phase-3');
  };

  const goPrev = () => {
    setCurrentPhase(1);
    router.push('/phase-1');
  };

  if (!project.brief && stage !== 'done') {
    return (
      <div className="card">
        <div className="card-header">
          <div className="card-title">🔍 시장조사 · 딥리서치</div>
        </div>
        <p className="text-sm text-text-secondary mb-4">
          연구 정보가 입력되지 않았습니다. Phase 1에서 먼저 입력해주세요.
        </p>
        <button className="btn btn-primary" onClick={goPrev}>
          ← 연구 정보 입력으로
        </button>
      </div>
    );
  }

  const loadingSteps = stage === 'refining' ? REFINING_STEPS : REPORT_STEPS;

  return (
    <div>
      {loading && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              🔍 시장조사 · 딥리서치
              <span className="badge badge-ai">AI 진행 중</span>
            </div>
          </div>
          <div className="progress-bar-wrap" style={{ marginBottom: 16 }}>
            <div
              className="progress-bar-fill"
              style={{ width: `${Math.round(((stepIndex + 1) / loadingSteps.length) * 100)}%`, transition: 'width 0.8s ease' }}
            />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {loadingSteps.map((label, i) => (
              <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 8, opacity: i > stepIndex ? 0.3 : 1, transition: 'opacity 0.4s' }}>
                <span style={{ fontSize: 12, color: i < stepIndex ? 'var(--green)' : i === stepIndex ? 'var(--accent)' : 'var(--text-muted)' }}>
                  {i < stepIndex ? '✓' : i === stepIndex ? '●' : '○'}
                </span>
                <span className="spinner-text" style={{ margin: 0 }}>{label}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {!loading && stage === 'idle' && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">🔍 시장조사 · 딥리서치</div>
          </div>
          <p className="text-xs text-text-secondary mb-4">
            먼저 연구 정보를 정제한 뒤, 정제된 입력을 기준으로 시장조사 보고서를 생성합니다.
          </p>
          {error && (
            <div className="mb-3 p-2.5 rounded-md text-xs" style={{ background: '#fdecea', color: 'var(--red)' }}>
              <div>{error}</div>
              <button className="btn btn-ghost text-[11px] mt-1" style={{ color: 'var(--red)' }} onClick={startRefining}>
                다시 시도
              </button>
            </div>
          )}
          <button className="btn btn-primary" onClick={startRefining}>
            연구 정보 정제 시작 →
          </button>
        </div>
      )}

      {!loading && stage === 'refined' && project.refined && (
        <>
          <div className="card">
            <div className="card-header" style={{ marginBottom: 0 }}>
              <div className="card-title">
                📝 연구 정보 정제
                <span className="badge" style={{ background: '#eef5ff', color: 'var(--accent)' }}>정제 완료</span>
              </div>
              <button className="btn btn-ghost text-[11px]" onClick={startRefining} disabled={loading}>
                🔄 다시 정제
              </button>
            </div>
          </div>

          <div className="two-col">
            <div>
              <div className="card">
                <div className="card-header">
                  <div className="card-title">
                    📝 시장조사 입력으로 사용할 정제본
                    <span className="badge badge-ai">AI 보강</span>
                  </div>
                </div>

                {REFINED_FIELDS.map(({ key, label, originalKey }) => (
                  <div key={key} className="mb-3.5">
                    <div className="field-label">{label}</div>
                    {editing ? (
                      <textarea
                        className="field-textarea"
                        value={editData?.[key] || ''}
                        onChange={(e) =>
                          setEditData((prev) =>
                            prev ? { ...prev, [key]: e.target.value } : prev,
                          )
                        }
                        rows={4}
                      />
                    ) : (
                      <>
                        {project.brief?.[originalKey] && (
                          <div className="diff-original text-xs leading-[1.8] mb-1">
                            {project.brief[originalKey]}
                          </div>
                        )}
                        <div className="diff-refined text-xs leading-[1.8]">
                          {project.refined![key]}
                        </div>
                      </>
                    )}
                  </div>
                ))}

                {error && (
                  <div className="mb-3 p-2.5 rounded-md text-xs" style={{ background: '#fdecea', color: 'var(--red)' }}>
                    <div>{error}</div>
                  </div>
                )}

                {editing ? (
                  <div className="flex gap-2">
                    <button className="btn btn-primary flex-1 justify-center" onClick={saveEdit}>
                      정제본 저장
                    </button>
                    <button className="btn btn-secondary flex-1 justify-center" onClick={toggleEdit}>
                      취소
                    </button>
                  </div>
                ) : (
                  <div className="flex gap-2">
                    <button className="btn btn-secondary flex-1 justify-center" onClick={toggleEdit}>
                      ✏️ 정제본 수정
                    </button>
                    <button className="btn btn-primary flex-1 justify-center" onClick={generateReport}>
                      시장조사 보고서 생성 →
                    </button>
                  </div>
                )}
              </div>
            </div>

            <div>
              <div className="card">
                <div className="card-header">
                  <div className="card-title">ℹ️ 현재 단계 안내</div>
                </div>
                <div className="text-xs text-text-secondary" style={{ lineHeight: 1.8 }}>
                  원본 Phase 1 입력을 먼저 정제했습니다.
                  <br />
                  이 정제본이 시장조사 보고서 생성의 직접 입력으로 사용됩니다.
                  <br />
                  필요하면 문장을 다듬은 뒤 보고서를 생성하세요.
                </div>
              </div>
            </div>
          </div>

          <div className="action-bar">
            <button className="btn btn-secondary" onClick={goPrev}>
              ← 연구 정보 수정
            </button>
          </div>
        </>
      )}

      {stage === 'done' && project.refined && project.marketReport && (
        <>
          <div className="card">
            <div className="card-header" style={{ marginBottom: 0 }}>
              <div className="card-title">
                🔍 시장조사 · 딥리서치
                <span className="badge" style={{ background: '#f0f7ee', color: 'var(--green)' }}>완료</span>
              </div>
              <button className="btn btn-ghost text-[11px]" onClick={generateReport} disabled={loading}>
                🔄 보고서 재생성
              </button>
            </div>
          </div>

          <div className="two-col">
            <div>
              <div className="card">
                <div className="card-header">
                  <div className="card-title">
                    📝 고도화된 연구 정보
                    <span className="badge badge-ai">시장조사 입력</span>
                  </div>
                </div>

                {REFINED_FIELDS.map(({ key, label, originalKey }) => (
                  <div key={key} className="mb-3.5">
                    <div className="field-label">{label}</div>
                    {editing ? (
                      <textarea
                        className="field-textarea"
                        value={editData?.[key] || ''}
                        onChange={(e) =>
                          setEditData((prev) =>
                            prev ? { ...prev, [key]: e.target.value } : prev,
                          )
                        }
                        rows={4}
                      />
                    ) : (
                      <>
                        {project.brief?.[originalKey] && (
                          <div className="diff-original text-xs leading-[1.8] mb-1">
                            {project.brief[originalKey]}
                          </div>
                        )}
                        <div className="diff-refined text-xs leading-[1.8]">
                          {project.refined![key]}
                        </div>
                      </>
                    )}
                  </div>
                ))}

                {editing ? (
                  <div className="flex gap-2">
                    <button className="btn btn-primary flex-1 justify-center" onClick={saveEdit}>
                      저장
                    </button>
                    <button className="btn btn-secondary flex-1 justify-center" onClick={toggleEdit}>
                      취소
                    </button>
                  </div>
                ) : (
                  <div className="flex gap-2">
                    <button className="btn btn-secondary flex-1 justify-center" onClick={toggleEdit}>
                      ✏️ 정제본 수정하기
                    </button>
                    <button className="btn btn-primary flex-1 justify-center" onClick={generateReport}>
                      보고서 다시 생성
                    </button>
                  </div>
                )}
              </div>
            </div>

            <div>
              <div className="card">
                <div className="card-header">
                  <div className="card-title">📊 시장조사 보고서</div>
                  <button className="btn btn-ghost text-[11px]" onClick={generateReport} disabled={loading}>
                    🔄 보고서 재생성
                  </button>
                </div>

                {error && (
                  <div className="mb-3 p-2.5 rounded-md text-xs" style={{ background: '#fdecea', color: 'var(--red)' }}>
                    <div>{error}</div>
                  </div>
                )}

                {REPORT_SECTIONS.map(({ key, icon, title }) => {
                  const section = project.marketReport![key];
                  return (
                    <div key={key} className="report-section">
                      <div className="report-section-title">{icon} {title}</div>
                      <div className="report-section-body whitespace-pre-wrap">
                        {section.content}
                      </div>
                      {section.sources.length > 0 && (
                        <details style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--border-light)' }}>
                          <summary
                            style={{
                              fontSize: 11,
                              fontWeight: 700,
                              color: 'var(--text-muted)',
                              cursor: 'pointer',
                              userSelect: 'none',
                            }}
                          >
                            출처 보기
                          </summary>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
                            {section.sources.map((source, index) => {
                              const meta = renderSourceMeta(source);
                              return (
                                <div key={`${source.label}-${index}`} style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                                  {source.url ? (
                                    <a
                                      href={source.url}
                                      target="_blank"
                                      rel="noreferrer"
                                      style={{ color: 'var(--accent)', textDecoration: 'underline' }}
                                    >
                                      {source.label}
                                    </a>
                                  ) : (
                                    <span>{source.label}</span>
                                  )}
                                  {meta && <span>{` · ${meta}`}</span>}
                                </div>
                              );
                            })}
                          </div>
                        </details>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="action-bar">
            <button className="btn btn-secondary" onClick={goPrev}>
              ← 연구 정보 수정
            </button>
            <button className="btn btn-primary" onClick={goNext}>
              에이전트 구성 →
            </button>
          </div>
        </>
      )}
    </div>
  );
}
