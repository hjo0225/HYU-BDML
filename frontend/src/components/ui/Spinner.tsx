import type { HTMLAttributes } from 'react';
import { cn } from './cn';

// 공용 스피너 — 비동기 로딩 표시. Button 의 인라인 로딩과 동일한 시각 언어.
type SpinnerSize = 'sm' | 'md' | 'lg';

const SIZE_CLASS: Record<SpinnerSize, string> = {
  sm: 'w-3.5 h-3.5 border-2',
  md: 'w-5 h-5 border-2',
  lg: 'w-8 h-8 border-[3px]',
};

interface SpinnerProps extends HTMLAttributes<HTMLSpanElement> {
  size?: SpinnerSize;
}

export function Spinner({ size = 'md', className, ...rest }: SpinnerProps) {
  return (
    <span
      aria-hidden
      {...rest}
      className={cn(
        'inline-block rounded-full border-current border-r-transparent animate-spin',
        SIZE_CLASS[size],
        className,
      )}
    />
  );
}

interface LoadingStateProps {
  /** 안내 문구 (기본: "불러오는 중…") */
  label?: string;
  className?: string;
}

/** 영역 중앙 정렬 로딩 표시 — 페이지·카드 로딩 플레이스홀더. */
export function LoadingState({ label = '불러오는 중…', className }: LoadingStateProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center gap-2 py-12 text-text-muted', className)}>
      <Spinner size="md" />
      <span className="text-sm">{label}</span>
    </div>
  );
}
