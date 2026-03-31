'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useProject } from '@/contexts/ProjectContext';
import { fetchAgents, checkAgentFitness } from '@/lib/api';
import type { AgentSchema, FitnessAIResult } from '@/lib/types';
import { buildSystemPromptFromPersona } from '@/lib/persona';
import { checkFitness } from '@/lib/fitness';

/* 타입 라벨 매핑 */
const TYPE_LABELS: Record<string, string> = {
  customer: '가상 고객',
  expert: '도메인 전문가',
  custom: '커스텀',
};

const GENDER_LABELS: Record<'male' | 'female' | 'other', string> = {
  male: '남성',
  female: '여성',
  other: '',
};

/* 빈 페르소나 프로필 */
const EMPTY_PERSONA = {
  age: 25,
  gender: 'female' as const,
  occupation: '',
  personality: '',
  consumption_style: '',
  experience: '',
  pain_points: '',
  communication_style: '',
};

/* 빈 에이전트 템플릿 */
const EMPTY_AGENT: AgentSchema = {
  id: '',
  type: 'customer',
  name: '',
  emoji: '👤',
  description: '',
  tags: [],
  system_prompt: '',
  color: '#2E6DB4',
  persona_profile: { ...EMPTY_PERSONA },
};

const MAX_AGENTS = 8;

