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

function toText(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function normalizeBrief(value: unknown): ResearchBrief | null {
  if (!isRecord(value)) return null;

  return {
    background: toText(value.background),
    objective: toText(value.objective),
    usage_plan: toText(value.usage_plan),
    category: toText(value.category),
    target_customer: toText(value.target_customer),
  };
}

function normalizeRefined(value: unknown): RefinedResearch | null {
  if (!isRecord(value)) return null;

  return {
    refined_background: toText(value.refined_background),
    refined_objective: toText(value.refined_objective),
    refined_usage_plan: toText(value.refined_usage_plan),
  };
}

function migrateProjectData(value: unknown): ProjectData {
  if (!isRecord(value)) return defaultProject;

  const brief = normalizeBrief(value.brief);
  const refined = normalizeRefined(value.refined);

  return {
    brief: brief ? { ...defaultBrief, ...brief } : null,
    refined: refined ? { ...defaultRefined, ...refined } : null,
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
  resetAfterBriefChange: (brief: ResearchBrief) => void;
  resetAfterRefinedChange: (refined: RefinedResearch | null) => void;
  resetAfterMarketReportChange: (report: MarketReport | null) => void;
  resetAfterAgentsChange: (agents: AgentSchema[]) => void;
  startMeetingSession: (topic: string) => void;
  resetProject: () => void;
}

const ProjectContext = createContext<ProjectContextValue | null>(null);

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [project, setProject] = useState<ProjectData>(defaultProject);

  // 저장된 상태가 있으면 초기 렌더 뒤에 복원한다.
  // 서버 렌더 단계에서는 sessionStorage에 접근할 수 없으므로 useEffect에서 처리한다.
  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(STORAGE_KEY);
      if (saved) setProject(migrateProjectData(JSON.parse(saved)));
    } catch {
      // 저장 포맷이 깨졌으면 기본 상태로 시작한다.
    }
  }, []);

  // 프로젝트 상태가 바뀔 때마다 다음 진입을 위해 현재 흐름 전체를 저장한다.
  useEffect(() => {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(project));
    } catch {
      // 저장소 사용이 불가능한 환경에서는 메모리 상태만 유지한다.
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
    // 상위 단계가 바뀌면 하위 산출물을 버려서 오래된 결과가 섞이지 않게 한다.
    resetAfterBriefChange: (brief) =>
      setProject((prev) => ({
        ...prev,
        brief,
        refined: null,
        marketReport: null,
        agents: [],
        meetingTopic: null,
        messages: [],
        minutes: null,
      })),
    // 정제 결과가 바뀌면 보고서 이후 단계는 다시 생성해야 한다.
    resetAfterRefinedChange: (refined) =>
      setProject((prev) => ({
        ...prev,
        refined,
        marketReport: null,
        agents: [],
        meetingTopic: null,
        messages: [],
        minutes: null,
      })),
    // 시장조사 보고서가 바뀌면 추천 에이전트와 회의 결과도 무효가 된다.
    resetAfterMarketReportChange: (marketReport) =>
      setProject((prev) => ({
        ...prev,
        marketReport,
        agents: [],
        meetingTopic: null,
        messages: [],
        minutes: null,
      })),
    // 참여자가 바뀌면 기존 회의 로그와 회의록은 더 이상 같은 맥락이 아니다.
    resetAfterAgentsChange: (agents) =>
      setProject((prev) => ({
        ...prev,
        agents,
        meetingTopic: null,
        messages: [],
        minutes: null,
      })),
    // 새 회의를 시작할 때는 주제만 남기고 이전 회의 산출물은 초기화한다.
    startMeetingSession: (meetingTopic) =>
      setProject((prev) => ({
        ...prev,
        meetingTopic,
        messages: [],
        minutes: null,
      })),
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
