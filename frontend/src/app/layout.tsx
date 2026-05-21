import type { Metadata } from 'next';
import '@/styles/globals.css';
import { AuthProvider } from '@/contexts/AuthContext';
import { ProjectProvider } from '@/contexts/ProjectContext';
import { TourProvider } from '@/contexts/TourContext';
import { TourOverlay } from '@/components/tour/TourOverlay';

export const metadata: Metadata = {
  title: 'Mind-Bridge',
  description: 'AI 소비자 패널 생성·대화·평가 리서치 플랫폼',
  // 파비콘은 app/icon.png(정사각 패딩 로고) 컨벤션이 자동 처리.
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <AuthProvider>
          <ProjectProvider>
            <TourProvider>
              {children}
              <TourOverlay />
            </TourProvider>
          </ProjectProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
