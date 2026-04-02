"use client";

import { useRouter } from "next/navigation";
import { useProject } from "@/contexts/ProjectContext";

export default function TopNav() {
  const router = useRouter();
  const { resetProject } = useProject();

  const handleReset = () => {
    resetProject();
    router.push("/research-input");
  };

  return (
    <nav className="topnav">
      <div className="topnav-logo">빅데이터마케팅랩</div>
      <div className="topnav-right">
        <button
          className="btn btn-ghost"
          style={{
            fontSize: 11,
            color: "var(--text-muted)",
            padding: "4px 10px",
          }}
          onClick={handleReset}
        >
          처음으로
        </button>
        <div className="topnav-avatar">U</div>
      </div>
    </nav>
  );
}
