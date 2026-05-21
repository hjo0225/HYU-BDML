'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Button } from '@/components/ui/Button';
import { Logo } from '@/components/layout/Logo';
import { useAuth } from '@/contexts/AuthContext';

interface NavItem { label: string; href: string; icon: string; disabled?: boolean; indent?: boolean }
interface NavSection { section: string; items: NavItem[] }

const NAV_ITEMS: NavSection[] = [
  {
    section: '리서치',
    items: [
      { label: '대시보드', href: '/dashboard', icon: '◈' },
      { label: '프로젝트', href: '/projects', icon: '◉' },
    ],
  },
];

// 프로젝트 세부 탭. 프로젝트 미선택(projectId=null) 시 비활성 상태로 노출한다.
function projectNav(projectId: string | null): NavSection {
  const at = (suffix: string) => (projectId ? `/projects/${projectId}${suffix}` : '');
  const disabled = !projectId;
  return {
    section: '프로젝트',
    items: [
      { label: '개요', href: at(''), icon: '▤', disabled },
      { label: '질문 관리', href: at('/questions'), icon: '✎', disabled },
      { label: '품질 평가', href: at('/quality'), icon: '◐', disabled },
      { label: 'AI 소비자', href: at('/agents'), icon: '👥', disabled },
      { label: '1:1 채팅', href: at('/chat'), icon: '💬', disabled, indent: true },
      { label: 'FGI 토론', href: at('/fgi'), icon: '🗣', disabled, indent: true },
    ],
  };
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  // 현재 프로젝트 id (/projects/{id}…). 세부 탭은 항상 노출하되 미선택 시 비활성.
  const projMatch = pathname.match(/^\/projects\/([^/]+)/);
  const projectId = projMatch ? projMatch[1] : null;
  const sections: NavSection[] = [...NAV_ITEMS, projectNav(projectId)];

  // 가장 긴(가장 구체적인) 일치 href 하나만 활성 처리 (비활성 항목 제외).
  const activeHref = sections
    .flatMap((s) => s.items)
    .filter((it) => !it.disabled && it.href && (pathname === it.href || pathname.startsWith(`${it.href}/`)))
    .sort((a, b) => b.href.length - a.href.length)[0]?.href;

  return (
    <div className="flex h-screen overflow-hidden bg-bg">
      {/* 사이드바 */}
      <aside className="w-[var(--sidebar-width)] flex flex-col bg-surface border-r border-border shrink-0">
        {/* 로고 */}
        <div className="h-[var(--topnav-height)] flex items-center px-5 border-b border-border">
          <Logo height={22} />
        </div>

        {/* 네비게이션 */}
        <nav className="flex-1 overflow-y-auto py-4">
          {sections.map(({ section, items }) => (
            <div key={section} className="mb-4">
              <p className="px-5 mb-1 text-2xs font-semibold uppercase tracking-wider text-text-muted">
                {section}
              </p>
              {items.map(({ label, href, icon, disabled, indent }) => {
                const pad = indent ? 'pl-10 pr-5' : 'px-5';
                // 비활성(프로젝트 미선택) 항목은 클릭 불가 회색 표시.
                if (disabled) {
                  return (
                    <div
                      key={label}
                      title="먼저 프로젝트를 선택하세요"
                      className={`flex items-center gap-2.5 ${pad} py-2 text-sm text-text-muted/50 cursor-not-allowed select-none`}
                    >
                      <span className="text-base leading-none">{icon}</span>
                      {label}
                    </div>
                  );
                }
                // 가장 긴 일치 href 만 활성 → '개요'(/projects/{id})가 하위 라우트에서 계속 켜지지 않게.
                const active = href === activeHref;
                return (
                  <Link
                    key={href}
                    href={href}
                    className={`flex items-center gap-2.5 ${pad} py-2 text-sm transition-colors duration-100 ${
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
              <p className="text-2xs text-text-muted capitalize">{user?.role}</p>
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={logout} className="w-full">
            로그아웃
          </Button>
        </div>
      </aside>

      {/* 메인 영역 */}
      <main className="flex-1 overflow-y-auto">
        {children}
      </main>
    </div>
  );
}
