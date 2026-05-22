'use client';

// 1:1 채팅 (plan 0015) — 메신저형. 좌측 연락처(저장한 AI 소비자) + 우측 대화창.
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';
import { AuthGuard } from '@/components/auth/AuthGuard';
import { AppShell } from '@/components/layout/AppShell';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { EmptyState } from '@/components/ui/EmptyState';
import { PageContainer } from '@/components/layout/PageContainer';
import { PageHeader } from '@/components/layout/PageHeader';
import { ChatBubble } from '@/components/chat/ChatBubble';
import { useAuth } from '@/contexts/AuthContext';
import { useProjectContext } from '@/contexts/ProjectContext';
import { agents as agentsApi, conversations as convApi } from '@/lib/api';
import type { Agent, ConversationTurn } from '@/lib/types';

function ChatMessengerView() {
  const params = useParams<{ id: string }>();
  const projectId = params?.id;
  const { token } = useAuth();
  const { selectedAgentIds } = useProjectContext();

  const [contacts, setContacts] = useState<Agent[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [streamingText, setStreamingText] = useState('');
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const active = contacts.find((c) => c.id === activeId) ?? null;

  // 저장한 선택 → 연락처 목록(선택 순서 보존).
  useEffect(() => {
    if (!token || !projectId) return;
    if (selectedAgentIds.length === 0) { setContacts([]); setActiveId(null); return; }
    agentsApi.list(token, projectId, { limit: 100 })
      .then((all) => {
        const byId = new Map(all.map((a) => [a.id, a]));
        const sel = selectedAgentIds.map((id) => byId.get(id)).filter((a): a is Agent => !!a);
        setContacts(sel);
        setActiveId((prev) => (prev && sel.some((a) => a.id === prev) ? prev : sel[0]?.id ?? null));
      })
      .catch(() => setContacts([]));
  }, [token, projectId, selectedAgentIds]);

  // 활성 연락처 변경 → 기존 대화 복원.
  useEffect(() => {
    if (!token || !activeId) return;
    setTurns([]); setConversationId(null); setStreamingText(''); setError(null);
    (async () => {
      try {
        const convs = await convApi.list(token, activeId);
        if (convs.length > 0) {
          const d = await convApi.get(token, convs[0].id);
          setConversationId(d.id);
          setTurns(d.turns);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : '대화 로드 실패');
      }
    })();
  }, [token, activeId]);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [turns, streamingText]);

  const handleSend = useCallback(async () => {
    const content = input.trim();
    if (!token || !activeId || !content || streaming) return;
    setError(null);
    setInput('');
    setTurns((prev) => [...prev, { id: `local-${Date.now()}`, role: 'user', content, created_at: new Date().toISOString() }]);
    setStreaming(true);
    setStreamingText('');
    try {
      let convId = conversationId;
      if (!convId) {
        const conv = await convApi.create(token, activeId);
        convId = conv.id;
        setConversationId(convId);
      }
      let acc = '';
      for await (const ev of convApi.sendMessage(token, convId, content)) {
        if (ev.type === 'delta') { acc += ev.delta; setStreamingText(acc); }
        else if (ev.type === 'end') {
          setTurns((prev) => [...prev, { id: ev.turn_id, role: 'agent', content: ev.content, created_at: new Date().toISOString() }]);
          setStreamingText('');
        } else if (ev.type === 'error') { setError(ev.reason); }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '전송 실패');
    } finally {
      setStreaming(false);
    }
  }, [input, token, activeId, streaming, conversationId]);

  return (
    <PageContainer width="wide">
      <PageHeader
        title="1:1 채팅"
        subtitle="저장한 AI 소비자와 메신저처럼 대화하며 성향을 깊이 들여다봅니다."
        backHref={`/projects/${projectId}`}
        backLabel="프로젝트 개요"
      />

      {contacts.length === 0 ? (
        <EmptyState
          icon="💬"
          title="대화할 AI 소비자가 없습니다"
          description="'AI 소비자' 탭에서 대화할 소비자를 선택·저장하세요."
          action={<Button href={`/projects/${projectId}/agents`} variant="primary" size="sm">AI 소비자로 이동 →</Button>}
        />
      ) : (
        <div className="flex h-[calc(100vh-14rem)] overflow-hidden rounded-2xl border border-border bg-surface">
          {/* 연락처 목록 */}
          <aside className="w-56 shrink-0 overflow-y-auto border-r border-border">
            <p className="px-4 py-3 text-2xs font-semibold uppercase tracking-wider text-text-muted">
              참여자 {contacts.length}명
            </p>
            {contacts.map((c) => {
              const on = c.id === activeId;
              return (
                <button
                  key={c.id}
                  onClick={() => setActiveId(c.id)}
                  className={`flex w-full items-center gap-2.5 px-4 py-2.5 text-left transition-colors ${
                    on ? 'bg-ditto-indigo-light' : 'hover:bg-ditto-indigo-light/50'
                  }`}
                >
                  <span className="text-xl leading-none">{c.emoji || '👤'}</span>
                  <span className="min-w-0 flex-1">
                    <span className={`block truncate text-sm font-medium ${on ? 'text-ditto-indigo' : 'text-text-primary'}`}>
                      {c.display_name || '에이전트'}
                    </span>
                    {(c.age_range || c.gender) && (
                      <span className="block truncate text-2xs text-text-muted">
                        {[c.age_range, c.gender].filter(Boolean).join(' ')}
                      </span>
                    )}
                  </span>
                </button>
              );
            })}
          </aside>

          {/* 대화창 */}
          <section className="flex min-w-0 flex-1 flex-col">
            <div className="flex items-center gap-2 border-b border-border px-4 py-3">
              <span className="text-xl leading-none">{active?.emoji || '👤'}</span>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-text-primary">{active?.display_name || '에이전트'}</p>
              </div>
            </div>

            <div className="flex-1 space-y-3 overflow-y-auto bg-bg p-4">
              {turns.length === 0 && !streaming && (
                <p className="mt-8 text-center text-sm text-text-muted">
                  {active?.display_name || '이 소비자'}에게 첫 메시지를 보내보세요.
                </p>
              )}
              {turns.map((t) => (
                <ChatBubble key={t.id} role={t.role} author={t.role === 'agent' ? active?.display_name ?? undefined : undefined}>
                  {t.content}
                </ChatBubble>
              ))}
              {streaming && (
                <ChatBubble role="agent" author={active?.display_name ?? undefined}>
                  {streamingText || '…'}
                </ChatBubble>
              )}
              <div ref={bottomRef} />
            </div>

            {error && <p className="px-4 pt-2 text-xs text-error">{error}</p>}

            <form
              className="flex items-center gap-2 border-t border-border p-3"
              onSubmit={(e) => { e.preventDefault(); void handleSend(); }}
            >
              <div className="flex-1">
                <Input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder={`${active?.display_name || '에이전트'}에게 메시지…`}
                  disabled={streaming}
                  className="h-10"
                />
              </div>
              <Button type="submit" loading={streaming} disabled={!input.trim()} className="h-10 shrink-0">전송</Button>
            </form>
          </section>
        </div>
      )}
    </PageContainer>
  );
}

export default function ChatMessengerPage() {
  return (
    <AuthGuard>
      <AppShell>
        <ChatMessengerView />
      </AppShell>
    </AuthGuard>
  );
}
