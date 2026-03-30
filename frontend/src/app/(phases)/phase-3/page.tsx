'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useProject } from '@/contexts/ProjectContext';
import { fetchAgents } from '@/lib/api';
import type { AgentSchema } from '@/lib/types';

/* 타입 라벨 매핑 */
const TYPE_LABELS: Record<string, string> = {
  customer: '가상 고객',
  expert: '도메인 전문가',
  custom: '커스텀',
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
};

const MAX_AGENTS = 8;

export default function Phase3Page() {
  const router = useRouter();
  const { project, setAgents, setCurrentPhase } = useProject();

  // 상태
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editData, setEditData] = useState<AgentSchema | null>(null);
  const [addMode, setAddMode] = useState(false);
  const [newAgent, setNewAgent] = useState<AgentSchema>({ ...EMPTY_AGENT });

  const agents = project.agents;
  const hasAgents = agents.length > 0;

  /* AI 에이전트 추천 요청 */
  const requestRecommend = useCallback(async () => {
    if (!project.brief || !project.refined || !project.marketReport) {
      setError('연구 정보와 시장조사가 필요합니다. 이전 단계를 먼저 완료해주세요.');
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
    } catch (err) {
      setError(err instanceof Error ? err.message : '에이전트 추천 중 오류 발생');
    } finally {
      setLoading(false);
    }
  }, [project.brief, project.refined, project.marketReport, setAgents]);

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
    setAgents(agents.map((a) => (a.id === editData.id ? editData : a)));
    setEditingId(null);
    setEditData(null);
  };

  /* 편집 취소 */
  const cancelEdit = () => {
    setEditingId(null);
    setEditData(null);
  };

  /* 에이전트 추가 */
  const addAgent = () => {
    const id = `agent-${Date.now()}`;
    const created: AgentSchema = { ...newAgent, id };
    setAgents([...agents, created]);
    setAddMode(false);
    setNewAgent({ ...EMPTY_AGENT });
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
  if (!project.brief || !project.refined || !project.marketReport) {
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
          <>
            <div className="text-xs font-medium mb-2" style={{ color: 'var(--blue)' }}>
              ⏳ AI가 에이전트를 구성하고 있습니다...
            </div>
            <div className="progress-bar-wrap">
              <div
                className="progress-bar-fill"
                style={{ width: '70%', animation: 'skeleton-pulse 1.5s infinite' }}
              />
            </div>
          </>
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
                      onChange={(e) => setEditData({ ...editData, emoji: e.target.value })}
                    />
                  </div>
                  <div className="field-group">
                    <div className="field-label">이름</div>
                    <input
                      className="field-input"
                      value={editData.name}
                      onChange={(e) => setEditData({ ...editData, name: e.target.value })}
                    />
                  </div>
                  <div className="field-group">
                    <div className="field-label">유형</div>
                    <select
                      className="field-input"
                      value={editData.type}
                      onChange={(e) =>
                        setEditData({ ...editData, type: e.target.value as AgentSchema['type'] })
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
                      onChange={(e) => setEditData({ ...editData, description: e.target.value })}
                    />
                  </div>
                  <div className="field-group">
                    <div className="field-label">태그 (쉼표 구분)</div>
                    <input
                      className="field-input"
                      value={editData.tags.join(', ')}
                      onChange={(e) =>
                        setEditData({
                          ...editData,
                          tags: e.target.value.split(',').map((t) => t.trim()).filter(Boolean),
                        })
                      }
                    />
                  </div>
                  <div className="field-group">
                    <div className="field-label">시스템 프롬프트</div>
                    <textarea
                      className="field-textarea"
                      rows={4}
                      value={editData.system_prompt}
                      onChange={(e) => setEditData({ ...editData, system_prompt: e.target.value })}
                    />
                  </div>
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
                  <div className="agent-desc">{agent.description}</div>
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
                    placeholder="예: 김서연 (28세)"
                  />
                </div>
                <div className="field-group">
                  <div className="field-label">유형</div>
                  <select
                    className="field-input"
                    value={newAgent.type}
                    onChange={(e) =>
                      setNewAgent({ ...newAgent, type: e.target.value as AgentSchema['type'] })
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
                      setNewAgent({ ...EMPTY_AGENT });
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
