'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useProject } from '@/contexts/ProjectContext';
import { fetchAgentsStreamV2 } from '@/lib/api';
import type { AgentBuildProgressEvent } from '@/lib/api';
import type { AgentSchema, AgentMode } from '@/lib/types';
import { buildSystemPromptFromPersona } from '@/lib/persona';

/* 타입 라벨 매핑 */
const TYPE_LABELS: Record<string, string> = {
  customer: '실제 패널',
  expert: '도메인 전문가',
  custom: '커스텀',
};

const GENDER_LABELS: Record<'male' | 'female' | 'other', string> = {
  male: '남성',
  female: '여성',
  other: '',
};

/* 커스텀 에이전트 추가용 빈 템플릿 */
const EMPTY_AGENT: AgentSchema = {
  id: '',
  type: 'custom',
  name: '',
  emoji: '👤',
  description: '',
  tags: [],
  system_prompt: '',
  color: '#2E6DB4',
};

const MAX_AGENTS = 8;

type SetupStep = 'topic' | 'mode' | 'agents';

export default function Phase3Page() {
  const router = useRouter();
  const {
    project, setAgents, setAgentMode, setMeetingTopic,
    setCurrentPhase, resetAfterAgentsChange,
  } = useProject();

  /* 위저드 상태 — 에이전트+주제 모두 있으면 agents, 주제만 없으면 topic부터 */
  const [setupStep, setSetupStep] = useState<SetupStep>(
    project.agents.length > 0 && project.meetingTopic ? 'agents' : 'topic',
  );
  const [localTopic, setLocalTopic] = useState(project.meetingTopic ?? '');
  const [selectedMode, setSelectedMode] = useState<AgentMode>(
    (project.agentMode as AgentMode) ?? 'rag',
  );

  const [loading, setLoading] = useState(false);
  const [buildProgress, setBuildProgress] = useState<AgentBuildProgressEvent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editData, setEditData] = useState<AgentSchema | null>(null);
  const [addMode, setAddMode] = useState(false);
  const [newAgent, setNewAgent] = useState<AgentSchema>({ ...EMPTY_AGENT });

  const agents = project.agents;
  const hasAgents = agents.length > 0;

  /* 에이전트 생성 요청 (RAG / LLM 통합) */
  const requestRecommend = useCallback(async () => {
    if (!project.brief || !project.refined || !project.marketReport) {
      setError('시장조사가 필요합니다. 이전 단계를 먼저 완료해주세요.');
      return;
    }
    setLoading(true);
    setBuildProgress(null);
    setError(null);
    try {
      await fetchAgentsStreamV2(
        {
          brief: project.brief,
          refined: project.refined,
          report: project.marketReport,
          topic: localTopic,
          mode: selectedMode,
        },
        (event) => setBuildProgress(event),
        (agents) => {
          resetAfterAgentsChange(agents);
          setAgentMode(selectedMode);
          setMeetingTopic(localTopic);
          setLoading(false);
          setBuildProgress(null);
          setSetupStep('agents');
        },
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : '에이전트 생성 중 오류 발생');
      setLoading(false);
      setBuildProgress(null);
    }
  }, [project.brief, project.refined, project.marketReport, localTopic, selectedMode, resetAfterAgentsChange, setAgentMode, setMeetingTopic]);

  /* 에이전트 삭제 */
  const removeAgent = (id: string) => {
    setAgents(agents.filter((a) => a.id !== id));
  };

  /* 편집 시작 */
  const startEdit = (agent: AgentSchema) => {
    setEditingId(agent.id);
    setEditData({ ...agent });
  };

  /* 편집 저장 */
  const saveEdit = () => {
    if (!editData) return;
    let saved = editData;
    if (!editData.demographics && editData.persona_profile) {
      saved = {
        ...editData,
        system_prompt: buildSystemPromptFromPersona(editData.name, editData.type, editData.persona_profile),
      };
    }
    setAgents(agents.map((a) => (a.id === saved.id ? saved : a)));
    setEditingId(null);
    setEditData(null);
  };

  /* 편집 취소 */
  const cancelEdit = () => {
    setEditingId(null);
    setEditData(null);
  };

  /* 커스텀 에이전트 추가 */
  const addAgent = () => {
    const id = `agent-${Date.now()}`;
    setAgents([...agents, { ...newAgent, id }]);
    setAddMode(false);
    setNewAgent({ ...EMPTY_AGENT });
  };

  /* 네비게이션 */
  const goNext = () => { setCurrentPhase(4); router.push('/meeting'); };
  const goPrev = () => { setCurrentPhase(2); router.push('/market-research'); };

  /* 데이터 없으면 Phase 2로 안내 */
  if (!project.refined || !project.marketReport) {
    return (
      <div className="card">
        <div className="card-header">
          <div className="card-title">💬 주제 · 에이전트 구성</div>
        </div>
        <p className="text-sm text-text-secondary mb-4">
          시장조사가 완료되지 않았습니다. Phase 2에서 먼저 시장조사를 수행해주세요.
        </p>
        <button className="btn btn-primary" onClick={goPrev}>← 시장조사로 이동</button>
      </div>
    );
  }

  return (
    <div>
      {/* ═══════════════════════════════════════════════════════════════════ */}
      {/* Step 1: 회의 주제 입력                                           */}
      {/* ═══════════════════════════════════════════════════════════════════ */}
      {setupStep === 'topic' && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">💬 회의 주제 설정</div>
          </div>
          <p className="text-xs text-text-secondary mb-4">
            FGI에서 논의할 핵심 주제를 입력하세요. 주제에 맞춰 최적의 참여자를 구성합니다.
          </p>

          {/* 연구 정보 요약 카드 */}
          <div style={{ background: '#f7f8fa', borderRadius: 8, padding: '12px 14px', marginBottom: 16, fontSize: 12, lineHeight: 1.7, color: 'var(--text-secondary)' }}>
            <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>연구 배경</div>
            <div style={{ overflow: 'hidden', display: '-webkit-box', WebkitBoxOrient: 'vertical', WebkitLineClamp: 3 }}>
              {project.refined?.refined_background || project.brief?.background || '—'}
            </div>
            <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginTop: 8, marginBottom: 4 }}>연구 목적</div>
            <div style={{ overflow: 'hidden', display: '-webkit-box', WebkitBoxOrient: 'vertical', WebkitLineClamp: 2 }}>
              {project.refined?.refined_objective || project.brief?.objective || '—'}
            </div>
          </div>

          <div className="field-group">
            <div className="field-label">회의 주제</div>
            <textarea
              className="field-textarea"
              rows={3}
              value={localTopic}
              onChange={(e) => setLocalTopic(e.target.value)}
              placeholder="예: 20-30대 직장인의 건강기능식품 구매 결정 요인과 브랜드 인식"
            />
          </div>

          <div className="action-bar" style={{ marginTop: 16 }}>
            <button className="btn btn-secondary" onClick={goPrev}>← 시장조사 수정</button>
            <button
              className="btn btn-primary"
              onClick={() => {
                setMeetingTopic(localTopic.trim());
                setSetupStep('mode');
              }}
              disabled={!localTopic.trim()}
            >
              다음: 방식 선택 →
            </button>
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════ */}
      {/* Step 2: 모드 선택 (RAG 패널 / LLM 가상)                         */}
      {/* ═══════════════════════════════════════════════════════════════════ */}
      {setupStep === 'mode' && !loading && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">🤖 참여자 구성 방식</div>
          </div>
          <p className="text-xs text-text-secondary mb-2">
            주제: <strong>{localTopic}</strong>
          </p>
          <p className="text-xs text-text-secondary mb-4">
            FGI 참여자를 어떤 방식으로 구성할지 선택하세요.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
            {/* RAG 패널 카드 */}
            <div
              onClick={() => setSelectedMode('rag')}
              style={{
                padding: '20px 16px',
                borderRadius: 10,
                border: selectedMode === 'rag' ? '2px solid #1B4B8C' : '2px solid #e0e0e0',
                background: selectedMode === 'rag' ? '#f0f5fb' : '#fff',
                cursor: 'pointer',
                transition: 'all 0.15s',
                position: 'relative',
              }}
            >
              {selectedMode === 'rag' && (
                <span style={{ position: 'absolute', top: 8, right: 10, fontSize: 9, background: '#1B4B8C', color: '#fff', padding: '2px 8px', borderRadius: 10, fontWeight: 600 }}>
                  추천
                </span>
              )}
              <div style={{ fontSize: 28, marginBottom: 8 }}>📊</div>
              <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 6, color: 'var(--text-primary)' }}>
                실제 패널 데이터 기반
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                500명의 실제 소비자 패널에서 주제 관련성과 클러스터 다양성을 고려해 최적 참여자를 선정합니다.
              </div>
            </div>

            {/* LLM 가상 카드 */}
            <div
              onClick={() => setSelectedMode('llm')}
              style={{
                padding: '20px 16px',
                borderRadius: 10,
                border: selectedMode === 'llm' ? '2px solid #1B4B8C' : '2px solid #e0e0e0',
                background: selectedMode === 'llm' ? '#f0f5fb' : '#fff',
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
            >
              <div style={{ fontSize: 28, marginBottom: 8 }}>🤖</div>
              <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 6, color: 'var(--text-primary)' }}>
                LLM 가상 에이전트
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                시장조사 결과를 기반으로 AI가 가상의 소비자 페르소나를 자동 생성합니다.
              </div>
            </div>
          </div>

          <div className="action-bar">
            <button className="btn btn-secondary" onClick={() => setSetupStep('topic')}>← 주제 수정</button>
            <button className="btn btn-primary" onClick={requestRecommend}>
              에이전트 생성 시작 →
            </button>
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════ */}
      {/* 로딩 상태 (모드 선택 후 생성 중)                                  */}
      {/* ═══════════════════════════════════════════════════════════════════ */}
      {loading && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">🤖 에이전트 구성</div>
          </div>
          <div className="spinner-wrap">
            <div className="spinner" />
            <div className="spinner-text">
              {buildProgress?.message || (selectedMode === 'rag'
                ? '실제 패널 데이터를 기반으로 참여자를 선정하고 있습니다...'
                : 'LLM이 가상 에이전트를 생성하고 있습니다...'
              )}
            </div>
            {buildProgress && buildProgress.total > 0 && buildProgress.step !== 'selecting' && (
              <div style={{ marginTop: 8, width: '100%', maxWidth: 260 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>
                  <span>{buildProgress.step === 'done' ? '완료' : '진행 중'}</span>
                  <span>{buildProgress.current}/{buildProgress.total}</span>
                </div>
                <div style={{ height: 4, background: '#e0e0e0', borderRadius: 2 }}>
                  <div style={{ height: '100%', background: '#1B4B8C', borderRadius: 2, width: `${(buildProgress.current / buildProgress.total) * 100}%`, transition: 'width 0.3s' }} />
                </div>
              </div>
            )}
          </div>
          {error && (
            <div className="mb-3 p-2.5 rounded-md text-xs" style={{ background: '#fdecea', color: 'var(--red)', marginTop: 12 }}>
              <div>{error}</div>
              <button className="btn btn-ghost text-[11px] mt-1" style={{ color: 'var(--red)' }} onClick={requestRecommend}>
                다시 시도
              </button>
            </div>
          )}
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════ */}
      {/* Step 3: 에이전트 결과 + 편집                                      */}
      {/* ═══════════════════════════════════════════════════════════════════ */}
      {setupStep === 'agents' && hasAgents && !loading && (
        <>
          {/* 헤더 카드 */}
          <div className="card">
            <div className="card-header" style={{ marginBottom: 0 }}>
              <div className="card-title">
                🤖 에이전트 구성
                <span className="badge" style={{ background: '#f0f7ee', color: 'var(--green)' }}>
                  {agents.length}명
                </span>
                <span className="badge" style={{ background: '#E8F0FA', color: '#1B4B8C', marginLeft: 4, fontSize: 10 }}>
                  {project.agentMode === 'rag' ? '📊 패널 기반' : '🤖 LLM 생성'}
                </span>
              </div>
              <button className="btn btn-ghost text-[11px]" onClick={() => setSetupStep('topic')} disabled={loading}>
                🔄 처음부터 다시
              </button>
            </div>
            {project.meetingTopic && (
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 8 }}>
                주제: <strong>{project.meetingTopic}</strong>
              </div>
            )}
          </div>

          {/* 추천 배너 */}
          <div className="recommend-banner">
            {project.agentMode === 'rag'
              ? '📊 데이터 기반 패널 선정 완료: 주제 관련성과 클러스터 다양성을 고려해 참여자를 구성했습니다.'
              : '🤖 가상 에이전트 생성 완료: 시장조사 결과 기반으로 참여자 페르소나를 구성했습니다.'
            }
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

                  {/* 편집 가능 필드 */}
                  <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>기본 정보</div>
                  <div className="field-group">
                    <div className="field-label">이모지</div>
                    <input className="field-input" value={editData.emoji} onChange={(e) => setEditData({ ...editData, emoji: e.target.value })} />
                  </div>
                  <div className="field-group">
                    <div className="field-label">이름</div>
                    <input className="field-input" value={editData.name} onChange={(e) => setEditData({ ...editData, name: e.target.value })} />
                  </div>
                  <div className="field-group">
                    <div className="field-label">설명</div>
                    <textarea className="field-textarea" rows={2} value={editData.description} onChange={(e) => setEditData({ ...editData, description: e.target.value })} />
                  </div>
                  <div className="field-group">
                    <div className="field-label">태그 (쉼표 구분)</div>
                    <input className="field-input" value={editData.tags.join(', ')} onChange={(e) => setEditData({ ...editData, tags: e.target.value.split(',').map((t) => t.trim()).filter(Boolean) })} />
                  </div>

                  {/* ── 데이터 기반 에이전트: 읽기 전용 인구통계 + 메모리 ── */}
                  {editData.demographics && (
                    <>
                      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', margin: '16px 0 8px', display: 'flex', alignItems: 'center', gap: 6 }}>
                        인구통계
                        <span style={{ fontSize: 9, background: '#f0f0f0', color: 'var(--text-muted)', padding: '1px 5px', borderRadius: 3, fontWeight: 500, textTransform: 'none', letterSpacing: 0 }}>읽기 전용</span>
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 12px', marginBottom: 12 }}>
                        {([
                          ['나이대', editData.demographics.age_group],
                          ['성별', editData.demographics.gender],
                          ['직업', editData.demographics.occupation],
                          ['지역', editData.demographics.region],
                        ] as [string, string][]).map(([label, value]) => (
                          <div key={label} style={{ padding: '6px 8px', background: '#f7f8fa', borderRadius: 4 }}>
                            <div style={{ fontSize: 9, color: 'var(--text-muted)', marginBottom: 2 }}>{label}</div>
                            <div style={{ fontSize: 12, fontWeight: 500 }}>{value || '—'}</div>
                          </div>
                        ))}
                      </div>

                      {editData.memories && editData.memories.length > 0 && (
                        <>
                          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', margin: '4px 0 8px', display: 'flex', alignItems: 'center', gap: 6 }}>
                            메모리 ({editData.memories.length}개)
                            <span style={{ fontSize: 9, background: '#f0f0f0', color: 'var(--text-muted)', padding: '1px 5px', borderRadius: 3, fontWeight: 500, textTransform: 'none', letterSpacing: 0 }}>읽기 전용</span>
                          </div>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                            {editData.memories.map((m, i) => (
                              <div
                                key={i}
                                style={{
                                  padding: '7px 10px',
                                  background: '#f7f8fa',
                                  borderRadius: 6,
                                  borderLeft: `3px solid ${m.importance >= 7 ? '#1B4B8C' : m.importance >= 4 ? '#A3C4E8' : '#E0E0E0'}`,
                                }}
                              >
                                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                                  <div style={{ flex: 1, height: 3, background: '#e0e0e0', borderRadius: 2 }}>
                                    <div style={{ width: `${m.importance * 10}%`, height: '100%', background: '#1B4B8C', borderRadius: 2 }} />
                                  </div>
                                  <span style={{ fontSize: 9, color: 'var(--text-muted)', flexShrink: 0 }}>{m.importance}/10</span>
                                </div>
                                <div style={{ fontSize: 11, lineHeight: 1.5, color: 'var(--text-secondary)' }}>{m.text}</div>
                              </div>
                            ))}
                          </div>
                        </>
                      )}
                    </>
                  )}

                  {/* ── 기존 LLM 페르소나 에이전트 (하위 호환) ── */}
                  {!editData.demographics && editData.persona_profile && (
                    <>
                      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', margin: '16px 0 8px' }}>페르소나</div>
                      <div className="field-group">
                        <div className="field-label">나이</div>
                        <input className="field-input" type="number" value={editData.persona_profile.age} onChange={(e) => setEditData({ ...editData, persona_profile: { ...editData.persona_profile!, age: Number(e.target.value) || 0 } })} />
                      </div>
                      <div className="field-group">
                        <div className="field-label">직업</div>
                        <input className="field-input" value={editData.persona_profile.occupation} onChange={(e) => setEditData({ ...editData, persona_profile: { ...editData.persona_profile!, occupation: e.target.value } })} />
                      </div>
                      <div className="field-group">
                        <div className="field-label">성격</div>
                        <input className="field-input" value={editData.persona_profile.personality} onChange={(e) => setEditData({ ...editData, persona_profile: { ...editData.persona_profile!, personality: e.target.value } })} />
                      </div>
                      <div className="field-group">
                        <div className="field-label">소비 스타일</div>
                        <textarea className="field-textarea" rows={2} value={editData.persona_profile.consumption_style} onChange={(e) => setEditData({ ...editData, persona_profile: { ...editData.persona_profile!, consumption_style: e.target.value } })} />
                      </div>
                      <div className="field-group">
                        <div className="field-label">관련 경험</div>
                        <textarea className="field-textarea" rows={3} value={editData.persona_profile.experience} onChange={(e) => setEditData({ ...editData, persona_profile: { ...editData.persona_profile!, experience: e.target.value } })} />
                      </div>
                      <div className="field-group">
                        <div className="field-label">불만/니즈</div>
                        <textarea className="field-textarea" rows={2} value={editData.persona_profile.pain_points} onChange={(e) => setEditData({ ...editData, persona_profile: { ...editData.persona_profile!, pain_points: e.target.value } })} />
                      </div>
                      <div className="field-group">
                        <div className="field-label">말투</div>
                        <input className="field-input" value={editData.persona_profile.communication_style} onChange={(e) => setEditData({ ...editData, persona_profile: { ...editData.persona_profile!, communication_style: e.target.value } })} />
                      </div>
                    </>
                  )}

                  {/* ── 커스텀 에이전트: 시스템 프롬프트 직접 편집 ── */}
                  {!editData.demographics && !editData.persona_profile && (
                    <div className="field-group" style={{ marginTop: 8 }}>
                      <div className="field-label">시스템 프롬프트</div>
                      <textarea className="field-textarea" rows={4} value={editData.system_prompt} onChange={(e) => setEditData({ ...editData, system_prompt: e.target.value })} />
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

          {/* ── 에이전트 그리드 ── */}
          <div className="agent-grid">
            {agents.map((agent) => {
              const hasDemographics = !!agent.demographics;
              const hasPersona = !!agent.persona_profile;
              const memCount = agent.memory_count ?? agent.memories?.length ?? 0;

              return (
                <div key={agent.id} className="agent-card" style={{ borderTop: `3px solid ${agent.color}`, paddingTop: 14 }}>
                  <div className="agent-actions">
                    {deletingId === agent.id ? (
                      <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                        <button className="agent-action-btn" style={{ color: 'var(--red)', fontSize: 10, padding: '2px 6px' }} onClick={() => { removeAgent(agent.id); setDeletingId(null); }}>삭제</button>
                        <button className="agent-action-btn" style={{ fontSize: 10, padding: '2px 6px' }} onClick={() => setDeletingId(null)}>취소</button>
                      </div>
                    ) : (
                      <>
                        <button className="agent-action-btn" title="수정" onClick={() => startEdit(agent)}>✏️</button>
                        <button className="agent-action-btn" title="삭제" onClick={() => setDeletingId(agent.id)}>✕</button>
                      </>
                    )}
                  </div>

                  <div className={`agent-avatar avatar-${agent.type}`}>{agent.emoji}</div>
                  <div className="agent-name">{agent.name}</div>
                  <div className={`agent-type type-${agent.type}`}>
                    {TYPE_LABELS[agent.type] || agent.type}
                  </div>

                  {/* 인구통계 + 메모리 배지 (데이터 기반 에이전트) */}
                  {hasDemographics ? (
                    <div className="agent-persona">
                      <div className="agent-persona-meta">
                        <span>{agent.demographics!.age_group}</span>
                        <span className="agent-persona-separator">·</span>
                        <span>{agent.demographics!.gender}</span>
                        <span className="agent-persona-separator">·</span>
                        <span>{agent.demographics!.occupation}</span>
                        {agent.demographics!.region && (
                          <>
                            <span className="agent-persona-separator">·</span>
                            <span>{agent.demographics!.region}</span>
                          </>
                        )}
                      </div>
                      {memCount > 0 && (
                        <div style={{ marginTop: 8 }}>
                          <span style={{ fontSize: 10, background: '#E8F0FA', color: '#1B4B8C', padding: '3px 8px', borderRadius: 10, fontWeight: 600 }}>
                            🧠 {memCount}개 메모리
                          </span>
                        </div>
                      )}
                    </div>
                  ) : hasPersona ? (
                    /* 기존 LLM 페르소나 (하위 호환) */
                    <div className="agent-persona">
                      <div className="agent-persona-meta">
                        <span>{agent.persona_profile!.age}세</span>
                        {GENDER_LABELS[agent.persona_profile!.gender] && (
                          <>
                            <span className="agent-persona-separator">·</span>
                            <span>{GENDER_LABELS[agent.persona_profile!.gender]}</span>
                          </>
                        )}
                        <span className="agent-persona-separator">·</span>
                        <span>{agent.persona_profile!.occupation}</span>
                      </div>
                      <div className="agent-persona-row">
                        <span className="agent-persona-label">성격:</span>
                        <span style={{ overflow: 'hidden', display: '-webkit-box', WebkitBoxOrient: 'vertical', WebkitLineClamp: 2 }}>{agent.persona_profile!.personality}</span>
                      </div>
                      <div className="agent-persona-row">
                        <span className="agent-persona-label">소비:</span>
                        <span style={{ overflow: 'hidden', display: '-webkit-box', WebkitBoxOrient: 'vertical', WebkitLineClamp: 2 }}>{agent.persona_profile!.consumption_style}</span>
                      </div>
                    </div>
                  ) : (
                    <div className="agent-desc">{agent.description || agent.system_prompt}</div>
                  )}

                  <div className="agent-tags">
                    {agent.tags.map((tag) => (
                      <span key={tag} className="agent-tag">{tag}</span>
                    ))}
                  </div>
                </div>
              );
            })}

            {/* 커스텀 에이전트 추가 카드 */}
            {agents.length < MAX_AGENTS && !addMode && (
              <div className="agent-add-card" onClick={() => setAddMode(true)}>
                <span style={{ fontSize: 20 }}>+</span>
                <span>에이전트 추가</span>
                <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>최대 {MAX_AGENTS}명</span>
              </div>
            )}

            {/* 추가 입력 카드 (커스텀 전용) */}
            {addMode && (
              <div className="agent-card" style={{ borderColor: 'var(--accent)' }}>
                <div className="field-group">
                  <div className="field-label">이모지</div>
                  <input className="field-input" value={newAgent.emoji} onChange={(e) => setNewAgent({ ...newAgent, emoji: e.target.value })} />
                </div>
                <div className="field-group">
                  <div className="field-label">이름</div>
                  <input className="field-input" value={newAgent.name} onChange={(e) => setNewAgent({ ...newAgent, name: e.target.value })} placeholder="예: 김서연" />
                </div>
                <div className="field-group">
                  <div className="field-label">설명</div>
                  <textarea className="field-textarea" rows={3} value={newAgent.description} onChange={(e) => setNewAgent({ ...newAgent, description: e.target.value })} placeholder="에이전트 설명을 입력하세요" />
                </div>
                <div className="field-group">
                  <div className="field-label">태그 (쉼표 구분)</div>
                  <input className="field-input" value={newAgent.tags.join(', ')} onChange={(e) => setNewAgent({ ...newAgent, tags: e.target.value.split(',').map((t) => t.trim()).filter(Boolean) })} placeholder="태그1, 태그2" />
                </div>
                <div className="field-group">
                  <div className="field-label">시스템 프롬프트</div>
                  <textarea className="field-textarea" rows={4} value={newAgent.system_prompt} onChange={(e) => setNewAgent({ ...newAgent, system_prompt: e.target.value })} placeholder="에이전트의 페르소나를 상세히 작성하세요" />
                </div>
                <div className="flex gap-2 mt-2">
                  <button className="btn btn-primary flex-1 justify-center" onClick={addAgent} disabled={!newAgent.name.trim()}>추가</button>
                  <button className="btn btn-secondary flex-1 justify-center" onClick={() => { setAddMode(false); setNewAgent({ ...EMPTY_AGENT }); }}>취소</button>
                </div>
              </div>
            )}
          </div>

          {/* ── 액션 바 ── */}
          <div className="action-bar">
            <button className="btn btn-secondary" onClick={() => setSetupStep('topic')}>← 주제 · 방식 수정</button>
            <button className="btn btn-primary" onClick={goNext}>회의 시작 →</button>
          </div>
        </>
      )}
    </div>
  );
}
