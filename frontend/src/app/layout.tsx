import type { Metadata } from 'next';
import '@/styles/globals.css';
import { ProjectProvider } from '@/contexts/ProjectContext';
import Sidebar from '@/components/layout/Sidebar';

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
          <div className="flex min-h-screen">
            <Sidebar />
            <main className="flex-1 p-6 max-w-[1200px]">
              {children}
            </main>
          </div>
        </ProjectProvider>
      </body>
    </html>
  );
}
