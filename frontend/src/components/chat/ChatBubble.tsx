import type { ReactNode } from 'react';
import { cn } from '@/components/ui/cn';

export type ChatRole = 'user' | 'agent' | 'moderator';

interface ChatBubbleProps {
  role: ChatRole;
  children: ReactNode;
  /** 에이전트/모더레이터 발언자명 (사용자는 보통 생략) */
  author?: string;
  /** 버블 하단 인라인 부착 (예: ScoreBadge — V1 동기화율 표시) */
  footer?: ReactNode;
  /** 타임스탬프 등 발언자명 옆 보조 정보 */
  meta?: ReactNode;
  className?: string;
}

// DESIGN.md ChatBubble:
//   user      : indigo + 흰 글자, 우측, rounded-xl + 좌하단 4px 끝부리
//   agent     : surface + primary 글자, 좌측, rounded-xl + 우하단 4px 끝부리
//   moderator : 중앙, 점선 테두리, text-sm, 옅은 배경
// Tailwind 의 `rounded` (suffix 없음) = 4px 가 끝부리에 해당.
const ROLE_CONTAINER: Record<ChatRole, string> = {
  user: 'flex justify-end',
  agent: 'flex justify-start',
  moderator: 'flex justify-center',
};

const ROLE_BUBBLE: Record<ChatRole, string> = {
  user: 'bg-ditto-indigo text-white rounded-xl rounded-bl px-4 py-2.5 max-w-[80%]',
  agent:
    'bg-surface border border-border text-text-primary rounded-xl rounded-br ' +
    'px-4 py-2.5 max-w-[80%] shadow-card',
  moderator:
    'bg-ditto-indigo-light/50 border border-dashed border-border text-text-secondary ' +
    'text-sm px-4 py-2 rounded-xl max-w-[70%] text-center',
};

const AUTHOR_CLASS: Record<ChatRole, string> = {
  user: 'text-xs text-text-muted mb-1 text-right',
  agent: 'text-xs text-text-muted mb-1',
  moderator: 'text-2xs text-text-muted mb-1 text-center uppercase tracking-wider',
};

export function ChatBubble({
  role,
  children,
  author,
  footer,
  meta,
  className,
}: ChatBubbleProps) {
  return (
    <div className={cn('w-full', className)}>
      {author && (
        <div className={AUTHOR_CLASS[role]}>
          <span className="font-medium">{author}</span>
          {meta && <span className="ml-1.5 opacity-70">{meta}</span>}
        </div>
      )}
      <div className={ROLE_CONTAINER[role]}>
        <div className={cn(ROLE_BUBBLE[role], 'whitespace-pre-wrap break-words')}>
          {children}
        </div>
      </div>
      {footer && (
        <div
          className={cn(
            'mt-1.5 flex gap-1.5 flex-wrap',
            role === 'user'
              ? 'justify-end'
              : role === 'moderator'
                ? 'justify-center'
                : 'justify-start',
          )}
        >
          {footer}
        </div>
      )}
    </div>
  );
}
