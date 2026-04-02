"use client";

import { useProject } from "@/contexts/ProjectContext";
import { useRouter, usePathname } from "next/navigation";

const PHASE_GROUPS = [
  {
    title: "준비",
    steps: [{ phase: 1, label: "연구 정보 입력", path: "/research-input" }],
  },
  {
    title: "분석",
    steps: [
      { phase: 2, label: "시장조사", path: "/market-research" },
      { phase: 3, label: "에이전트 결정", path: "/agent-setup" },
    ],
  },
  {
    title: "실행",
    steps: [
      { phase: 4, label: "회의 시뮬레이션", path: "/meeting" },
      { phase: 5, label: "회의록 · 내보내기", path: "/minutes" },
    ],
  },
];

export default function Sidebar() {
  const { project, setCurrentPhase } = useProject();
  const router = useRouter();
  const pathname = usePathname();

  const handleNav = (phase: number, path: string) => {
    setCurrentPhase(phase);
    router.push(path);
  };

  const getStepState = (phase: number) => {
    if (phase < project.currentPhase) return "done";
    if (phase === project.currentPhase) return "active";
    return "upcoming";
  };

  return (
    <aside
      style={{ width: 250, minHeight: "100vh" }}
      className="bg-surface border-r border-border flex flex-col"
    >
      {/* 로고 */}
      <div className="px-5 py-4 border-b border-border">
        <div className="font-mono font-semibold text-sm tracking-tight text-text-primary">
          빅데이터마케팅랩
        </div>
        <div className="text-[10px] text-text-muted mt-0.5">
          AI 정성조사 시뮬레이션
        </div>
      </div>

      {/* Phase 그룹 */}
      <nav className="flex-1 px-3 py-4 space-y-5">
        {PHASE_GROUPS.map((group) => (
          <div key={group.title}>
            <div className="text-[10px] font-semibold text-text-muted uppercase tracking-wider px-2 mb-2">
              {group.title}
            </div>
            <div className="space-y-0.5">
              {group.steps.map((step) => {
                const state = getStepState(step.phase);
                const isActive = pathname === step.path;

                return (
                  <button
                    key={step.phase}
                    onClick={() => handleNav(step.phase, step.path)}
                    className={`w-full flex items-center gap-2.5 px-2 py-1.5 rounded-md text-left transition-colors text-xs ${
                      isActive
                        ? "bg-accent-light text-text-primary font-medium"
                        : "text-text-secondary hover:bg-accent-light"
                    }`}
                  >
                    <span
                      className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-semibold flex-shrink-0 ${
                        state === "done"
                          ? "bg-phase-done text-white"
                          : state === "active"
                          ? "bg-phase-active text-white"
                          : "border border-phase-upcoming text-phase-upcoming"
                      }`}
                    >
                      {state === "done" ? "✓" : step.phase}
                    </span>
                    <span>{step.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
    </aside>
  );
}
