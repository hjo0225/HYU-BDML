import type { HTMLAttributes, ReactNode } from 'react';
import { cn } from './cn';

// 범용 캡슐 배지 — cluster 태그·상태 칩·source 라벨 등에 재사용.
// 점수 전용 배지는 components/dashboard/ScoreBadge 를 쓴다(임계값 로직 포함).
type BadgeVariant = 'neutral' | 'indigo' | 'violet' | 'success' | 'warning' | 'error';
type BadgeSize = 'sm' | 'md';

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  size?: BadgeSize;
  /** 좌측 점(•) 인디케이터 표시 */
  dot?: boolean;
  children: ReactNode;
}

// 옅은 배경은 DESIGN.md §ScoreBadge 가 허용한 Tailwind 기본 스케일을 따른다.
const VARIANT_CLASS: Record<BadgeVariant, string> = {
  neutral: 'bg-ditto-indigo-light text-text-secondary',
  indigo: 'bg-ditto-indigo-light text-ditto-indigo',
  violet: 'bg-ditto-violet-light text-ditto-violet',
  success: 'bg-emerald-50 text-success',
  warning: 'bg-amber-50 text-warning',
  error: 'bg-red-50 text-error',
};

const SIZE_CLASS: Record<BadgeSize, string> = {
  sm: 'text-2xs px-1.5 py-0.5 gap-1',
  md: 'text-xs px-2 py-1 gap-1.5',
};

const DOT_COLOR: Record<BadgeVariant, string> = {
  neutral: 'bg-text-muted',
  indigo: 'bg-ditto-indigo',
  violet: 'bg-ditto-violet',
  success: 'bg-success',
  warning: 'bg-warning',
  error: 'bg-error',
};

export function Badge({
  variant = 'neutral',
  size = 'md',
  dot = false,
  className,
  children,
  ...rest
}: BadgeProps) {
  return (
    <span
      {...rest}
      className={cn(
        'inline-flex items-center rounded-full font-medium whitespace-nowrap',
        VARIANT_CLASS[variant],
        SIZE_CLASS[size],
        className,
      )}
    >
      {dot && <span aria-hidden className={cn('w-1.5 h-1.5 rounded-full', DOT_COLOR[variant])} />}
      {children}
    </span>
  );
}
