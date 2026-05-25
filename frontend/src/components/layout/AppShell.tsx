'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Button } from '@/components/ui/Button';
import { Logo } from '@/components/layout/Logo';
import { useAuth } from '@/contexts/AuthContext';
import { useProjectContext } from '@/contexts/ProjectContext';

interface NavItem { label: string; href: string; icon: string; disabled?: boolean; indent?: boolean; disabledReason?: string }
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
// fgiRunning 동안에는 FGI 의 참여자 소스인 'AI 소비자' 탭을 잠가, 진행 중 이탈로
// SSE 세션이 끊기는 것을 막는다.
function projectNav(projectId: string | null, fgiRunning: boolean): NavSection {
  const at = (suffix: string) => (projectId ? `/projects/${projectId}${suffix}` : '');
  const disabled = !projectId;
  const lockedByFgi = !disabled && fgiRunning;
  return {
    section: '프로젝트',
    items: [
      { label: '개요', href: at(''), icon: '▤', disabled },
      { label: '질문 관리', href: at('/questions'), icon: '✎', disabled },
      { label: '품질 평가', href: at('/quality'), icon: '◐', disabled },
      {
        label: 'AI 소비자', href: at('/agents'), icon: '👥',
        disabled: disabled || lockedByFgi,
        disabledReason: lockedByFgi ? 'FGI 진행 중에는 이동할 수 없습니다' : undefined,
      },
      { label: '1:1 채팅', href: at('/chat'), icon: '💬', disabled, indent: true },
      { label: 'FGI 토론', href: at('/fgi'), icon: '🗣', disabled, indent: true },
    ],
  };
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { fgiRunning } = useProjectContext();

  // FGI 진행이 시작되면 사이드바를 자동으로 접어 토론 화면에 집중하게 한다(plan 0022).
  // 접힌 뒤에도 토글로 다시 열 수 있고, FGI 가 끝나면(fgiRunning=false) 자동으로 다시 펼친다.
  const [collapsed, setCollapsed] = useState(false);
  useEffect(() => { setCollapsed(fgiRunning); }, [fgiRunning]);

  // 현재 프로젝트 id (/projects/{id}…). 세부 탭은 항상 노출하되 미선택 시 비활성.
  const projMatch = pathname.match(/^\/projects\/([^/]+)/);
  const projectId = projMatch ? projMatch[1] : null;
  const sections: NavSection[] = [...NAV_ITEMS, projectNav(projectId, fgiRunning)];

  // 가장 긴(가장 구체적인) 일치 href 하나만 활성 처리 (비활성 항목 제외).
  const activeHref = sections
    .flatMap((s) => s.items)
    .filter((it) => !it.disabled && it.href && (pathname === it.href || pathname.startsWith(`${it.href}/`)))
    .sort((a, b) => b.href.length - a.href.length)[0]?.href;

  return (
    <div className="flex h-screen overflow-hidden bg-bg">
      {/* 사이드바 */}
      <aside
        className={`${collapsed ? 'w-16' : 'w-[var(--sidebar-width)]'} flex flex-col bg-surface border-r border-border shrink-0 transition-[width] duration-200`}
      >
        {/* 로고 + 접기 토글 */}
        <div className={`h-[var(--topnav-height)] flex items-center border-b border-border ${collapsed ? 'justify-center px-2' : 'justify-between px-4'}`}>
          {!collapsed && <Logo height={22} />}
          <button
            type="button"
            onClick={() => setCollapsed((c) => !c)}
            title={collapsed ? '사이드바 열기' : '사이드바 접기'}
            aria-label={collapsed ? '사이드바 열기' : '사이드바 접기'}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-base text-text-secondary hover:bg-ditto-indigo-light hover:text-ditto-indigo"
          >
            {collapsed ? '»' : '«'}
          </button>
        </div>

        {/* 네비게이션 */}
        <nav className="flex-1 overflow-y-auto py-4">
          {sections.map(({ section, items }) => (
            <div key={section} className="mb-4">
              {!collapsed && (
                <p className="px-5 mb-1 text-2xs font-medium uppercase tracking-wider
                              bg-gradient-to-br from-ditto-indigo to-ditto-violet bg-clip-text text-transparent">
                  {section}
                </p>
              )}
              {items.map(({ label, href, icon, disabled, indent, disabledReason }) => {
                const pad = collapsed ? 'justify-center px-0' : indent ? 'pl-10 pr-5' : 'px-5';
                // 비활성(프로젝트 미선택 또는 FGI 진행 중) 항목은 클릭 불가 회색 표시.
                // 그라데이션 비적용 — disabled 시각 위계 보존. 접힘 시 아이콘만 + title 로 라벨 안내.
                if (disabled) {
                  return (
                    <div
                      key={label}
                      title={collapsed ? label : (disabledReason ?? '먼저 프로젝트를 선택하세요')}
                      className={`flex items-center gap-2.5 ${pad} py-2 text-sm font-medium text-text-muted/50 cursor-not-allowed select-none`}
                    >
                      <span className="text-base leading-none">{icon}</span>
                      {!collapsed && label}
                      {!collapsed && disabledReason && <span className="ml-auto text-sm leading-none" aria-hidden>🔒</span>}
                    </div>
                  );
                }
                // 가장 긴 일치 href 만 활성 → '개요'(/projects/{id})가 하위 라우트에서 계속 켜지지 않게.
                // 활성/비활성 모두 라벨에는 인디고→바이올렛 그라데이션 적용.
                // 위계는 배경(bg-ditto-indigo-light)+오른쪽 보더로 유지.
                const active = href === activeHref;
                return (
                  <Link
                    key={href}
                    href={href}
                    title={collapsed ? label : undefined}
                    className={`flex items-center gap-2.5 ${pad} py-2 text-sm font-medium transition-colors duration-100 ${
                      active
                        ? 'bg-ditto-indigo-light border-r-2 border-ditto-indigo'
                        : 'hover:bg-ditto-indigo-light/40'
                    }`}
                  >
                    <span className={`text-base leading-none ${active ? 'text-ditto-indigo' : 'text-text-secondary'}`}>{icon}</span>
                    {!collapsed && (
                      <span className="bg-gradient-to-br from-ditto-indigo to-ditto-violet bg-clip-text text-transparent">
                        {label}
                      </span>
                    )}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>

        {/* 유저 정보 */}
        <div className="border-t border-border p-4">
          {collapsed ? (
            <div className="flex flex-col items-center gap-2">
              <div className="w-7 h-7 rounded-full bg-ditto-indigo-light flex items-center justify-center text-ditto-indigo text-xs font-bold">
                {user?.email?.[0]?.toUpperCase() ?? 'U'}
              </div>
              <button
                type="button"
                onClick={logout}
                title="로그아웃"
                aria-label="로그아웃"
                className="flex h-7 w-7 items-center justify-center rounded-lg text-text-secondary hover:bg-ditto-indigo-light hover:text-ditto-indigo"
              >
                ⎋
              </button>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-2 mb-2">
                <div className="w-7 h-7 rounded-full bg-ditto-indigo-light flex items-center justify-center text-ditto-indigo text-xs font-bold">
                  {user?.email?.[0]?.toUpperCase() ?? 'U'}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium truncate
                                bg-gradient-to-br from-ditto-indigo to-ditto-violet bg-clip-text text-transparent">
                    {user?.name || user?.email}
                  </p>
                  <p className="text-2xs font-medium capitalize
                                bg-gradient-to-br from-ditto-indigo to-ditto-violet bg-clip-text text-transparent">
                    {user?.role}
                  </p>
                </div>
              </div>
              <Button variant="ghost" size="sm" onClick={logout} className="w-full">
                로그아웃
              </Button>
            </>
          )}
        </div>
      </aside>

      {/* 메인 영역 */}
      <main className="flex-1 overflow-y-auto">
        {children}
      </main>
    </div>
  );
}
