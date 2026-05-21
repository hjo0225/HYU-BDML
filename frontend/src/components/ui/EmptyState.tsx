import type { ReactNode } from 'react';
import { cn } from './cn';

// 빈 상태 플레이스홀더 — 빈 목록·"첫 메시지를 보내세요"·"평가 전" 등에 재사용.
interface EmptyStateProps {
  /** 상단 이모지 또는 아이콘 노드 */
  icon?: ReactNode;
  title: string;
  description?: ReactNode;
  /** 하단 액션 슬롯 (예: 생성 버튼) */
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center text-center gap-2 py-12 px-4', className)}>
      {icon && <div className="text-3xl leading-none mb-1">{icon}</div>}
      <p className="text-sm font-medium text-text-secondary">{title}</p>
      {description && <p className="text-xs text-text-muted max-w-sm">{description}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}
