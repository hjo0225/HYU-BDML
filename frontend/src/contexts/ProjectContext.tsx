'use client';

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import type {
  ProjectData,
  ResearchBrief,
  RefinedResearch,
  MarketReport,
  AgentSchema,
  MeetingMessage,
} from '@/lib/types';

const STORAGE_KEY = 'bigmarlab_project';

const defaultProject: ProjectData = {
  brief: null,
  refined: null,
  marketReport: null,
  agents: [],
  meetingTopic: null,
  messages: [],
  minutes: null,
  currentPhase: 1,
};

const defaultBrief: ResearchBrief = {
  background: '',
  objective: '',
  usage_plan: '',
  category: '',
  target_customer: '',
};

const defaultRefined: RefinedResearch = {
  refined_background: '',
  refined_objective: '',
  refined_usage_plan: '',
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function migrateProjectData(value: unknown): ProjectData {
  if (!isRecord(value)) return defaultProject;

  const brief = isRecord(value.brief)
    ? {
        ...defaultBrief,
        ...value.brief,
      }
    : null;

  const refined = isRecord(value.refined)
    ? {
        ...defaultRefined,
        ...value.refined,
      }
    : null;

  return {
    brief,
    refined,
    marketReport: isRecord(value.marketReport) ? (value.marketReport as unknown as MarketReport) : null,
    agents: Array.isArray(value.agents) ? (value.agents as AgentSchema[]) : [],
    meetingTopic: typeof value.meetingTopic === 'string' ? value.meetingTopic : null,
    messages: Array.isArray(value.messages) ? (value.messages as MeetingMessage[]) : [],
    minutes: typeof value.minutes === 'string' ? value.minutes : null,
    currentPhase: typeof value.currentPhase === 'number' ? value.currentPhase : 1,
  };
}

interface ProjectContextValue {
  project: ProjectData;
  setBrief: (brief: ResearchBrief | null) => void;
  setRefined: (refined: RefinedResearch | null) => void;
  setMarketReport: (report: MarketReport | null) => void;
  setAgents: (agents: AgentSchema[]) => void;
  setMeetingTopic: (topic: string | null) => void;
  addMessage: (msg: MeetingMessage) => void;
  setMessages: (msgs: MeetingMessage[]) => void;
  setMinutes: (minutes: string | null) => void;
  setCurrentPhase: (phase: number) => void;
  resetProject: () => void;
}

const ProjectContext = createContext<ProjectContextValue | null>(null);

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [project, setProject] = useState<ProjectData>(defaultProject);

  // sessionStorage에서 복원
  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(STORAGE_KEY);
      if (saved) setProject(migrateProjectData(JSON.parse(saved)));
    } catch {
      // 복원 실패 시 기본값 유지
    }
  }, []);

  // 변경 시 sessionStorage에 저장
  useEffect(() => {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(project));
    } catch {
      // 저장 실패 무시
    }
  }, [project]);

  const update = useCallback((partial: Partial<ProjectData>) => {
    setProject((prev) => ({ ...prev, ...partial }));
  }, []);

  const value: ProjectContextValue = {
    project,
    setBrief: (brief) => update({ brief }),
    setRefined: (refined) => update({ refined }),
    setMarketReport: (report) => update({ marketReport: report }),
    setAgents: (agents) => update({ agents }),
    setMeetingTopic: (meetingTopic) => update({ meetingTopic }),
    addMessage: (msg) =>
      setProject((prev) => ({ ...prev, messages: [...prev.messages, msg] })),
    setMessages: (messages) => update({ messages }),
    setMinutes: (minutes) => update({ minutes }),
    setCurrentPhase: (phase) => update({ currentPhase: phase }),
    resetProject: () => setProject(defaultProject),
  };

  return (
    <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>
  );
}

export function useProject(): ProjectContextValue {
  const ctx = useContext(ProjectContext);
  if (!ctx) throw new Error('useProject는 ProjectProvider 안에서 사용해야 합니다');
  return ctx;
}