export default function Phase3Page() {
  const router = useRouter();
  const { project, setAgents, setMessages, setMinutes, setCurrentPhase } = useProject();

  // 상태
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editData, setEditData] = useState<AgentSchema | null>(null);
  const [isPromptPreviewOpen, setIsPromptPreviewOpen] = useState(false);
  const [aiResult, setAiResult] = useState<FitnessAIResult | null>(null);
  const [isAiLoading, setIsAiLoading] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [needsReanalysis, setNeedsReanalysis] = useState(false);
  const [addMode, setAddMode] = useState(false);
  const [newAgent, setNewAgent] = useState<AgentSchema>({ ...EMPTY_AGENT });

  const agents = project.agents;
  const hasAgents = agents.length > 0;
  const fitness = project.brief ? checkFitness(agents, project.brief) : null;

  const invalidateAiResult = () => {
    setAiResult(null);
    setAiError(null);
    setNeedsReanalysis(true);
  };

  /* AI 에이전트 추천 요청 */
  const requestRecommend = useCallback(async () => {
    if (!project.refined || !project.marketReport) {
      setError('시장조사가 필요합니다. 이전 단계를 먼저 완료해주세요.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await fetchAgents({
        brief: project.brief,
        refined: project.refined,
        report: project.marketReport,
      });
      setAgents(result);
      invalidateAiResult();
      // 하위 단계 데이터 초기화
      setMessages([]);
      setMinutes(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : '에이전트 추천 중 오류 발생');
    } finally {
      setLoading(false);
    }
  }, [project.refined, project.marketReport, setAgents, setMessages, setMinutes]);

  /* 에이전트 삭제 */
  const removeAgent = (id: string) => {
    setAgents(agents.filter((a) => a.id !== id));
    invalidateAiResult();
  };

  /* 편집 시작 */
  const startEdit = (agent: AgentSchema) => {
    setEditingId(agent.id);
    setEditData({ ...agent });
    setIsPromptPreviewOpen(true);
  };

  /* 편집 저장 */
  const saveEdit = () => {
    if (!editData) return;
    setAgents(agents.map((a) => (a.id === editData.id ? editData : a)));
    invalidateAiResult();
    setEditingId(null);
    setEditData(null);
  };

  /* 편집 취소 */
  const cancelEdit = () => {
    setEditingId(null);
    setEditData(null);
    setIsPromptPreviewOpen(false);
  };

  const updateEditData = (updater: (prev: AgentSchema) => AgentSchema) => {
    setEditData((prev) => {
      if (!prev) return prev;
      const next = updater(prev);
      if (next.persona_profile) {
        next.system_prompt = buildSystemPromptFromPersona(
          next.name,
          next.type,
          next.persona_profile,
        );
      }
      return next;
    });
  };

  /* 에이전트 추가 */
  const addAgent = () => {
    const id = `agent-${Date.now()}`;
    const created: AgentSchema = { ...newAgent, id };
    if (created.persona_profile) {
      created.system_prompt = buildSystemPromptFromPersona(
        created.name,
        created.type,
        created.persona_profile,
      );
    }
    setAgents([...agents, created]);
    invalidateAiResult();
    setAddMode(false);
    setNewAgent({ ...EMPTY_AGENT, persona_profile: { ...EMPTY_PERSONA } });
  };

  const runAiFitnessCheck = async () => {
    if (!project.brief || !project.marketReport) return;

    setIsAiLoading(true);
    setAiError(null);
    try {
      const result = await checkAgentFitness({
        agents,
        brief: project.brief,
        report: project.marketReport,
      });
      setAiResult(result);
      setNeedsReanalysis(false);
    } catch (err) {
      setAiError(err instanceof Error ? err.message : 'AI 적합성 분석 중 오류 발생');
      setAiResult(null);
    } finally {
      setIsAiLoading(false);
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'var(--green)';
    if (score >= 60) return 'var(--yellow)';
    return 'var(--red)';
  };

  /* 네비게이션 */
  const goNext = () => {
    setCurrentPhase(4);
    router.push('/phase-4');
  };
  const goPrev = () => {
    setCurrentPhase(2);
    router.push('/phase-2');
  };

  /* 데이터 없으면 Phase 2로 안내 */
  if (!project.refined || !project.marketReport) {
    return (
      <div className="card">
        <div className="card-header">
          <div className="card-title">🤖 에이전트 구성</div>
        </div>
        <p className="text-sm text-text-secondary mb-4">
          시장조사가 완료되지 않았습니다. Phase 2에서 먼저 시장조사를 수행해주세요.
        </p>
        <button className="btn btn-primary" onClick={goPrev}>
          ← 시장조사로 이동
        </button>
      </div>
    );
  }

  return (
    <div>
      {/* ── 헤더 카드 ── */}
      <div className="card">
        <div className="card-header" style={{ marginBottom: hasAgents ? 0 : 14 }}>
          <div className="card-title">
            🤖 에이전트 구성
            {hasAgents && (
              <span className="badge" style={{ background: '#f0f7ee', color: 'var(--green)' }}>
                {agents.length}명
              </span>
            )}
          </div>
          {hasAgents && (
            <button
              className="btn btn-ghost text-[11px]"
              onClick={requestRecommend}
              disabled={loading}
            >
              🔄 재추천
            </button>
          )}
        </div>

        {/* 로딩 */}
        {loading && (
          <div className="spinner-wrap">
            <div className="spinner" />
            <div className="spinner-text">AI가 에이전트를 구성하고 있습니다...</div>
          </div>
        )}

        {/* 시작 전 (에이전트 없음) */}
        {!loading && !hasAgents && (
          <>
            <p className="text-xs text-text-secondary mb-4">
              시장조사 결과를 기반으로 AI가 FGI에 적합한 에이전트를 추천합니다.
            </p>
            {error && (
              <div className="mb-3 p-2.5 rounded-md text-xs" style={{ background: '#fdecea', color: 'var(--red)' }}>
                {error}
              </div>
            )}
            <button className="btn btn-primary" onClick={requestRecommend}>
              에이전트 추천받기 →
            </button>
          </>
        )}
      </div>

      {/* ── 에이전트 그리드 ── */}
      {hasAgents && !loading && (
        <>
          {/* 추천 배너 */}
          <div className="recommend-banner">
            💡 <strong>오케스트레이터 추천:</strong>&nbsp; 연구 목적에 맞춰 에이전트를 구성했습니다. 자유롭게 수정하세요.
          </div>

          {error && (
            <div className="mb-3 p-2.5 rounded-md text-xs" style={{ background: '#fdecea', color: 'var(--red)' }}>
              {error}
            </div>
          )}

          {fitness && (() => {
            const STATUS = {
              good:    { icon: '✅', label: '양호', color: 'var(--green)',  bg: '#f0f7ee', bar: '#2e8b57', border: '#b8dfc8' },
              warning: { icon: '⚠️', label: '주의', color: 'var(--yellow)', bg: '#fffbeb', bar: '#d4a017', border: '#f5e088' },
              poor:    { icon: '❌', label: '미흡', color: 'var(--red)',    bg: '#fdecea', bar: '#c0392b', border: '#f5b8b4' },
            } as const;
            const overall = STATUS[fitness.overall];
            const overallDesc = fitness.overall === 'good'
              ? '에이전트 구성이 연구 목적에 적합합니다'
              : fitness.overall === 'warning'
              ? '일부 항목을 개선하면 더 좋은 결과를 얻을 수 있습니다'
              : '에이전트 구성을 재검토할 것을 권장합니다';

            return (
              <div className="card" style={{ marginBottom: 16, padding: 0, overflow: 'hidden' }}>
                {/* ── 전체 판정 배너 ── */}
                <div style={{ background: overall.bg, borderBottom: `1px solid ${overall.border}`, padding: '12px 18px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ fontSize: 20, lineHeight: 1 }}>{overall.icon}</span>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: overall.color }}>전체 {overall.label}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 1 }}>{overallDesc}</div>
                    </div>
                  </div>
                  <button
                    className="btn btn-ghost text-[11px]"
                    style={{ flexShrink: 0 }}
                    onClick={runAiFitnessCheck}
                    disabled={!project.brief || !project.marketReport || isAiLoading}
                  >
                    AI 상세 분석
                  </button>
                </div>

                <div style={{ padding: '14px 18px' }}>
                  {/* ── 체크 항목 (신호등 바) ── */}
                  <div style={{ display: 'grid', gap: 6 }}>
                    {fitness.checks.map((check) => {
                      const s = STATUS[check.status];
                      return (
                        <div key={check.label} style={{ display: 'flex', borderRadius: 6, overflow: 'hidden', border: `1px solid ${s.border}` }}>
                          <div style={{ width: 4, background: s.bar, flexShrink: 0 }} />
                          <div style={{ flex: 1, padding: '8px 12px', background: s.bg }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 }}>
                              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>{check.label}</div>
                              <span style={{ fontSize: 10, fontWeight: 600, color: s.color, whiteSpace: 'nowrap' }}>
                                {s.icon} {s.label}
                              </span>
                            </div>
                            <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{check.detail}</div>
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {/* ── AI 분석 로딩 ── */}
                  {isAiLoading && (
                    <div className="spinner-wrap" style={{ padding: '16px 0 4px' }}>
                      <div className="spinner" />
                      <div className="spinner-text">AI 분석 중...</div>
                    </div>
                  )}

                  {aiError && (
                    <div style={{ marginTop: 12, padding: '8px 12px', borderRadius: 6, background: '#fdecea', color: 'var(--red)', fontSize: 11 }}>
                      {aiError}
                    </div>
                  )}

                  {needsReanalysis && !isAiLoading && !aiResult && (
                    <div style={{ marginTop: 10, fontSize: 11, color: 'var(--text-muted)' }}>
                      에이전트 구성이 변경되었습니다. AI 상세 분석을 다시 실행해주세요.
                    </div>
                  )}

                  {/* ── AI 분석 결과 ── */}
                  {aiResult && !isAiLoading && (
                    <div style={{ marginTop: 14, borderTop: '1px solid var(--border-light)', paddingTop: 14 }}>
                      {/* 점수 + 요약 */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
                        <div style={{ textAlign: 'center', minWidth: 52, padding: '6px 10px', borderRadius: 8, background: 'var(--bg)', border: '1px solid var(--border-light)' }}>
                          <div style={{ fontSize: 20, fontWeight: 700, color: getScoreColor(aiResult.score), lineHeight: 1 }}>{aiResult.score}</div>
                          <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 2 }}>/ 100</div>
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6, flex: 1 }}>{aiResult.summary}</div>
                      </div>

                      {/* 강점 / 주의 / 제안 */}
                      <div style={{ display: 'grid', gap: 10 }}>
                        {aiResult.strengths.length > 0 && (
                          <div>
                            <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--green)', textTransform: 'uppercase', letterSpacing: '0.4px', marginBottom: 5 }}>✅ 강점</div>
                            <div style={{ display: 'grid', gap: 3 }}>
                              {aiResult.strengths.map((item, i) => (
                                <div key={i} style={{ fontSize: 11, color: 'var(--text-secondary)', paddingLeft: 8, borderLeft: '2px solid #b8dfc8' }}>{item}</div>
                              ))}
                            </div>
                          </div>
                        )}
                        {aiResult.warnings.length > 0 && (
                          <div>
                            <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--yellow)', textTransform: 'uppercase', letterSpacing: '0.4px', marginBottom: 5 }}>⚠️ 주의</div>
                            <div style={{ display: 'grid', gap: 3 }}>
                              {aiResult.warnings.map((item, i) => (
                                <div key={i} style={{ fontSize: 11, color: 'var(--text-secondary)', paddingLeft: 8, borderLeft: '2px solid #f5e088' }}>{item}</div>
                              ))}
                            </div>
                          </div>
                        )}
                        {aiResult.suggestions.length > 0 && (
                          <div>
                            <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.4px', marginBottom: 5 }}>💡 제안</div>
                            <div style={{ display: 'grid', gap: 3 }}>
                              {aiResult.suggestions.map((item, i) => (
                                <div key={i} style={{ fontSize: 11, color: 'var(--text-secondary)', paddingLeft: 8, borderLeft: '2px solid var(--accent-border)' }}>{item}</div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })()}
          )}

          <div className="agent-grid">
            {agents.map((agent) =>
              editingId === agent.id && editData ? (
                /* ── 편집 모드 카드 ── */
                <div key={agent.id} className="agent-card" style={{ borderColor: 'var(--accent)' }}>
                  <div className="field-group">
                    <div className="field-label">이모지</div>
                    <input
                      className="field-input"
                      value={editData.emoji}
                      onChange={(e) => updateEditData((prev) => ({ ...prev, emoji: e.target.value }))}
                    />
                  </div>
                  <div className="field-group">
                    <div className="field-label">이름</div>
                    <input
                      className="field-input"
                      value={editData.name}
                      onChange={(e) => updateEditData((prev) => ({ ...prev, name: e.target.value }))}
                    />
                  </div>
                  <div className="field-group">
                    <div className="field-label">유형</div>
                    <select
                      className="field-input"
                      value={editData.type}
                      onChange={(e) =>
                        updateEditData((prev) => ({
                          ...prev,
                          type: e.target.value as AgentSchema['type'],
                        }))
                      }
                    >
                      <option value="customer">가상 고객</option>
                      <option value="expert">도메인 전문가</option>
                      <option value="custom">커스텀</option>
                    </select>
                  </div>
                  <div className="field-group">
                    <div className="field-label">설명</div>
                    <textarea
                      className="field-textarea"
                      rows={3}
                      value={editData.description}
                      onChange={(e) =>
                        updateEditData((prev) => ({ ...prev, description: e.target.value }))
                      }
                    />
                  </div>
                  <div className="field-group">
                    <div className="field-label">태그 (쉼표 구분)</div>
                    <input
                      className="field-input"
                      value={editData.tags.join(', ')}
                      onChange={(e) =>
                        updateEditData((prev) => ({
                          ...prev,
                          tags: e.target.value.split(',').map((t) => t.trim()).filter(Boolean),
                        }))
                      }
                    />
                  </div>
                  {editData.persona_profile ? (
                    <>
                      <div className="field-group">
                        <div className="field-label">나이</div>
                        <input
                          className="field-input"
                          type="number"
                          value={editData.persona_profile.age}
                          onChange={(e) =>
                            updateEditData((prev) => ({
                              ...prev,
                              persona_profile: {
                                ...prev.persona_profile!,
                                age: Number(e.target.value) || 0,
                              },
                            }))
                          }
                        />
                      </div>
                      <div className="field-group">
                        <div className="field-label">성별</div>
                        <select
                          className="field-input"
                          value={editData.persona_profile.gender}
                          onChange={(e) =>
                            updateEditData((prev) => ({
                              ...prev,
                              persona_profile: {
                                ...prev.persona_profile!,
                                gender: e.target.value as NonNullable<AgentSchema['persona_profile']>['gender'],
                              },
                            }))
                          }
                        >
                          <option value="male">남성</option>
                          <option value="female">여성</option>
                          <option value="other">기타</option>
                        </select>
                      </div>
                      <div className="field-group">
                        <div className="field-label">직업</div>
                        <input
                          className="field-input"
                          value={editData.persona_profile.occupation}
                          onChange={(e) =>
                            updateEditData((prev) => ({
                              ...prev,
                              persona_profile: {
                                ...prev.persona_profile!,
                                occupation: e.target.value,
                              },
                            }))
                          }
                        />
                      </div>
                      <div className="field-group">
                        <div className="field-label">성격</div>
                        <input
                          className="field-input"
                          value={editData.persona_profile.personality}
                          onChange={(e) =>
                            updateEditData((prev) => ({
                              ...prev,
                              persona_profile: {
                                ...prev.persona_profile!,
                                personality: e.target.value,
                              },
                            }))
                          }
                        />
                      </div>
                      <div className="field-group">
                        <div className="field-label">소비 스타일</div>
                        <textarea
                          className="field-textarea"
                          rows={2}
                          value={editData.persona_profile.consumption_style}
                          onChange={(e) =>
                            updateEditData((prev) => ({
                              ...prev,
                              persona_profile: {
                                ...prev.persona_profile!,
                                consumption_style: e.target.value,
                              },
                            }))
                          }
                        />
                      </div>
                      <div className="field-group">
                        <div className="field-label">관련 경험</div>
                        <textarea
                          className="field-textarea"
                          rows={3}
                          value={editData.persona_profile.experience}
                          onChange={(e) =>
                            updateEditData((prev) => ({
                              ...prev,
                              persona_profile: {
                                ...prev.persona_profile!,
                                experience: e.target.value,
                              },
                            }))
                          }
                        />
                      </div>
                      <div className="field-group">
                        <div className="field-label">불만/니즈</div>
                        <textarea
                          className="field-textarea"
                          rows={2}
                          value={editData.persona_profile.pain_points}
                          onChange={(e) =>
                            updateEditData((prev) => ({
                              ...prev,
                              persona_profile: {
                                ...prev.persona_profile!,
                                pain_points: e.target.value,
                              },
                            }))
                          }
                        />
                      </div>
                      <div className="field-group">
                        <div className="field-label">말투</div>
                        <input
                          className="field-input"
                          value={editData.persona_profile.communication_style}
                          onChange={(e) =>
                            updateEditData((prev) => ({
                              ...prev,
                              persona_profile: {
                                ...prev.persona_profile!,
                                communication_style: e.target.value,
                              },
                            }))
                          }
                        />
                      </div>
                      <div className="field-group">
                        <button
                          className="btn btn-ghost w-full justify-between"
                          onClick={() => setIsPromptPreviewOpen((prev) => !prev)}
                        >
                          생성된 system_prompt
                          <span>{isPromptPreviewOpen ? '접기' : '펼치기'}</span>
                        </button>
                        {isPromptPreviewOpen && (
                          <div className="agent-desc" style={{ whiteSpace: 'pre-wrap', marginTop: 8 }}>
                            {editData.system_prompt}
                          </div>
                        )}
                      </div>
                    </>
                  ) : (
                    <div className="field-group">
                      <div className="field-label">시스템 프롬프트</div>
                      <textarea
                        className="field-textarea"
                        rows={4}
                        value={editData.system_prompt}
                        onChange={(e) =>
                          updateEditData((prev) => ({ ...prev, system_prompt: e.target.value }))
                        }
                      />
                    </div>
                  )}
                  <div className="flex gap-2 mt-2">
                    <button className="btn btn-primary flex-1 justify-center" onClick={saveEdit}>
                      저장
                    </button>
                    <button className="btn btn-secondary flex-1 justify-center" onClick={cancelEdit}>
                      취소
                    </button>
                  </div>
                </div>
              ) : (
                /* ── 일반 카드 ── */
                <div key={agent.id} className="agent-card">
                  <div className="agent-actions">
                    <button
                      className="agent-action-btn"
                      title="수정"
                      onClick={() => startEdit(agent)}
                    >
                      ✏️
                    </button>
                    <button
                      className="agent-action-btn"
                      title="삭제"
                      onClick={() => removeAgent(agent.id)}
                    >
                      ✕
                    </button>
                  </div>
                  <div className={`agent-avatar avatar-${agent.type}`}>{agent.emoji}</div>
                  <div className="agent-name">{agent.name}</div>
                  <div className={`agent-type type-${agent.type}`}>
                    {TYPE_LABELS[agent.type] || agent.type}
                  </div>
                  {agent.persona_profile ? (
                    <div className="agent-persona">
                      <div className="agent-persona-meta">
                        <span>{agent.persona_profile.age}세</span>
                        {GENDER_LABELS[agent.persona_profile.gender] && (
                          <>
                            <span className="agent-persona-separator">·</span>
                            <span>{GENDER_LABELS[agent.persona_profile.gender]}</span>
                          </>
                        )}
                        <span className="agent-persona-separator">·</span>
                        <span>{agent.persona_profile.occupation}</span>
                      </div>
                      <div className="agent-persona-row">
                        <span className="agent-persona-label">성격:</span>
                        <span>{agent.persona_profile.personality}</span>
                      </div>
                      <div className="agent-persona-row">
                        <span className="agent-persona-label">소비:</span>
                        <span>{agent.persona_profile.consumption_style}</span>
                      </div>
                      <div className="agent-persona-row agent-persona-row-clamp">
                        <span className="agent-persona-label">경험:</span>
                        <span>{agent.persona_profile.experience}</span>
                      </div>
                      <div className="agent-persona-row">
                        <span className="agent-persona-label">니즈:</span>
                        <span>{agent.persona_profile.pain_points}</span>
                      </div>
                      <div className="agent-persona-row">
                        <span className="agent-persona-label">말투:</span>
                        <span>{agent.persona_profile.communication_style}</span>
                      </div>
                    </div>
                  ) : (
                    <div className="agent-desc">{agent.system_prompt}</div>
                  )}
                  <div className="agent-tags">
                    {agent.tags.map((tag) => (
                      <span key={tag} className="agent-tag">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              ),
            )}

            {/* ── 에이전트 추가 카드 ── */}
            {agents.length < MAX_AGENTS && !addMode && (
              <div className="agent-add-card" onClick={() => setAddMode(true)}>
                <span style={{ fontSize: 20 }}>+</span>
                <span>에이전트 추가</span>
                <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>최대 {MAX_AGENTS}명</span>
              </div>
            )}

            {/* ── 추가 입력 카드 ── */}
            {addMode && (
              <div className="agent-card" style={{ borderColor: 'var(--accent)' }}>
                <div className="field-group">
                  <div className="field-label">이모지</div>
                  <input
                    className="field-input"
                    value={newAgent.emoji}
                    onChange={(e) => setNewAgent({ ...newAgent, emoji: e.target.value })}
                  />
                </div>
                <div className="field-group">
                  <div className="field-label">이름</div>
                  <input
                    className="field-input"
                    value={newAgent.name}
                    onChange={(e) => setNewAgent({ ...newAgent, name: e.target.value })}
                    placeholder="예: 김서연"
                  />
                </div>
                <div className="field-group">
                  <div className="field-label">유형</div>
                  <select
                    className="field-input"
                    value={newAgent.type}
                    onChange={(e) => {
                      const type = e.target.value as AgentSchema['type'];
                      setNewAgent({
                        ...newAgent,
                        type,
                        persona_profile: type !== 'custom' ? (newAgent.persona_profile ?? { ...EMPTY_PERSONA }) : null,
                      });
                    }}
                  >
                    <option value="customer">가상 고객</option>
                    <option value="expert">도메인 전문가</option>
                    <option value="custom">커스텀</option>
                  </select>
                </div>
                <div className="field-group">
                  <div className="field-label">설명</div>
                  <textarea
                    className="field-textarea"
                    rows={3}
                    value={newAgent.description}
                    onChange={(e) => setNewAgent({ ...newAgent, description: e.target.value })}
                    placeholder="에이전트 설명을 입력하세요"
                  />
                </div>
                <div className="field-group">
                  <div className="field-label">태그 (쉼표 구분)</div>
                  <input
                    className="field-input"
                    value={newAgent.tags.join(', ')}
                    onChange={(e) =>
                      setNewAgent({
                        ...newAgent,
                        tags: e.target.value.split(',').map((t) => t.trim()).filter(Boolean),
                      })
                    }
                    placeholder="태그1, 태그2, 태그3"
                  />
                </div>
                {newAgent.persona_profile ? (
                  <>
                    <div className="field-group">
                      <div className="field-label">나이</div>
                      <input
                        className="field-input"
                        type="number"
                        value={newAgent.persona_profile.age}
                        onChange={(e) =>
                          setNewAgent({
                            ...newAgent,
                            persona_profile: {
                              ...newAgent.persona_profile!,
                              age: Number(e.target.value) || 0,
                            },
                          })
                        }
                      />
                    </div>
                    <div className="field-group">
                      <div className="field-label">성별</div>
                      <select
                        className="field-input"
                        value={newAgent.persona_profile.gender}
                        onChange={(e) =>
                          setNewAgent({
                            ...newAgent,
                            persona_profile: {
                              ...newAgent.persona_profile!,
                              gender: e.target.value as NonNullable<AgentSchema['persona_profile']>['gender'],
                            },
                          })
                        }
                      >
                        <option value="male">남성</option>
                        <option value="female">여성</option>
                        <option value="other">기타</option>
                      </select>
                    </div>
                    <div className="field-group">
                      <div className="field-label">직업</div>
                      <input
                        className="field-input"
                        value={newAgent.persona_profile.occupation}
                        onChange={(e) =>
                          setNewAgent({
                            ...newAgent,
                            persona_profile: {
                              ...newAgent.persona_profile!,
                              occupation: e.target.value,
                            },
                          })
                        }
                        placeholder="예: IT기업 UX디자이너"
                      />
                    </div>
                    <div className="field-group">
                      <div className="field-label">성격</div>
                      <input
                        className="field-input"
                        value={newAgent.persona_profile.personality}
                        onChange={(e) =>
                          setNewAgent({
                            ...newAgent,
                            persona_profile: {
                              ...newAgent.persona_profile!,
                              personality: e.target.value,
                            },
                          })
                        }
                        placeholder="예: 외향적, 트렌드에 민감, 충동적"
                      />
                    </div>
                    <div className="field-group">
                      <div className="field-label">소비 스타일</div>
                      <textarea
                        className="field-textarea"
                        rows={2}
                        value={newAgent.persona_profile.consumption_style}
                        onChange={(e) =>
                          setNewAgent({
                            ...newAgent,
                            persona_profile: {
                              ...newAgent.persona_profile!,
                              consumption_style: e.target.value,
                            },
                          })
                        }
                        placeholder="예: SNS에서 본 제품을 바로 구매하는 편"
                      />
                    </div>
                    <div className="field-group">
                      <div className="field-label">관련 경험</div>
                      <textarea
                        className="field-textarea"
                        rows={3}
                        value={newAgent.persona_profile.experience}
                        onChange={(e) =>
                          setNewAgent({
                            ...newAgent,
                            persona_profile: {
                              ...newAgent.persona_profile!,
                              experience: e.target.value,
                            },
                          })
                        }
                        placeholder="구체적인 이용 에피소드를 작성하세요"
                      />
                    </div>
                    <div className="field-group">
                      <div className="field-label">불만/니즈</div>
                      <textarea
                        className="field-textarea"
                        rows={2}
                        value={newAgent.persona_profile.pain_points}
                        onChange={(e) =>
                          setNewAgent({
                            ...newAgent,
                            persona_profile: {
                              ...newAgent.persona_profile!,
                              pain_points: e.target.value,
                            },
                          })
                        }
                        placeholder="구체적인 불만이나 니즈를 작성하세요"
                      />
                    </div>
                    <div className="field-group">
                      <div className="field-label">말투</div>
                      <input
                        className="field-input"
                        value={newAgent.persona_profile.communication_style}
                        onChange={(e) =>
                          setNewAgent({
                            ...newAgent,
                            persona_profile: {
                              ...newAgent.persona_profile!,
                              communication_style: e.target.value,
                            },
                          })
                        }
                        placeholder="예: 수다스럽고 감탄사가 많음"
                      />
                    </div>
                  </>
                ) : (
                  <div className="field-group">
                    <div className="field-label">시스템 프롬프트</div>
                    <textarea
                      className="field-textarea"
                      rows={4}
                      value={newAgent.system_prompt}
                      onChange={(e) => setNewAgent({ ...newAgent, system_prompt: e.target.value })}
                      placeholder="에이전트의 페르소나를 상세히 작성하세요"
                    />
                  </div>
                )}
                <div className="flex gap-2 mt-2">
                  <button
                    className="btn btn-primary flex-1 justify-center"
                    onClick={addAgent}
                    disabled={!newAgent.name.trim()}
                  >
                    추가
                  </button>
                  <button
                    className="btn btn-secondary flex-1 justify-center"
                    onClick={() => {
                      setAddMode(false);
                      setNewAgent({ ...EMPTY_AGENT, persona_profile: { ...EMPTY_PERSONA } });
                    }}
                  >
                    취소
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* ── 액션 바 ── */}
          <div className="action-bar">
            <button className="btn btn-secondary" onClick={goPrev}>
              ← 시장조사 수정
            </button>
            <button className="btn btn-primary" onClick={goNext}>
              회의 시작 →
            </button>
          </div>
        </>
      )}
    </div>
  );
}
