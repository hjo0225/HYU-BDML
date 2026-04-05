'use client';

import { usePathname } from 'next/navigation';
import TopNav from './TopNav';
import Stepper from './Stepper';

// 이 경로에서는 TopNav/Stepper를 숨긴다 (프로젝트 목록, 인증 페이지)
const SHELL_HIDDEN_PATHS = ['/', '/login', '/register'];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const showShell = !SHELL_HIDDEN_PATHS.includes(pathname);

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
