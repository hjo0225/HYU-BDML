"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useProject } from "@/contexts/ProjectContext";
import { fetchRefinedResearch, fetchMarketReportStream } from "@/lib/api";
import type { EvidenceItem, RefinedResearch, ThinkingEvent } from "@/lib/types";

const REFINING_STEPS = [
  "연구 정보 분석 중...",
  "입력 맥락 정리 중...",
  "핵심 목적 정제 중...",
] as const;

const REPORT_STEPS = [
  "시장 데이터 수집 중...",
  "수치·기업 정보 검증 중...",
  "보고서 섹션 작성 중...",
  "보고서 정리 중...",
] as const;

const REPORT_SECTIONS = [
  { key: "market_overview", icon: "📈", title: "시장 개요" },
  { key: "competitive_landscape", icon: "🏢", title: "경쟁 환경" },
  { key: "target_analysis", icon: "👥", title: "타깃 고객 분석" },
  { key: "trends", icon: "🔮", title: "관련 트렌드" },
  { key: "implications", icon: "💡", title: "시사점" },
] as const;

const REFINED_FIELDS = [
  {
    key: "refined_background",
    label: "연구 배경 / 맥락",
    originalKey: "background",
  },
  {
    key: "refined_objective",
    label: "연구 목적 / 목표",
    originalKey: "objective",
  },
  {
    key: "refined_usage_plan",
    label: "연구결과 활용방안",
    originalKey: "usage_plan",
  },
] as const;

function renderEvidenceMeta(source: EvidenceItem): string {
  return [
    source.publisher,
    source.published_at,
    source.source_engine === "naver" ? "Naver" : source.source_engine === "openai_web" ? "OpenAI Web" : "",
    `가중치 ${source.relevance_score.toFixed(2)}`,
  ]
    .filter(Boolean)
    .join(" · ");
}

function sourceTypeLabel(sourceType: EvidenceItem["source_type"]): string {
  switch (sourceType) {
    case "doc":
      return "전문자료";
    case "news":
      return "뉴스";
    case "webkr":
      return "웹문서";
    case "blog":
      return "블로그";
    case "cafearticle":
      return "카페";
  }
}

