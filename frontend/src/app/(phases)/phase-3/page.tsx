'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useProject } from '@/contexts/ProjectContext';
import { fetchAgents } from '@/lib/api';
import type { AgentSchema } from '@/lib/types';
import { buildSystemPromptFromPersona } from '@/lib/persona';

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
  const { project, setAgents, setMeetingTopic, setMessages, setMinutes, setCurrentPhase } = useProject();

  // 상태
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editData, setEditData] = useState<AgentSchema | null>(null);
  const [isPromptPreviewOpen, setIsPromptPreviewOpen] = useState(false);
  const [addMode, setAddMode] = useState(false);
  const [newAgent, setNewAgent] = useState<AgentSchema>({ ...EMPTY_AGENT });

  const agents = project.agents;
  const hasAgents = agents.length > 0;

  /* AI 에이전트 추천 요청 */
  const requestRecommend = useCallback(async () => {
    if (!project.brief || !project.refined || !project.marketReport) {
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
      // 하위 단계 데이터 초기화
      setMeetingTopic(null);
      setMessages([]);
      setMinutes(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : '에이전트 추천 중 오류 발생');
    } finally {
      setLoading(false);
    }
  }, [project.refined, project.marketReport, setAgents, setMeetingTopic, setMessages, setMinutes]);

  /* 에이전트 삭제 */
  const removeAgent = (id: string) => {
    setAgents(agents.filter((a) => a.id !== id));
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
    setAddMode(false);
    setNewAgent({ ...EMPTY_AGENT, persona_profile: { ...EMPTY_PERSONA } });
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
                <div>{error}</div>
                <button className="btn btn-ghost text-[11px] mt-1" style={{ color: 'var(--red)' }} onClick={requestRecommend}>
                  다시 시도
                </button>
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
              <div>{error}</div>
              <button className="btn btn-ghost text-[11px] mt-1" style={{ color: 'var(--red)' }} onClick={requestRecommend}>
                다시 시도
              </button>
            </div>
          )}

          {/* ── 편집 드로어 ── */}
          {editingId && editData && (
            <>
              <div className="drawer-overlay" onClick={cancelEdit} />
              <div className="drawer-panel">
                <div className="drawer-header">
                  <span>✏️ 에이전트 수정 — {editData.name || '이름 없음'}</span>
                  <button className="btn btn-ghost" style={{ padding: '4px 8px' }} onClick={cancelEdit}>✕</button>
                </div>
                <div className="drawer-body">
                  {/* 기본 정보 */}
                  <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>기본 정보</div>
                  <div className="field-group">
                    <div className="field-label">이모지</div>
                    <input className="field-input" value={editData.emoji} onChange={(e) => updateEditData((prev) => ({ ...prev, emoji: e.target.value }))} />
                  </div>
                  <div className="field-group">
                    <div className="field-label">이름</div>
                    <input className="field-input" value={editData.name} onChange={(e) => updateEditData((prev) => ({ ...prev, name: e.target.value }))} />
                  </div>
                  <div className="field-group">
                    <div className="field-label">유형</div>
                    <select className="field-input" value={editData.type} onChange={(e) => updateEditData((prev) => ({ ...prev, type: e.target.value as AgentSchema['type'] }))}>
                      <option value="customer">가상 고객</option>
                      <option value="expert">도메인 전문가</option>
                      <option value="custom">커스텀</option>
                    </select>
                  </div>
                  <div className="field-group">
                    <div className="field-label">설명</div>
                    <textarea className="field-textarea" rows={2} value={editData.description} onChange={(e) => updateEditData((prev) => ({ ...prev, description: e.target.value }))} />
                  </div>
                  <div className="field-group">
                    <div className="field-label">태그 (쉼표 구분)</div>
                    <input className="field-input" value={editData.tags.join(', ')} onChange={(e) => updateEditData((prev) => ({ ...prev, tags: e.target.value.split(',').map((t) => t.trim()).filter(Boolean) }))} />
                  </div>

                  {editData.persona_profile ? (
                    <>
                      {/* 기본 정보 (페르소나) */}
                      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', margin: '16px 0 8px' }}>기본 정보 (페르소나)</div>
                      <div className="field-group">
                        <div className="field-label">나이</div>
                        <input className="field-input" type="number" value={editData.persona_profile.age} onChange={(e) => updateEditData((prev) => ({ ...prev, persona_profile: { ...prev.persona_profile!, age: Number(e.target.value) || 0 } }))} />
                      </div>
                      <div className="field-group">
                        <div className="field-label">성별</div>
                        <select className="field-input" value={editData.persona_profile.gender} onChange={(e) => updateEditData((prev) => ({ ...prev, persona_profile: { ...prev.persona_profile!, gender: e.target.value as NonNullable<AgentSchema['persona_profile']>['gender'] } }))}>
                          <option value="male">남성</option>
                          <option value="female">여성</option>
                          <option value="other">기타</option>
                        </select>
                      </div>
                      <div className="field-group">
                        <div className="field-label">직업</div>
                        <input className="field-input" value={editData.persona_profile.occupation} onChange={(e) => updateEditData((prev) => ({ ...prev, persona_profile: { ...prev.persona_profile!, occupation: e.target.value } }))} />
                      </div>

                      {/* 성격 & 행동 */}
                      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', margin: '16px 0 8px' }}>성격 & 행동</div>
                      <div className="field-group">
                        <div className="field-label">성격</div>
                        <input className="field-input" value={editData.persona_profile.personality} onChange={(e) => updateEditData((prev) => ({ ...prev, persona_profile: { ...prev.persona_profile!, personality: e.target.value } }))} />
                      </div>
                      <div className="field-group">
                        <div className="field-label">소비 스타일</div>
                        <textarea className="field-textarea" rows={2} value={editData.persona_profile.consumption_style} onChange={(e) => updateEditData((prev) => ({ ...prev, persona_profile: { ...prev.persona_profile!, consumption_style: e.target.value } }))} />
                      </div>
                      <div className="field-group">
                        <div className="field-label">말투</div>
                        <input className="field-input" value={editData.persona_profile.communication_style} onChange={(e) => updateEditData((prev) => ({ ...prev, persona_profile: { ...prev.persona_profile!, communication_style: e.target.value } }))} />
                      </div>

                      {/* 경험 & 니즈 */}
                      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', margin: '16px 0 8px' }}>경험 & 니즈</div>
                      <div className="field-group">
                        <div className="field-label">관련 경험</div>
                        <textarea className="field-textarea" rows={3} value={editData.persona_profile.experience} onChange={(e) => updateEditData((prev) => ({ ...prev, persona_profile: { ...prev.persona_profile!, experience: e.target.value } }))} />
                      </div>
                      <div className="field-group">
                        <div className="field-label">불만/니즈</div>
                        <textarea className="field-textarea" rows={2} value={editData.persona_profile.pain_points} onChange={(e) => updateEditData((prev) => ({ ...prev, persona_profile: { ...prev.persona_profile!, pain_points: e.target.value } }))} />
                      </div>

                      {/* AI 생성 프롬프트 미리보기 */}
                      <div className="field-group" style={{ marginTop: 8 }}>
                        <button className="btn btn-ghost w-full justify-between" onClick={() => setIsPromptPreviewOpen((prev) => !prev)}>
                          AI 생성 프롬프트 미리보기
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
                      <textarea className="field-textarea" rows={4} value={editData.system_prompt} onChange={(e) => updateEditData((prev) => ({ ...prev, system_prompt: e.target.value }))} />
                    </div>
                  )}
                </div>
                <div className="drawer-footer">
                  <button className="btn btn-primary flex-1 justify-center" onClick={saveEdit}>저장</button>
                  <button className="btn btn-secondary flex-1 justify-center" onClick={cancelEdit}>취소</button>
                </div>
              </div>
            </>
          )}

          <div className="agent-grid">
            {agents.map((agent) =>
              (
                /* ── 일반 카드 (항상 표시) ── */
                <div key={agent.id} className="agent-card" style={{ borderTop: `3px solid ${agent.color}`, paddingTop: 14 }}>
                  <div className="agent-actions">
                    {deletingId === agent.id ? (
                      <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                        <button
                          className="agent-action-btn"
                          title="삭제 확인"
                          style={{ color: 'var(--red)', fontSize: 10, padding: '2px 6px' }}
                          onClick={() => { removeAgent(agent.id); setDeletingId(null); }}
                        >
                          삭제
                        </button>
                        <button
                          className="agent-action-btn"
                          title="취소"
                          style={{ fontSize: 10, padding: '2px 6px' }}
                          onClick={() => setDeletingId(null)}
                        >
                          취소
                        </button>
                      </div>
                    ) : (
                      <>
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
                          onClick={() => setDeletingId(agent.id)}
                        >
                          ✕
                        </button>
                      </>
                    )}
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
                        <span style={{ overflow: 'hidden', display: '-webkit-box', WebkitBoxOrient: 'vertical', WebkitLineClamp: 2 }}>{agent.persona_profile.personality}</span>
                      </div>
                      <div className="agent-persona-row">
                        <span className="agent-persona-label">소비:</span>
                        <span style={{ overflow: 'hidden', display: '-webkit-box', WebkitBoxOrient: 'vertical', WebkitLineClamp: 2 }}>{agent.persona_profile.consumption_style}</span>
                      </div>
                      <div className="agent-persona-row">
                        <span className="agent-persona-label">경험:</span>
                        <span style={{ overflow: 'hidden', display: '-webkit-box', WebkitBoxOrient: 'vertical', WebkitLineClamp: 2 }}>{agent.persona_profile.experience}</span>
                      </div>
                      <div className="agent-persona-row">
                        <span className="agent-persona-label">니즈:</span>
                        <span style={{ overflow: 'hidden', display: '-webkit-box', WebkitBoxOrient: 'vertical', WebkitLineClamp: 2 }}>{agent.persona_profile.pain_points}</span>
                      </div>
                      <div className="agent-persona-row">
                        <span className="agent-persona-label">말투:</span>
                        <span style={{ overflow: 'hidden', display: '-webkit-box', WebkitBoxOrient: 'vertical', WebkitLineClamp: 1 }}>{agent.persona_profile.communication_style}</span>
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
