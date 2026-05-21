import type { HTMLAttributes } from 'react';
import { cn } from '@/components/ui/cn';

// 페이지 외곽 셸 통일 — AppShell 내부 콘텐츠 컨테이너.
// 기존 페이지가 p-8 max-w-5xl / 6xl / 3xl 로 제각각이던 것을 한 컴포넌트로 수렴.
type Width = 'narrow' | 'default' | 'wide';

const WIDTH_CLASS: Record<Width, string> = {
  narrow: 'max-w-3xl',   // 채팅·집중 폼
  default: 'max-w-5xl',  // 표준 페이지 (프로젝트·상세)
  wide: 'max-w-6xl',     // 카탈로그·갤러리 등 넓은 그리드
};

interface PageContainerProps extends HTMLAttributes<HTMLDivElement> {
  width?: Width;
}

export function PageContainer({
  width = 'default',
  className,
  children,
  ...rest
}: PageContainerProps) {
  return (
    <div {...rest} className={cn('p-8 mx-auto w-full', WIDTH_CLASS[width], className)}>
      {children}
    </div>
  );
}