export default function Phase2Page() {
  const router = useRouter();
  const {
    project,
    setRefined,
    setCurrentPhase,
    resetAfterRefinedChange,
    resetAfterMarketReportChange,
  } = useProject();

  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState<
    "idle" | "refining" | "refined" | "reporting" | "done"
  >(() => {
    if (project.refined && project.marketReport) return "done";
    if (project.refined) return "refined";
    return "idle";
  });
  const [error, setError] = useState<string | null>(null);
  const [stepIndex, setStepIndex] = useState(0);
  const [editing, setEditing] = useState(false);
  const [editData, setEditData] = useState<RefinedResearch | null>(
    project.refined ?? null
  );
  const [partialSections, setPartialSections] = useState<
    Record<string, string>
  >({});
  const [thinkingLog, setThinkingLog] = useState<ThinkingEvent[]>([]);
  const thinkingEndRef = useRef<HTMLDivElement>(null);

  // sessionStorage 복원 후 stage 동기화
  // (useState 초기값은 sessionStorage 로드 전에 실행되므로 useEffect로 보정)
  useEffect(() => {
    if (loading) return;
    if (project.refined && project.marketReport) {
      setStage("done");
    } else if (project.refined && !project.marketReport) {
      setStage((prev) => (prev === "idle" ? "refined" : prev));
    }
  }, [project.refined, project.marketReport, loading]);

  useEffect(() => {
    if (!loading) {
      setStepIndex(0);
      return;
    }
    const totalSteps =
      stage === "refining" ? REFINING_STEPS.length : REPORT_STEPS.length;
    // refining은 LLM 단독 호출이라 빠름 → 1.2초 간격, reporting은 웹검색 포함 → 8초 간격
    const intervalMs = stage === "refining" ? 1200 : 8000;
    const id = setInterval(() => {
      setStepIndex((prev) => Math.min(prev + 1, totalSteps - 1));
    }, intervalMs);
    return () => clearInterval(id);
  }, [loading, stage]);

  useEffect(() => {
    thinkingEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [thinkingLog]);

  const startRefining = useCallback(async () => {
    if (!project.brief) {
      setError("연구 정보가 없습니다. Phase 1에서 입력해주세요.");
      return;
    }
    if (loading) return;

    setLoading(true);
    setError(null);
    setStage("refining");
    setEditing(false);
    resetAfterRefinedChange(null);

    try {
      const refined = await fetchRefinedResearch(project.brief);
      setRefined(refined);
      setEditData(refined);
      setStage("refined");
    } catch (err) {
      setStage("idle");
      setError(
        err instanceof Error ? err.message : "연구 정보 정제 중 오류 발생"
      );
    } finally {
      setLoading(false);
    }
  }, [loading, project.brief, resetAfterRefinedChange, setRefined]);

  const generateReport = useCallback(async () => {
    if (!project.brief || !project.refined) {
      setError("정제된 연구 정보가 없습니다. 먼저 정제를 완료해주세요.");
      return;
    }
    if (loading) return;

    const refinedInput = editing ? editData : project.refined;
    if (!refinedInput) {
      setError("시장조사 입력용 정제본이 없습니다.");
      return;
    }

    setLoading(true);
    setError(null);
    setStage("reporting");
    setPartialSections({});
    setThinkingLog([]);

    try {
      if (editing) {
        setRefined(refinedInput);
        setEditing(false);
      }
      await fetchMarketReportStream(
        project.brief,
        refinedInput,
        (field, content) => {
          setPartialSections((prev) => ({ ...prev, [field]: content }));
        },
        (updatedRefined, report) => {
          setRefined(updatedRefined);
          resetAfterMarketReportChange(report);
          setStage("done");
        },
        (event) => {
          setThinkingLog((prev) => [...prev, event]);
        },
        (field, delta) => {
          setPartialSections((prev) => ({
            ...prev,
            [field]: (prev[field] ?? "") + delta,
          }));
        }
      );
    } catch (err) {
      setStage("refined");
      setError(
        err instanceof Error ? err.message : "시장조사 보고서 생성 중 오류 발생"
      );
    } finally {
      setLoading(false);
    }
  }, [
    editData,
    editing,
    loading,
    project.brief,
    project.refined,
    resetAfterMarketReportChange,
    setRefined,
  ]);

  const toggleEdit = () => {
    if (!editing && project.refined) {
      setEditData({ ...project.refined });
    }
    setEditing((prev) => !prev);
  };

  const saveEdit = () => {
    if (editData) {
      resetAfterRefinedChange(editData);
      setStage("refined");
    }
    setEditing(false);
  };

  const goNext = () => {
    setCurrentPhase(3);
    router.push("/agent-setup");
  };

  const goPrev = () => {
    setCurrentPhase(1);
    router.push("/research-input");
  };

  if (!project.brief && stage !== "done") {
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

  const loadingSteps = stage === "refining" ? REFINING_STEPS : REPORT_STEPS;

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
              style={{
                width: `${Math.round(
                  ((stepIndex + 1) / loadingSteps.length) * 100
                )}%`,
                transition: "width 0.8s ease",
              }}
            />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {loadingSteps.map((label, i) => (
              <div
                key={label}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  opacity: i > stepIndex ? 0.3 : 1,
                  transition: "opacity 0.4s",
                }}
              >
                <span
                  style={{
                    fontSize: 12,
                    color:
                      i < stepIndex
                        ? "var(--green)"
                        : i === stepIndex
                        ? "var(--accent)"
                        : "var(--text-muted)",
                  }}
                >
                  {i < stepIndex ? "✓" : i === stepIndex ? "●" : "○"}
                </span>
                <span className="spinner-text" style={{ margin: 0 }}>
                  {label}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {loading && stage === "reporting" && thinkingLog.length > 0 && (
        <div className="card" style={{ marginTop: 12 }}>
          <div className="card-header" style={{ marginBottom: 8 }}>
            <div className="card-title" style={{ fontSize: 13 }}>
              🧠 AI 사고 과정
            </div>
          </div>
          <div
            style={{
              maxHeight: 160,
              overflowY: "auto",
              display: "flex",
              flexDirection: "column",
              gap: 4,
            }}
          >
            {thinkingLog.map((evt, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 6,
                  fontSize: 11,
                  color: "var(--text-secondary)",
                }}
              >
                <span
                  style={{
                    flexShrink: 0,
                    color:
                      evt.agent === "researcher"
                        ? "var(--accent)"
                        : "var(--green)",
                  }}
                >
                  {evt.agent === "researcher" ? "🔍" : "✅"}
                </span>
                <span style={{ lineHeight: 1.5 }}>
                  <span
                    style={{
                      fontWeight: 600,
                      color:
                        evt.agent === "researcher"
                          ? "var(--accent)"
                          : "var(--green)",
                      marginRight: 4,
                    }}
                  >
                    {evt.agent === "researcher" ? "리서처" : "팩트체커"}
                  </span>
                  {evt.query}
                </span>
              </div>
            ))}
            <div ref={thinkingEndRef} />
          </div>
        </div>
      )}

      {loading &&
        stage === "reporting" &&
        Object.keys(partialSections).length > 0 && (
          <div className="card" style={{ marginTop: 12 }}>
            <div className="card-header">
              <div className="card-title">
                📊 시장조사 보고서
                <span className="badge badge-ai">작성 중</span>
              </div>
            </div>
            {REPORT_SECTIONS.map(({ key, icon, title }) => {
              const content = partialSections[key];
              return (
                <div
                  key={key}
                  className="report-section"
                  style={{
                    opacity: content ? 1 : 0.35,
                    transition: "opacity 0.4s",
                  }}
                >
                  <div className="report-section-title">
                    {icon} {title}
                    {!content && (
                      <span
                        style={{
                          fontSize: 11,
                          color: "var(--text-muted)",
                          marginLeft: 8,
                        }}
                      >
                        검색 중...
                      </span>
                    )}
                  </div>
                  {content && (
                    <div className="report-section-body whitespace-pre-wrap">
                      {content}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

      {!loading && stage === "idle" && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">🔍 시장조사 · 딥리서치</div>
          </div>
          <p className="text-xs text-text-secondary mb-4">
            먼저 연구 정보를 정제한 뒤, 정제된 입력을 기준으로 시장조사 보고서를
            생성합니다.
          </p>
          {error && (
            <div
              className="mb-3 p-2.5 rounded-md text-xs"
              style={{ background: "#fdecea", color: "var(--red)" }}
            >
              <div>{error}</div>
              <button
                className="btn btn-ghost text-[11px] mt-1"
                style={{ color: "var(--red)" }}
                onClick={startRefining}
              >
                다시 시도
              </button>
            </div>
          )}
          <button className="btn btn-primary" onClick={startRefining}>
            연구 정보 정제 시작 →
          </button>
        </div>
      )}

      {!loading && stage === "refined" && project.refined && (
        <>
          <div className="card">
            <div className="card-header" style={{ marginBottom: 0 }}>
              <div className="card-title">
                📝 연구 정보 정제
                <span
                  className="badge"
                  style={{ background: "#eef5ff", color: "var(--accent)" }}
                >
                  정제 완료
                </span>
              </div>
              <button
                className="btn btn-ghost text-[11px]"
                onClick={startRefining}
                disabled={loading}
              >
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
                        value={editData?.[key] || ""}
                        onChange={(e) =>
                          setEditData((prev) =>
                            prev ? { ...prev, [key]: e.target.value } : prev
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
                  <div
                    className="mb-3 p-2.5 rounded-md text-xs"
                    style={{ background: "#fdecea", color: "var(--red)" }}
                  >
                    <div>{error}</div>
                  </div>
                )}

                {editing ? (
                  <div className="flex gap-2">
                    <button
                      className="btn btn-primary flex-1 justify-center"
                      onClick={saveEdit}
                    >
                      정제본 저장
                    </button>
                    <button
                      className="btn btn-secondary flex-1 justify-center"
                      onClick={toggleEdit}
                    >
                      취소
                    </button>
                  </div>
                ) : (
                  <div className="flex gap-2">
                    <button
                      className="btn btn-secondary flex-1 justify-center"
                      onClick={toggleEdit}
                    >
                      ✏️ 정제본 수정
                    </button>
                    <button
                      className="btn btn-primary flex-1 justify-center"
                      onClick={generateReport}
                    >
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
                <div
                  className="text-xs text-text-secondary"
                  style={{ lineHeight: 1.8 }}
                >
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

      {stage === "done" && project.refined && project.marketReport && (
        <>
          <div className="card">
            <div className="card-header" style={{ marginBottom: 0 }}>
              <div className="card-title">
                🔍 시장조사 · 딥리서치
                <span
                  className="badge"
                  style={{ background: "#f0f7ee", color: "var(--green)" }}
                >
                  완료
                </span>
              </div>
              <button
                className="btn btn-ghost text-[11px]"
                onClick={generateReport}
                disabled={loading}
              >
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
                        value={editData?.[key] || ""}
                        onChange={(e) =>
                          setEditData((prev) =>
                            prev ? { ...prev, [key]: e.target.value } : prev
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
                  <div className="flex gap-2">
                    <button
                      className="btn btn-secondary flex-1 justify-center"
                      onClick={toggleEdit}
                    >
                      ✏️ 정제본 수정하기
                    </button>
                    <button
                      className="btn btn-primary flex-1 justify-center"
                      onClick={generateReport}
                    >
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
                  <button
                    className="btn btn-ghost text-[11px]"
                    onClick={generateReport}
                    disabled={loading}
                  >
                    🔄 보고서 재생성
                  </button>
                </div>

                {error && (
                  <div
                    className="mb-3 p-2.5 rounded-md text-xs"
                    style={{ background: "#fdecea", color: "var(--red)" }}
                  >
                    <div>{error}</div>
                  </div>
                )}

                {REPORT_SECTIONS.map(({ key, icon, title }) => {
                  const section = project.marketReport![key];
                  return (
                    <div key={key} className="report-section">
                      <div className="report-section-title">
                        {icon} {title}
                      </div>
                      <div className="report-section-body whitespace-pre-wrap">
                        {section.summary}
                      </div>
                      {section.key_claims.length > 0 && (
                        <div style={{ marginTop: 10 }}>
                          <div
                            style={{
                              fontSize: 11,
                              fontWeight: 700,
                              color: "var(--text-muted)",
                              marginBottom: 6,
                            }}
                          >
                            핵심 주장
                          </div>
                          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                            {section.key_claims.map((claim, index) => (
                              <div
                                key={`${key}-claim-${index}`}
                                style={{ fontSize: 12, lineHeight: 1.6, color: "var(--text-secondary)" }}
                              >
                                {`• ${claim}`}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      <div style={{ marginTop: 10 }}>
                        <span
                          className="badge"
                          style={{
                            background:
                              section.confidence === "high"
                                ? "#eef8f1"
                                : section.confidence === "medium"
                                ? "#fff5e8"
                                : "#fdecea",
                            color:
                              section.confidence === "high"
                                ? "var(--green)"
                                : section.confidence === "medium"
                                ? "#b26a00"
                                : "var(--red)",
                          }}
                        >
                          {`신뢰도 ${section.confidence}`}
                        </span>
                      </div>
                      {section.evidence.length > 0 && (
                        <details
                          style={{
                            marginTop: 10,
                            paddingTop: 10,
                            borderTop: "1px solid var(--border-light)",
                          }}
                        >
                          <summary
                            style={{
                              fontSize: 11,
                              fontWeight: 700,
                              color: "var(--text-muted)",
                              cursor: "pointer",
                              userSelect: "none",
                            }}
                          >
                            근거 보기
                          </summary>
                          <div
                            style={{
                              display: "flex",
                              flexDirection: "column",
                              gap: 6,
                              marginTop: 8,
                            }}
                          >
                            {section.evidence.map((source, index) => {
                              const meta = renderEvidenceMeta(source);
                              return (
                                <div
                                  key={`${source.url}-${index}`}
                                  style={{
                                    fontSize: 11,
                                    color: "var(--text-muted)",
                                  }}
                                >
                                  <span
                                    className="badge"
                                    style={{
                                      background: "#eef5ff",
                                      color: "var(--accent)",
                                      marginRight: 6,
                                    }}
                                  >
                                    {sourceTypeLabel(source.source_type)}
                                  </span>
                                  {source.url ? (
                                    <a
                                      href={source.url}
                                      target="_blank"
                                      rel="noreferrer"
                                      style={{
                                        color: "var(--accent)",
                                        textDecoration: "underline",
                                      }}
                                    >
                                      {source.title}
                                    </a>
                                  ) : (
                                    <span>{source.title}</span>
                                  )}
                                  {meta && <span>{` · ${meta}`}</span>}
                                  {source.snippet && (
                                    <div style={{ marginTop: 4, lineHeight: 1.5 }}>
                                      {source.snippet}
                                    </div>
                                  )}
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
