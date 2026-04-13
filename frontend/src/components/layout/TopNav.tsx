"use client";

import { useRouter } from "next/navigation";
import { useProject } from "@/contexts/ProjectContext";
import { useAuth } from "@/contexts/AuthContext";

export default function TopNav() {
  const router = useRouter();
  const { resetProject, isSaving, saveError, projectId } = useProject();
  const { user, logout } = useAuth();

  const handleHome = () => {
    router.push("/");
  };

  const handleReset = () => {
    resetProject();
    router.push("/research-input");
  };

  return (
    <nav className="topnav">
      <div className="topnav-left">
        <button className="topnav-logo" onClick={handleHome} title="프로젝트 목록으로">
          <img src="/logo.png" alt="BDML" />
        </button>
      </div>

      <div className="topnav-right">
        {/* 저장 상태 인디케이터 */}
        {isSaving && (
          <span className="topnav-save-indicator topnav-save-indicator--saving">
            <span className="topnav-save-spinner" />
            저장 중...
          </span>
        )}
        {saveError && !isSaving && (
          <span
            className="topnav-save-indicator topnav-save-indicator--error"
            title={saveError}
          >
            ⚠ 저장 실패
          </span>
        )}
        {!isSaving && !saveError && projectId && (
          <span className="topnav-save-indicator topnav-save-indicator--saved">
            ✓ 저장됨
          </span>
        )}

        <button
          className="btn btn-ghost"
          style={{ fontSize: 11, color: "var(--text-muted)", padding: "4px 10px" }}
          onClick={handleReset}
          title="새 연구 시작"
        >
          새 연구
        </button>

        <button
          className="btn btn-ghost"
          style={{ fontSize: 11, color: "var(--text-muted)", padding: "4px 10px" }}
          onClick={handleHome}
        >
          목록
        </button>

        <div
          className="topnav-avatar"
          title={user?.email}
        >
          {user?.name?.[0]?.toUpperCase() ?? user?.email?.[0]?.toUpperCase() ?? 'U'}
        </div>

        <button
          className="btn btn-ghost"
          style={{ fontSize: 11, color: "var(--text-muted)", padding: "4px 10px" }}
          onClick={logout}
        >
          로그아웃
        </button>
      </div>
    </nav>
  );
}
