'use client';

import { useEffect, type ReactNode } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';

// 인증 없이 접근 가능한 경로
// - '/' (랜딩), '/login', '/register'는 정확 매치
// - '/lab'은 prefix 매치 (/lab, /lab/chat/{id} 등 전체 공개)
const PUBLIC_EXACT = ['/', '/login', '/register'];
const PUBLIC_PREFIX = ['/lab'];

function isPublicPath(pathname: string): boolean {
  if (PUBLIC_EXACT.includes(pathname)) return true;
  return PUBLIC_PREFIX.some((p) => pathname === p || pathname.startsWith(p + '/'));
}

export function AuthGuard({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (isLoading) return;

    if (!user && !isPublicPath(pathname)) {
      // 로그인 후 원래 페이지로 돌아올 수 있도록 redirect 파라미터 추가
      router.replace(`/login?redirect=${encodeURIComponent(pathname)}`);
    }
  }, [user, isLoading, pathname, router]);

  if (isLoading) {
    return (
      <div className="auth-loading">
        <div className="auth-loading__spinner" />
      </div>
    );
  }

  if (!user && !isPublicPath(pathname)) return null; // 리다이렉트 대기 중 빈 화면

  return <>{children}</>;
}
