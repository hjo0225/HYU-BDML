import type { Metadata } from "next";
import "@/styles/globals.css";
import { AuthProvider } from "@/contexts/AuthContext";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { ProjectProvider } from "@/contexts/ProjectContext";
import AppShell from "@/components/layout/AppShell";

export const metadata: Metadata = {
  title: "AI 정성조사 시뮬레이션",
  description: "AI 에이전트 기반 정성조사 시뮬레이션 웹앱",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body>
        <AuthProvider>
          <AuthGuard>
            <ProjectProvider>
              <AppShell>{children}</AppShell>
            </ProjectProvider>
          </AuthGuard>
        </AuthProvider>
      </body>
    </html>
  );
}
