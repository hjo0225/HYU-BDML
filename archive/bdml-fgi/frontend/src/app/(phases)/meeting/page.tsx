'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useProject } from '@/contexts/ProjectContext';
import { fetchMeeting } from '@/lib/api';
import type { MeetingMessage, MeetingDesign } from '@/lib/types';

/* 타입 라벨 */
const TYPE_LABELS: Record<string, string> = {
  customer: '실제 패널',
  expert: '전문가',
  custom: '커스텀',
};

function buildResearchContext(project: ReturnType<typeof useProject>['project']): string {
  return [
    project.refined?.refined_background,
    project.refined?.refined_objective,
    project.marketReport?.market_overview.summary,
    project.marketReport?.implications.summary,
  ]
    .filter(Boolean)
    .join('\n');
}

export default function Phase4Page() {
  const router = useRouter();
  const {
    project,
    addMessage,
    setMeetingTopic,
    setCurrentPhase,
    startMeetingSession,
  } = useProject();

  // 상태 — 주제는 Phase 3에서 설정됨
  const [displayTopic, setDisplayTopic] = useState(project.meetingTopic ?? '');
  const [phase, setPhase] = useState<'running' | 'done'>(() =>
    project.messages.length > 0 ? 'done' : 'running',
  );
  const [error, setError] = useState<string | null>(null);
  const [speakingAgent, setSpeakingAgent] = useState<string | null>(null);
  const [startTime, setStartTime] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  // 현재 스트리밍 중인 발언의 메타 + 누적 텍스트
  const [streamingMeta, setStreamingMeta] = useState<{
    role: 'moderator' | 'agent';
    agent_id: string | null;
    agent_name: string;
    agent_emoji: string;
    color: string | null;
  } | null>(null);
  const [streamingText, setStreamingText] = useState('');
  // 회의 설계안
  const [meetingDesign, setMeetingDesign] = useState<MeetingDesign | null>(null);

  // refs
  const chatEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef(false);
  const controllerRef = useRef<AbortController | null>(null);
  const streamingTextRef = useRef('');

  // 경과 시간 타이머
  useEffect(() => {
    if (phase !== 'running' || !startTime) return;
    const id = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, [phase, startTime]);

  // 새 메시지 자동 스크롤
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [project.messages]);

  useEffect(() => {
    return () => {
      controllerRef.current?.abort();
    };
  }, []);

  // 라운드 계산 (백엔드가 질문 수 기반으로 라운드를 결정하므로 표시용)
  const agentCount = project.agents.length;
  const agentMessages = project.messages.filter((m) => m.role === 'agent').length;
  const currentRound = agentCount > 0 ? Math.ceil(agentMessages / agentCount) : 0;

  /* 경과 시간 포맷 */
  const formatElapsed = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return m > 0 ? `${m}분 ${sec}초` : `${sec}초`;
  };

  /* 회의 시작 */
  const startMeeting = useCallback(async () => {
    const meetingTopic = project.meetingTopic ?? '';
    if (!meetingTopic.trim()) {
      setError('회의 주제가 설정되지 않았습니다. 에이전트 구성 단계로 돌아가세요.');
      return;
    }
    if (!project.agents.length) {
      setError('에이전트가 없습니다. Phase 3에서 먼저 구성해주세요.');
      return;
    }

    setPhase('running');
    setMeetingDesign(null);
    startMeetingSession(meetingTopic.trim());
    setError(null);
    setSpeakingAgent(null);
    setStreamingMeta(null);
    setStreamingText('');
    streamingTextRef.current = '';
    setStartTime(Date.now());
    abortRef.current = false;
    controllerRef.current?.abort();
    controllerRef.current = new AbortController();

    const context = buildResearchContext(project);
    const panel_ids = Object.fromEntries(
      project.agents.filter((a) => a.panel_id).map((a) => [a.id, a.panel_id!]),
    );

    try {
      await fetchMeeting(
        { agents: project.agents, topic: meetingTopic, research_context: context, panel_ids },
        // onStart
        (meta) => {
          if (abortRef.current) return;
          streamingTextRef.current = '';
          setStreamingText('');
          setStreamingMeta(meta);
          setSpeakingAgent(meta.role === 'agent' ? meta.agent_id : 'moderator');
        },
        // onDelta
        (delta) => {
          if (abortRef.current) return;
          streamingTextRef.current += delta;
          setStreamingText(streamingTextRef.current);
        },
        // onEnd
        (msg) => {
          if (abortRef.current) return;
          addMessage(msg);
          setStreamingMeta(null);
          setStreamingText('');
          streamingTextRef.current = '';
        },
        // onDone
        () => {
          setStreamingMeta(null);
          setStreamingText('');
          streamingTextRef.current = '';
          setSpeakingAgent(null);
          setPhase('done');
        },
        // onTopicRefined
        (refined) => {
          if (!abortRef.current) {
            setDisplayTopic(refined);
            setMeetingTopic(refined);
          }
        },
        controllerRef.current.signal,
        // onMeetingDesign
        (design) => {
          if (!abortRef.current) setMeetingDesign(design);
        },
      );
    } catch (err) {
      if (abortRef.current) return;
      setError(err instanceof Error ? err.message : '회의 중 오류 발생');
      setStreamingMeta(null);
      setStreamingText('');
      setSpeakingAgent(null);
      setPhase('done');
    } finally {
      controllerRef.current = null;
    }
  }, [project, setMeetingTopic, startMeetingSession, addMessage]);

  // 마운트 시 자동 회의 시작 (메시지가 없을 때)
  const hasStarted = useRef(false);
  useEffect(() => {
    if (phase === 'running' && project.messages.length === 0 && !hasStarted.current && project.agents.length > 0) {
      hasStarted.current = true;
      startMeeting();
    }
  }, [phase, project.messages.length, project.agents.length, startMeeting]);

  /* 회의 종료 */
  const stopMeeting = () => {
    abortRef.current = true;
    controllerRef.current?.abort();
    controllerRef.current = null;
    setSpeakingAgent(null);
    setStreamingMeta(null);
    setStreamingText('');
    streamingTextRef.current = '';
    setPhase('done');
  };

  /* 네비게이션 */
  const goNext = () => { setCurrentPhase(5); router.push('/minutes'); };
  const goPrev = () => { setCurrentPhase(3); router.push('/agent-setup'); };

  /* 데이터 없으면 Phase 3으로 안내 */
  if (!project.agents.length) {
    return (
      <div className="card">
        <div className="card-header">
          <div className="card-title">💬 회의 시뮬레이션</div>
        </div>
        <p className="text-sm text-text-secondary mb-4">
          에이전트가 구성되지 않았습니다. 에이전트 구성 단계에서 먼저 주제와 참여자를 설정해주세요.
        </p>
        <button className="btn btn-primary" onClick={goPrev}>← 에이전트 구성으로</button>
      </div>
    );
  }

  /* ── 회의 진행 / 완료 화면 (3분할) ── */
  return (
    <div>
      <div className="meeting-layout">
        {/* ── 왼쪽: 참여자 사이드바 ── */}
        <div className="meeting-sidebar">
          <div className="meeting-sidebar-title">참여자 ({project.agents.length + 1}명)</div>

          {/* 모더레이터 */}
          <div className="sidebar-agent" style={speakingAgent === 'moderator' ? { background: 'var(--accent-light)' } : undefined}>
            <div className="sidebar-agent-dot" style={{ background: 'var(--accent)' }} />
            <div>
              <div className="sidebar-agent-name">🎙️ 모더레이터</div>
              {speakingAgent === 'moderator' ? (
                <div className="sidebar-agent-speaking">● 발언 중</div>
              ) : (
                <div className="sidebar-agent-type">AI 진행자</div>
              )}
            </div>
          </div>

          <hr style={{ border: 'none', borderTop: '1px solid var(--border-light)', margin: '8px 0' }} />

          {/* 에이전트 목록 */}
          {project.agents.map((agent) => {
            const isSpeaking = speakingAgent === agent.id;
            return (
              <div key={agent.id} className="sidebar-agent" style={isSpeaking ? { background: 'var(--accent-light)' } : undefined}>
                <div className="sidebar-agent-dot" style={{ background: agent.color }} />
                <div>
                  <div className="sidebar-agent-name">{agent.name}</div>
                  {isSpeaking ? (
                    <div className="sidebar-agent-speaking">● 발언 중</div>
                  ) : (
                    <div className="sidebar-agent-type">{TYPE_LABELS[agent.type] || agent.type}</div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* ── 중앙: 채팅 ── */}
        <div className="meeting-chat" style={{ maxHeight: 'calc(100vh - 220px)' }}>
          {/* 헤더 */}
          <div className="chat-header">
            <div className="chat-header-title">{displayTopic || 'FGI 시뮬레이션'}</div>
            {phase === 'running' ? (
              <div className="chat-header-status">
                <div className="chat-header-dot" />
                진행 중 · {formatElapsed(elapsed)} 경과
              </div>
            ) : (
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>완료 · {formatElapsed(elapsed)} 소요</div>
            )}
          </div>

          {/* 메시지 목록 */}
          <div className="chat-messages">
            {(() => {
              let modCount = 0;
              const totalModMsgs = project.messages.filter((m: MeetingMessage) => m.role === 'moderator').length;
              return project.messages.map((msg: MeetingMessage, i: number) => {
                const isLastMod = msg.role === 'moderator' && modCount === totalModMsgs - 1;
                // 마지막 모더레이터 발언(closing)에는 라운드 디바이더 표시 안 함
                const showRoundDivider = msg.role === 'moderator' && !isLastMod;
                const roundNum = modCount + 1;
                if (msg.role === 'moderator') modCount++;
                return (
                  <div key={i}>
                    {showRoundDivider && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '6px 0 14px' }}>
                        <div style={{ flex: 1, height: 1, background: 'var(--border-light)' }} />
                        <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', whiteSpace: 'nowrap' }}>
                          Round {roundNum}
                        </span>
                        <div style={{ flex: 1, height: 1, background: 'var(--border-light)' }} />
                      </div>
                    )}
                    <div className={`chat-msg ${msg.role === 'moderator' ? 'chat-msg-moderator' : ''}`}>
                      {msg.role === 'moderator' ? (
                        <div className="chat-msg-avatar">M</div>
                      ) : (
                        <div className="chat-msg-avatar" style={{ background: '#e8f4fd' }}>{msg.agent_emoji}</div>
                      )}
                      <div className="chat-msg-body">
                        <div className="chat-msg-name" style={msg.color ? { color: msg.color } : undefined}>
                          {msg.agent_name}
                        </div>
                        <div className="chat-msg-text">{msg.content}</div>
                        {msg.activated_categories && msg.activated_categories.length > 0 && (
                          <div style={{ marginTop: 6, display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                            {msg.activated_categories.map((cat, ci) => (
                              <span key={ci} style={{ fontSize: 9, background: '#E8F0FA', color: '#1B4B8C', padding: '1px 5px', borderRadius: 3, fontWeight: 500 }}>
                                {cat}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              });
            })()}

            {/* 스트리밍 중인 발언 */}
            {streamingMeta && phase === 'running' && (
              <div className={`chat-msg ${streamingMeta.role === 'moderator' ? 'chat-msg-moderator' : ''}`}>
                {streamingMeta.role === 'moderator' ? (
                  <div className="chat-msg-avatar">M</div>
                ) : (
                  <div className="chat-msg-avatar" style={{ background: '#e8f4fd' }}>{streamingMeta.agent_emoji}</div>
                )}
                <div className="chat-msg-body">
                  <div className="chat-msg-name" style={streamingMeta.color ? { color: streamingMeta.color } : undefined}>
                    {streamingMeta.agent_name}
                  </div>
                  <div className="chat-msg-text">
                    {streamingText || (
                      <span style={{ color: 'var(--text-muted)', animation: 'pulse 1.5s infinite' }}>응답을 생성하고 있습니다...</span>
                    )}
                    {streamingText && <span className="streaming-cursor" />}
                  </div>
                </div>
              </div>
            )}

            <div ref={chatEndRef} />
          </div>

          {/* 하단 컨트롤 */}
          <div className="chat-controls">
            {error && (
              <div className="mb-2 p-2.5 rounded-md text-xs" style={{ background: '#fdecea', color: 'var(--red)', width: '100%' }}>
                {error}
              </div>
            )}
            {phase === 'running' && (
              <button className="btn btn-danger" onClick={stopMeeting}>⏹ 회의 종료</button>
            )}
          </div>
        </div>

        {/* ── 오른쪽: 회의 아젠다 ── */}
        <div className="insight-panel">
          {meetingDesign ? (
            <>
              <div className="insight-title">회의 아젠다</div>

              {meetingDesign.session_objective && (
                <div className="insight-item">
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>세션 목적</div>
                  <div style={{ fontSize: 11, lineHeight: 1.5, color: 'var(--text-secondary)' }}>
                    {meetingDesign.session_objective}
                  </div>
                </div>
              )}

              {meetingDesign.key_themes.length > 0 && (
                <div className="insight-item">
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>핵심 주제</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {meetingDesign.key_themes.map((theme, ti) => (
                      <span key={ti} style={{ fontSize: 10, background: '#E8F0FA', color: '#1B4B8C', borderRadius: 4, padding: '1px 6px', fontWeight: 500 }}>
                        {theme}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {meetingDesign.discussion_questions.length > 0 && (
                <div className="insight-item">
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 6 }}>토론 질문</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {meetingDesign.discussion_questions.map((q) => (
                      <div key={q.order} style={{ padding: '6px 8px', background: 'var(--bg)', borderRadius: 5, borderLeft: '2px solid #A3C4E8' }}>
                        <div style={{ fontSize: 9, color: '#1B4B8C', fontWeight: 600, marginBottom: 2 }}>
                          Q{q.order}. {q.focus_area}
                        </div>
                        <div style={{ fontSize: 11, lineHeight: 1.4, color: 'var(--text-secondary)' }}>
                          {q.question}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {meetingDesign.moderator_notes && (
                <div className="insight-item">
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>진행 유의사항</div>
                  <div style={{ fontSize: 11, lineHeight: 1.5, color: 'var(--text-muted)', fontStyle: 'italic' }}>
                    {meetingDesign.moderator_notes}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>회의가 시작되면 아젠다가 표시됩니다.</div>
          )}
        </div>
      </div>

      {/* ── 액션 바 (완료 시) ── */}
      {phase === 'done' && project.messages.length > 0 && (
        <div className="action-bar">
          <button className="btn btn-secondary" onClick={goPrev}>← 에이전트 수정</button>
          <button className="btn btn-primary" onClick={goNext}>회의록 생성 →</button>
        </div>
      )}
    </div>
  );
}
