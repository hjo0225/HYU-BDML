'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { fetchLabChat, fetchLabJudge, fetchLabTwins } from '@/lib/api';
import type {
  LabChatTurn,
  LabConfidence,
  LabJudgeResponse,
  LabTwin,
  MemoryCitation,
} from '@/lib/types';
import CitationToggle from '@/components/lab/CitationToggle';
import JudgeVerdictCard from '@/components/lab/JudgeVerdictCard';
import { FaithfulnessBadge } from '@/components/lab/FaithfulnessBar';
import SurveyQuestionsPanel from '@/components/lab/SurveyQuestionsPanel';

const STORAGE_PREFIX = 'lab-chat-';

interface DisplayTurn extends LabChatTurn {
  id: number;
  streaming?: boolean;
  citations?: MemoryCitation[];
  confidence?: LabConfidence;
  question?: string;          // twin 턴이 응답한 사용자 질문 (judge 호출용)
  judging?: boolean;
  verdict?: LabJudgeResponse;
  judgeError?: string;
}

export default function LabTwinChatPage() {
  const params = useParams<{ twinId: string }>();
  const twinId = decodeURIComponent(params.twinId);
  const [twin, setTwin] = useState<LabTwin | null>(null);
  const [history, setHistory] = useState<DisplayTurn[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const turnIdRef = useRef(1);

  const handleProbeSelect = useCallback((question: string) => {
    setInput(question);
    textareaRef.current?.focus();
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const list = await fetchLabTwins();
        if (cancelled) return;
        const found = list.find((t) => t.twin_id === twinId);
        setTwin(found || null);
      } catch {
        // 카드 정보 없어도 채팅은 가능
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [twinId]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const raw = window.sessionStorage.getItem(STORAGE_PREFIX + twinId);
    if (!raw) return;
    try {
      const parsed = JSON.parse(raw) as DisplayTurn[];
      if (Array.isArray(parsed)) {
        setHistory(parsed);
        turnIdRef.current = parsed.reduce((m, t) => Math.max(m, t.id), 0) + 1;
      }
    } catch {
      // 파싱 실패 시 무시
    }
  }, [twinId]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const persistable = history.filter((t) => !t.streaming);
    if (persistable.length === 0) {
      window.sessionStorage.removeItem(STORAGE_PREFIX + twinId);
      return;
    }
    // judging 같은 휘발성 플래그는 저장하지 않음
    const cleaned = persistable.map(({ judging, ...rest }) => rest);
    window.sessionStorage.setItem(STORAGE_PREFIX + twinId, JSON.stringify(cleaned));
  }, [history, twinId]);

  useEffect(() => {
    messagesRef.current?.scrollTo({ top: messagesRef.current.scrollHeight, behavior: 'smooth' });
  }, [history]);

  const handleClear = () => {
    if (sending) return;
    if (!confirm('이 트윈과의 대화 기록을 모두 지울까요?')) return;
    setHistory([]);
    if (typeof window !== 'undefined') {
      window.sessionStorage.removeItem(STORAGE_PREFIX + twinId);
    }
  };

  const handleJudge = useCallback(
    async (turnId: number) => {
      const turn = history.find((t) => t.id === turnId);
      if (!turn || turn.role !== 'twin' || !turn.content || !turn.question) return;
      if (turn.judging) return;

      setHistory((prev) =>
        prev.map((t) => (t.id === turnId ? { ...t, judging: true, judgeError: undefined } : t)),
      );
      try {
        const verdict = await fetchLabJudge({
          twin_id: twinId,
          question: turn.question,
          answer: turn.content,
        });
        setHistory((prev) =>
          prev.map((t) => (t.id === turnId ? { ...t, verdict, judging: false } : t)),
        );
      } catch (e) {
        const msg = e instanceof Error ? e.message : '검증 실패';
        setHistory((prev) =>
          prev.map((t) => (t.id === turnId ? { ...t, judgeError: msg, judging: false } : t)),
        );
      }
    },
    [history, twinId],
  );

  const handleSend = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || sending) return;

    setError(null);
    setSending(true);

    const myTurn: DisplayTurn = { id: turnIdRef.current++, role: 'me', content: trimmed };
    const twinPlaceholder: DisplayTurn = {
      id: turnIdRef.current++,
      role: 'twin',
      content: '',
      streaming: true,
      question: trimmed,
    };
    setHistory((prev) => [...prev, myTurn, twinPlaceholder]);
    setInput('');

    const requestHistory: LabChatTurn[] = history.map(({ role, content }) => ({ role, content }));

    try {
      await fetchLabChat(
        { twin_id: twinId, history: requestHistory, message: trimmed },
        {
          onStart: () => {
            // placeholder는 이미 추가됨
          },
          onDelta: (delta) => {
            setHistory((prev) =>
              prev.map((t) =>
                t.id === twinPlaceholder.id
                  ? { ...t, content: (t.content || '') + delta }
                  : t,
              ),
            );
          },
          onEnd: ({ content, citations, confidence }) => {
            setHistory((prev) =>
              prev.map((t) =>
                t.id === twinPlaceholder.id
                  ? {
                      ...t,
                      content,
                      citations,
                      confidence,
                      streaming: false,
                    }
                  : t,
              ),
            );
          },
          onError: (reason, retryAfter) => {
            setHistory((prev) => prev.filter((t) => t.id !== twinPlaceholder.id));
            if (reason === 'rate_limit') {
              const hours = retryAfter ? Math.ceil(retryAfter / 3600) : 24;
              setError(`일일 메시지 한도에 도달했습니다. 약 ${hours}시간 후 다시 시도해 주세요.`);
            } else if (reason === 'twin_not_found') {
              setError('이 트윈을 찾을 수 없습니다.');
            } else {
              setError('응답 생성 중 오류가 발생했습니다. 다시 시도해 주세요.');
            }
          },
        },
      );
    } finally {
      setSending(false);
    }
  }, [input, sending, history, twinId]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="lab-chat-shell">
      <div className="lab-chat">
        <div className="lab-chat__topbar">
        <Link href="/lab/twin-chat" className="lab-chat__back">
          ← 목록
        </Link>
        <div className="lab-chat__avatar">{twin?.emoji || '🧑'}</div>
        <div className="lab-chat__title">
          <div className="lab-chat__name">
            {twin?.name || twinId}
            {twin?.faithfulness && (
              <span style={{ marginLeft: 8 }}>
                <FaithfulnessBadge faithfulness={twin.faithfulness} compact />
              </span>
            )}
          </div>
          <div className="lab-chat__sub">
            {twin
              ? [twin.age ? `${twin.age}세` : null, twin.gender, twin.occupation]
                  .filter(Boolean)
                  .join(' · ')
              : 'Twin-2K-500'}
          </div>
        </div>
        <button className="lab-chat__clear" onClick={handleClear} disabled={sending}>
          기록 초기화
        </button>
      </div>

      <div ref={messagesRef} className="lab-chat__messages">
        {history.length === 0 && (
          <div className="lab-chat__empty">
            <div className="lab-chat__empty-icon">💬</div>
            <p>먼저 인사를 건네 보세요. 트윈이 자기 경험을 바탕으로 답합니다.</p>
            <p style={{ fontSize: 11 }}>예: &ldquo;요즘 뭐 하면서 시간 보내요?&rdquo;</p>
          </div>
        )}
        {history.map((turn) => (
          <div key={turn.id} className={`lab-chat__msg lab-chat__msg--${turn.role}`}>
            <div className="lab-chat__msg-avatar">
              {turn.role === 'me' ? '나' : twin?.emoji || '🧑'}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
              <div className="lab-chat__bubble">
                {turn.content || (turn.streaming ? '...' : '')}
                {turn.streaming && turn.content && <span className="streaming-cursor" />}
              </div>
              {turn.role === 'twin' && !turn.streaming && (turn.confidence || (turn.citations && turn.citations.length > 0)) && (
                <CitationToggle
                  citations={turn.citations || []}
                  confidence={turn.confidence || 'unknown'}
                  onJudgeClick={turn.question ? () => handleJudge(turn.id) : undefined}
                  judging={turn.judging}
                />
              )}
              {turn.role === 'twin' && turn.judgeError && (
                <div className="lab-chat__error" style={{ marginTop: 6 }}>
                  {turn.judgeError}
                </div>
              )}
              {turn.role === 'twin' && turn.verdict && (
                <JudgeVerdictCard verdict={turn.verdict} />
              )}
            </div>
          </div>
        ))}
        {error && <div className="lab-chat__error">{error}</div>}
      </div>

      <div className="lab-chat__inputbar">
        <textarea
          ref={textareaRef}
          className="lab-chat__textarea"
          placeholder="메시지 입력 (Enter: 전송, Shift+Enter: 줄바꿈)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={sending}
        />
        <button
          className="lab-chat__send"
          onClick={handleSend}
          disabled={sending || !input.trim()}
        >
          {sending ? '응답 중...' : '전송'}
        </button>
      </div>
      </div>
      <SurveyQuestionsPanel
        probeQuestions={twin?.probe_questions ?? []}
        onSelect={handleProbeSelect}
        disabled={sending}
      />
    </div>
  );
}
