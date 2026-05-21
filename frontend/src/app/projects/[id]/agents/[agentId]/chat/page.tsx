'use client';

// 1:1 대화 페이지 (plan 0007) — 에이전트 1명과 SSE 스트리밍 채팅.
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';
import { AuthGuard } from '@/components/auth/AuthGuard';
import { AppShell } from '@/components/layout/AppShell';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { ChatBubble } from '@/components/chat/ChatBubble';
import { EmptyState } from '@/components/ui/EmptyState';
import { useAuth } from '@/contexts/AuthContext';
import { agents as agentsApi, conversations as convApi } from '@/lib/api';
import type { AgentDetail, ConversationTurn } from '@/lib/types';

function ChatView() {
  const params = useParams<{ id: string; agentId: string }>();
  const projectId = params.id;
  const agentId = params.agentId;
  const { token } = useAuth();

  const [agent, setAgent] = useState<AgentDetail | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [streamingText, setStreamingText] = useState('');
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // 초기 로드: 에이전트 정보 + 기존 대화(있으면 최신 1건) 복원
  useEffect(() => {
    if (!token || !agentId || !projectId) return;
    (async () => {
      try {
        const [a, convs] = await Promise.all([
          agentsApi.get(token, agentId),
          convApi.list(token, agentId),
        ]);
        setAgent(a);
        if (convs.length > 0) {
          const detail = await convApi.get(token, convs[0].id);
          setConversationId(detail.id);
          setTurns(detail.turns);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : '로드 실패');
      }
    })();
  }, [token, agentId, projectId]);

  // 새 발화·스트리밍 시 하단으로 스크롤
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [turns, streamingText]);

  const handleSend = useCallback(async () => {
    const content = input.trim();
    if (!token || !content || streaming) return;
    setError(null);
    setInput('');

    // 사용자 발화 즉시 화면 반영
    const userTurn: ConversationTurn = {
      id: `local-${Date.now()}`,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    };
    setTurns((prev) => [...prev, userTurn]);
    setStreaming(true);
    setStreamingText('');

    try {
      // 대화 세션이 없으면 첫 발화 시 생성
      let convId = conversationId;
      if (!convId) {
        const conv = await convApi.create(token, agentId);
        convId = conv.id;
        setConversationId(convId);
      }

      let acc = '';
      for await (const ev of convApi.sendMessage(token, convId, content)) {
        if (ev.type === 'delta') {
          acc += ev.delta;
          setStreamingText(acc);
        } else if (ev.type === 'end') {
          setTurns((prev) => [
            ...prev,
            { id: ev.turn_id, role: 'agent', content: ev.content, created_at: new Date().toISOString() },
          ]);
          setStreamingText('');
        } else if (ev.type === 'error') {
          setError(ev.reason);
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '전송 실패');
    } finally {
      setStreaming(false);
    }
  }, [input, token, streaming, conversationId, projectId, agentId]);

  return (
    <div className="mx-auto flex h-[calc(100vh-8rem)] max-w-3xl flex-col">
      {/* 헤더 */}
      <div className="mb-4 flex items-center gap-3">
        <Link
          href={`/projects/${projectId}/agents/${agentId}`}
          className="text-sm text-text-muted hover:text-text-primary"
        >
          ← 대시보드
        </Link>
        <div className="flex items-center gap-2">
          <span className="text-2xl">{agent?.emoji ?? '👤'}</span>
          <div>
            <p className="font-semibold text-text-primary">{agent?.display_name ?? '에이전트'}</p>
            {agent?.intro_ko && <p className="text-xs text-text-muted">{agent.intro_ko}</p>}
          </div>
        </div>
      </div>

      {/* 대화 영역 */}
      <div className="flex-1 space-y-4 overflow-y-auto rounded-xl border border-border bg-surface p-4">
        {turns.length === 0 && !streaming && (
          <EmptyState
            icon="💬"
            title="아직 대화가 없어요"
            description={`${agent?.display_name ?? '이 에이전트'}에게 첫 메시지를 보내 대화를 시작하세요.`}
          />
        )}
        {turns.map((t) => (
          <ChatBubble key={t.id} role={t.role} author={t.role === 'agent' ? agent?.display_name ?? undefined : undefined}>
            {t.content}
          </ChatBubble>
        ))}
        {streaming && (
          <ChatBubble role="agent" author={agent?.display_name ?? undefined}>
            {streamingText || '…'}
          </ChatBubble>
        )}
        <div ref={bottomRef} />
      </div>

      {error && <p className="mt-2 text-sm text-error">{error}</p>}

      {/* 입력 */}
      <form
        className="mt-4 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void handleSend();
        }}
      >
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="메시지를 입력하세요…"
          disabled={streaming}
          className="flex-1"
        />
        <Button type="submit" loading={streaming} disabled={!input.trim()}>
          전송
        </Button>
      </form>
    </div>
  );
}

export default function ChatPage() {
  return (
    <AuthGuard>
      <AppShell>
        <ChatView />
      </AppShell>
    </AuthGuard>
  );
}
