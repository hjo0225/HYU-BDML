import type { Metadata } from 'next';
import '@/styles/globals.css';
import { ProjectProvider } from '@/contexts/ProjectContext';
import TopNav from '@/components/layout/TopNav';
import Stepper from '@/components/layout/Stepper';

export const metadata: Metadata = {
  title: '빅마랩 — AI 정성조사 시뮬레이션',
  description: 'AI 에이전트 기반 정성조사 시뮬레이션 웹앱',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body>
        <ProjectProvider>
          <TopNav />
          <Stepper />
          <div className="main">
            {children}
          </div>
        </ProjectProvider>
      </body>
    </html>
  );
}
