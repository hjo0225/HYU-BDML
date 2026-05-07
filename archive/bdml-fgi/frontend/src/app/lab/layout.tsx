'use client';

import Link from 'next/link';
import type { ReactNode } from 'react';

export default function LabLayout({ children }: { children: ReactNode }) {
  return (
    <div className="lab-page">
      <header className="lab-header">
        <div className="lab-header__inner">
          <Link href="/lab" className="lab-header__brand" style={{ textDecoration: 'none', color: 'inherit' }}>
            <img src="/logo.png" alt="BDML" />
            <span className="lab-header__brand-tag">LAB</span>
          </Link>
          <nav className="lab-header__nav">
            <Link href="/" className="lab-header__nav-link">
              메인 서비스
            </Link>
            <Link href="/login" className="lab-header__nav-link">
              로그인
            </Link>
          </nav>
        </div>
      </header>
      {children}
    </div>
  );
}
