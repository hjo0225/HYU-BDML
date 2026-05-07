'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';

const NAV_ITEMS = [
  {
    section: '리서치',
    items: [
      { label: '대시보드', href: '/dashboard', icon: '◈' },
      { label: '에이전트', href: '/agents', icon: '◉' },
      { label: '대화 (1:1)', href: '/conversations', icon: '◎' },
      { label: 'FGI 세션', href: '/fgi', icon: '⊞' },
    ],
  },
  {
    section: '평가',
    items: [
      { label: '성능 대시보드', href: '/evaluation', icon: '⊕' },
      { label: '6-Lens 분석', href: '/lens', icon: '⊗' },
    ],
  },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <div className="flex h-screen overflow-hidden bg-bg">
      {/* 사이드바 */}
      <aside className="w-[var(--sidebar-width)] flex flex-col bg-surface border-r border-border shrink-0">
        {/* 로고 */}
        <div className="h-[var(--topnav-height)] flex items-center px-5 border-b border-border">
          <span className="text-lg font-bold text-ditto-indigo tracking-tight">Ditto</span>
          <span className="ml-1 text-xs text-ditto-violet font-medium">Research</span>
        </div>

        {/* 네비게이션 */}
        <nav className="flex-1 overflow-y-auto py-4">
          {NAV_ITEMS.map(({ section, items }) => (
            <div key={section} className="mb-4">
              <p className="px-5 mb-1 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                {section}
              </p>
              {items.map(({ label, href, icon }) => {
                const active = pathname === href || pathname.startsWith(`${href}/`);
                return (
                  <Link
                    key={href}
                    href={href}
                    className={`flex items-center gap-2.5 px-5 py-2 text-sm transition-colors duration-100 ${
                      active
                        ? 'bg-ditto-indigo-light text-ditto-indigo font-medium border-r-2 border-ditto-indigo'
                        : 'text-text-secondary hover:bg-ditto-indigo-light/50 hover:text-ditto-indigo'
                    }`}
                  >
                    <span className="text-base leading-none">{icon}</span>
                    {label}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>

        {/* 유저 정보 */}
        <div className="border-t border-border p-4">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-7 h-7 rounded-full bg-ditto-indigo-light flex items-center justify-center text-ditto-indigo text-xs font-bold">
              {user?.email?.[0]?.toUpperCase() ?? 'U'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-text-primary truncate">{user?.name || user?.email}</p>
              <p className="text-[10px] text-text-muted capitalize">{user?.role}</p>
            </div>
          </div>
          <button
            onClick={logout}
            className="w-full text-xs text-text-muted hover:text-error transition-colors py-1"
          >
            로그아웃
          </button>
        </div>
      </aside>

      {/* 메인 영역 */}
      <main className="flex-1 overflow-y-auto">
        {children}
      </main>
    </div>
  );
}
