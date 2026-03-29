'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useProject } from '@/contexts/ProjectContext';
import { fetchResearch } from '@/lib/api';
import type { ResearchResponse, RefinedResearch } from '@/lib/types';

/* 진행 단계 라벨 */
const STEP_LABELS = [
  '연구 정보 분석 중...',
  '시장 개요 조사 중...',
  '경쟁 환경 분석 중...',
  '타깃 고객 분석 중...',
  '트렌드 및 시사점 도출 중...',
];

/* 보고서 섹션 정의 */
const REPORT_SECTIONS = [
  { key: 'market_overview', icon: '📈', title: '시장 개요' },
  { key: 'competitive_landscape', icon: '🏢', title: '경쟁 환경' },
  { key: 'target_analysis', icon: '👥', title: '타깃 고객 분석' },
  { key: 'trends', icon: '🔮', title: '관련 트렌드' },
  { key: 'implications', icon: '💡', title: '시사점' },
  { key: 'sources', icon: '📚', title: '출처' },
] as const;

/* 고도화된 연구 정보 필드 */
const REFINED_FIELDS = [
  { key: 'refined_background', label: '연구 배경 / 맥락' },
  { key: 'refined_objective', label: '연구 목적 / 목표' },
  { key: 'refined_usage_plan', label: '연구결과 활용방안' },
] as const;

export default function Phase2Page() {
  const router = useRouter();
  const { project, setRefined, setMarketReport, setCurrentPhase } = useProject();

  // 상태
  const [loading, setLoading] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  const [done, setDone] = useState(
    () => !!(project.refined && project.marketReport),
  );
  const [error, setError] = useState<string | null>(null);

  // 인라인 편집
  const [editing, setEditing] = useState(false);
  const [editData, setEditData] = useState<RefinedResearch | null>(null);

  /* 시장조사 시작 */
  const startResearch = useCallback(async () => {
    if (!project.brief) {
      setError('연구 정보가 없습니다. Phase 1에서 입력해주세요.');
      return;
    }

    setLoading(true);
    setError(null);
    setStepIndex(0);
    setDone(false);

    try {
      await fetchResearch(
        project.brief,
        // onStatus — 진행 단계 업데이트
        (step: number) => {
          setStepIndex(step);
        },
        // onDone — 결과 수신
        (result: ResearchResponse) => {
          setRefined(result.refined);
          setMarketReport(result.report);
          setDone(true);
          setLoading(false);
        },
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : '시장조사 중 오류 발생');
      setLoading(false);
    }
  }, [project.brief, setRefined, setMarketReport]);

  /* 편집 모드 토글 */
  const toggleEdit = () => {
    if (!editing && project.refined) {
      setEditData({ ...project.refined });
    }
    setEditing(!editing);
  };

  /* 편집 저장 */
  const saveEdit = () => {
    if (editData) {
      setRefined(editData);
    }
    setEditing(false);
  };

  /* 다음 Phase로 이동 */
  const goNext = () => {
    setCurrentPhase(3);
    router.push('/phase-3');
  };

  /* 이전 Phase로 이동 */
  const goPrev = () => {
    setCurrentPhase(1);
    router.push('/phase-1');
  };

  // brief가 없으면 Phase 1로 안내
  if (!project.brief && !done) {
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

  return (
    <div>
      {/* ── 로딩 상태 ── */}
      {loading && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              🔍 시장조사 · 딥리서치
              <span className="badge badge-ai">AI 진행 중</span>
            </div>
          </div>
          <div className="text-xs font-medium mb-1" style={{ color: 'var(--blue)' }}>
            ⏳ {STEP_LABELS[Math.min(stepIndex, STEP_LABELS.length - 1)]} ({stepIndex}/{STEP_LABELS.length} 단계)
          </div>
          <div className="progress-bar-wrap">
            <div
              className="progress-bar-fill"
              style={{ width: `${(stepIndex / STEP_LABELS.length) * 100}%` }}
            />
          </div>
        </div>
      )}

      {/* ── 시작 전 ── */}
      {!loading && !done && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">🔍 시장조사 · 딥리서치</div>
          </div>
          <p className="text-xs text-text-secondary mb-4">
            입력하신 연구 정보를 기반으로 AI가 시장조사를 수행하고, 연구 정보를 고도화합니다.
          </p>
          {error && (
            <div className="mb-3 p-2.5 rounded-md text-xs" style={{ background: '#fdecea', color: 'var(--red)' }}>
              {error}
            </div>
          )}
          <button className="btn btn-primary" onClick={startResearch}>
            시장조사 시작 →
          </button>
        </div>
      )}

      {/* ── 결과 표시 ── */}
      {done && project.refined && project.marketReport && (
        <>
          {/* 완료 배너 */}
          <div className="card">
            <div className="card-header" style={{ marginBottom: 0 }}>
              <div className="card-title">
                🔍 시장조사 · 딥리서치
                <span className="badge" style={{ background: '#f0f7ee', color: 'var(--green)' }}>완료</span>
              </div>
              <button className="btn btn-ghost text-[11px]" onClick={startResearch}>
                🔄 재조사
              </button>
            </div>
          </div>

          {/* 2컬럼 레이아웃 */}
          <div className="two-col">
            {/* 왼쪽: 고도화된 연구 정보 */}
            <div>
              <div className="card">
                <div className="card-header">
                  <div className="card-title">
                    📝 고도화된 연구 정보
                    <span className="badge badge-ai">AI 보강</span>
                  </div>
                </div>

                {REFINED_FIELDS.map(({ key, label }) => (
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
                      <div
                        className="text-xs leading-[1.8]"
                        style={{
                          background: 'var(--bg)',
                          padding: '10px 12px',
                          borderRadius: 6,
                        }}
                      >
                        {project.refined[key]}
                      </div>
                    )}
                  </div>
                ))}

                {editing ? (
                  <div className="flex gap-2">
                    <button
                      className="btn btn-primary flex-1 justify-center"
                      onClick={saveEdit}
                    >
                      저장
                    </button>
                    <button
                      className="btn btn-secondary flex-1 justify-center"
                      onClick={toggleEdit}
                    >
                      취소
                    </button>
                  </div>
                ) : (
                  <button
                    className="btn btn-secondary w-full justify-center"
                    onClick={toggleEdit}
                  >
                    ✏️ 직접 수정하기
                  </button>
                )}
              </div>
            </div>

            {/* 오른쪽: 시장조사 보고서 */}
            <div>
              <div className="card">
                <div className="card-header">
                  <div className="card-title">📊 시장조사 보고서</div>
                  <button className="btn btn-ghost text-[11px]" onClick={startResearch}>
                    🔄 재조사
                  </button>
                </div>

                {REPORT_SECTIONS.map(({ key, icon, title }) => (
                  <div key={key} className="report-section">
                    <div className="report-section-title">
                      {icon} {title}
                    </div>
                    <div
                      className="report-section-body whitespace-pre-wrap"
                      style={
                        key === 'sources'
                          ? { fontSize: 11, color: 'var(--text-muted)' }
                          : undefined
                      }
                    >
                      {project.marketReport![key as keyof typeof project.marketReport]}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* 액션 바 */}
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
