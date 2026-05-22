import Link from 'next/link';
import type { ReactNode } from 'react';
import { cn } from '@/components/ui/cn';

// 페이지 상단 헤더 — (선택) 뒤로가기 링크 + 제목 + 부제 + 우측 액션 슬롯.
// 카탈로그·에이전트 상세·채팅 등에서 반복되던 "← 링크 / 타이틀 / 액션" 블록을 통일.
interface PageHeaderProps {
  title: ReactNode;
  subtitle?: ReactNode;
  /** 뒤로가기 링크 대상. 지정 시 제목 위에 "← {backLabel}" 표시 */
  backHref?: string;
  backLabel?: string;
  /** true 면 뒤로가기를 클릭 불가(회색·🔒)로 표시. 진행 중 이탈 방지 등에 사용. */
  backDisabled?: boolean;
  /** backDisabled 일 때 보여줄 사유(툴팁) */
  backDisabledReason?: string;
  /** 우측 정렬 액션 (버튼 등) */
  actions?: ReactNode;
  className?: string;
}

export function PageHeader({
  title,
  subtitle,
  backHref,
  backLabel = '뒤로',
  backDisabled = false,
  backDisabledReason,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <div className={cn('mb-6', className)}>
      {backHref && (
        backDisabled ? (
          <span
            title={backDisabledReason}
            className="mb-2 inline-flex cursor-not-allowed select-none items-center gap-1 text-xs text-text-muted/50"
          >
            ← {backLabel} 🔒
          </span>
        ) : (
          <Link
            href={backHref}
            className="inline-block mb-2 text-xs text-text-muted hover:text-ditto-indigo transition-colors"
          >
            ← {backLabel}
          </Link>
        )
      )}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-3xl font-bold text-text-primary truncate">{title}</h1>
          {subtitle && <p className="text-sm text-text-muted mt-1">{subtitle}</p>}
        </div>
        {actions && <div className="shrink-0 flex items-center gap-2">{actions}</div>}
      </div>
    </div>
  );
}
