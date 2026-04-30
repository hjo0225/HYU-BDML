'use client';

import { usePathname } from 'next/navigation';
import TopNav from './TopNav';
import Stepper from './Stepper';

// 이 경로에서는 TopNav/Stepper를 숨긴다 (랜딩, 인증 페이지, 대시보드, 실험실)
// - 정확 매치: '/', '/login', '/register', '/dashboard'
// - prefix 매치: '/lab' (자체 레이아웃)
const SHELL_HIDDEN_EXACT = ['/', '/login', '/register', '/dashboard'];
const SHELL_HIDDEN_PREFIX = ['/lab'];

function shouldHideShell(pathname: string): boolean {
  if (SHELL_HIDDEN_EXACT.includes(pathname)) return true;
  return SHELL_HIDDEN_PREFIX.some((p) => pathname === p || pathname.startsWith(p + '/'));
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const showShell = !shouldHideShell(pathname);

  if (!showShell) {
    return <>{children}</>;
  }

  return (
    <>
      <TopNav />
      <Stepper />
      <div className="main">{children}</div>
    </>
  );
}
