'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import type {
  ProjectData,
  ResearchBrief,
  RefinedResearch,
  MarketReport,
  AgentSchema,
  MeetingMessage,
} from '@/lib/types';
import {
  createProject,
  updateProject,
  getProject,
  type ProjectUpdatePayload,
} from '@/lib/api';

// ── 상수 ──────────────────────────────────────────────────────────────────
const STORAGE_KEY = 'bigmarlab_project';
const PROJECT_ID_KEY = 'bigmarlab_project_id';

// ── 기본값 ────────────────────────────────────────────────────────────────
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

// ── 타입 가드 / 정규화 ─────────────────────────────────────────────────────
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
    marketReport: isRecord(value.marketReport)
      ? (value.marketReport as unknown as MarketReport)
      : null,
    agents: Array.isArray(value.agents) ? (value.agents as AgentSchema[]) : [],
    meetingTopic: typeof value.meetingTopic === 'string' ? value.meetingTopic : null,
    messages: Array.isArray(value.messages) ? (value.messages as MeetingMessage[]) : [],
    minutes: typeof value.minutes === 'string' ? value.minutes : null,
    currentPhase: typeof value.currentPhase === 'number' ? value.currentPhase : 1,
  };
}

// ── 백엔드 페이로드 빌드 ───────────────────────────────────────────────────
function buildUpdatePayload(project: ProjectData, phase: number): ProjectUpdatePayload {
  const payload: ProjectUpdatePayload = { current_phase: phase };

  // 각 단계에서 저장할 데이터를 phase 기준으로 포함
  if (phase >= 2 && project.brief) {
    payload.brief = project.brief as unknown as Record<string, unknown>;
  }
  if (phase >= 3 && project.refined) {
    payload.refined = project.refined as unknown as Record<string, unknown>;
    payload.market_report = project.marketReport as unknown as Record<string, unknown>;
  }
  if (phase >= 4 && project.agents.length > 0) {
    payload.agents = project.agents as unknown[];
  }
  if (phase >= 5) {
    if (project.meetingTopic) payload.meeting_topic = project.meetingTopic;
    if (project.messages.length > 0) payload.meeting_messages = project.messages as unknown[];
  }
  if (project.minutes) {
    payload.minutes = project.minutes;
    payload.status = 'completed';
  }

  return payload;
}

// ── Context 타입 ──────────────────────────────────────────────────────────

interface ProjectContextValue {
  project: ProjectData;
  projectId: string | null;       // DB 프로젝트 ID (없으면 아직 미생성)
  isSaving: boolean;              // 백엔드 저장 중 여부
  saveError: string | null;       // 저장 실패 메시지
  setBrief: (brief: ResearchBrief | null) => void;
  setRefined: (refined: RefinedResearch | null) => void;
  setMarketReport: (report: MarketReport | null) => void;
  setAgents: (agents: AgentSchema[]) => void;
  setMeetingTopic: (topic: string | null) => void;
  addMessage: (msg: MeetingMessage) => void;
  setMessages: (msgs: MeetingMessage[]) => void;
  setMinutes: (minutes: string | null) => void;
  setCurrentPhase: (phase: number) => void;  // 단계 전진 → 자동 백엔드 저장
  resetAfterBriefChange: (brief: ResearchBrief) => void;
  resetAfterRefinedChange: (refined: RefinedResearch | null) => void;
  resetAfterMarketReportChange: (report: MarketReport | null) => void;
  resetAfterAgentsChange: (agents: AgentSchema[]) => void;
  startMeetingSession: (topic: string) => void;
  resetProject: () => void;
  loadProjectFromBackend: (id: string) => Promise<void>;  // 목록에서 프로젝트 열기
}

const ProjectContext = createContext<ProjectContextValue | null>(null);

// ── Provider ──────────────────────────────────────────────────────────────

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [project, setProject] = useState<ProjectData>(defaultProject);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // ref로 최신 상태를 항상 참조 (비동기 콜백 클로저 문제 방지)
  const projectRef = useRef(project);
  const projectIdRef = useRef(projectId);
  useEffect(() => { projectRef.current = project; }, [project]);
  useEffect(() => { projectIdRef.current = projectId; }, [projectId]);

  // ── sessionStorage 복원 ────────────────────────────────────────────────
  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(STORAGE_KEY);
      if (saved) setProject(migrateProjectData(JSON.parse(saved)));
      const savedId = sessionStorage.getItem(PROJECT_ID_KEY);
      if (savedId) setProjectId(savedId);
    } catch {
      // 저장 포맷이 깨졌으면 기본 상태로 시작
    }
  }, []);

  // ── sessionStorage 동기화 ──────────────────────────────────────────────
  useEffect(() => {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(project));
    } catch {
      // 저장소 사용 불가 시 메모리 상태만 유지
    }
  }, [project]);

  // ── 상태 업데이트 헬퍼 ────────────────────────────────────────────────
  const update = useCallback((partial: Partial<ProjectData>) => {
    setProject((prev) => ({ ...prev, ...partial }));
  }, []);

  // ── 백엔드 저장 ───────────────────────────────────────────────────────
  /**
   * 단계 전진 시 백엔드에 저장한다.
   * - projectId 없음: 새 프로젝트 생성 (POST /api/projects)
   * - projectId 있음: PATCH /api/projects/:id
   *
   * 실패해도 로컬/sessionStorage 상태는 이미 업데이트됐으므로 플로우는 계속 진행된다.
   */
  const saveToBackend = useCallback(async (nextPhase: number, currentState: ProjectData) => {
    setIsSaving(true);
    setSaveError(null);

    try {
      const currentId = projectIdRef.current;

      if (!currentId) {
        // Phase 1→2: 프로젝트 최초 생성
        if (!currentState.brief) {
          setIsSaving(false);
          return;
        }
        const created = await createProject(currentState.brief);
        setProjectId(created.id);
        projectIdRef.current = created.id;
        sessionStorage.setItem(PROJECT_ID_KEY, created.id);
      } else {
        // Phase 2+: 기존 프로젝트 업데이트
        const payload = buildUpdatePayload(currentState, nextPhase);
        await updateProject(currentId, payload);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : '저장 중 오류가 발생했습니다.';
      setSaveError(msg);
      console.warn('[ProjectContext] 백엔드 저장 실패 (로컬 상태는 유지됩니다):', msg);
    } finally {
      setIsSaving(false);
    }
  }, []);

  // ── 외부에서 프로젝트 열기 (프로젝트 목록 → 이어보기) ─────────────────
  const loadProjectFromBackend = useCallback(async (id: string) => {
    setIsSaving(true);
    try {
      const data = await getProject(id);
      setProjectId(id);
      projectIdRef.current = id;
      sessionStorage.setItem(PROJECT_ID_KEY, id);

      // 백엔드 필드 → ProjectData 매핑
      const loaded: ProjectData = {
        brief: data.brief ? normalizeBrief(data.brief) : null,
        refined: data.refined ? normalizeRefined(data.refined) : null,
        marketReport: isRecord(data.market_report)
          ? (data.market_report as unknown as MarketReport)
          : null,
        agents: Array.isArray(data.agents) ? (data.agents as AgentSchema[]) : [],
        meetingTopic: data.meeting_topic ?? null,
        messages: Array.isArray(data.meeting_messages)
          ? (data.meeting_messages as MeetingMessage[])
          : [],
        minutes: data.minutes ?? null,
        currentPhase: data.current_phase ?? 1,
      };

      setProject(migrateProjectData(loaded));
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(loaded));
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : '프로젝트 불러오기 실패');
    } finally {
      setIsSaving(false);
    }
  }, []);

  // ── Context 값 ────────────────────────────────────────────────────────
  const value: ProjectContextValue = {
    project,
    projectId,
    isSaving,
    saveError,

    setBrief: (brief) => update({ brief }),
    setRefined: (refined) => update({ refined }),
    setMarketReport: (report) => update({ marketReport: report }),
    setAgents: (agents) => update({ agents }),
    setMeetingTopic: (meetingTopic) => update({ meetingTopic }),
    addMessage: (msg) =>
      setProject((prev) => ({ ...prev, messages: [...prev.messages, msg] })),
    setMessages: (messages) => update({ messages }),
    setMinutes: (minutes) => update({ minutes }),

    /**
     * 단계 전진 — 로컬 상태를 즉시 업데이트하고 백그라운드에서 백엔드에 저장한다.
     * 저장 실패 시에도 로컬/sessionStorage는 유지되므로 UX를 블로킹하지 않는다.
     */
    setCurrentPhase: (phase) => {
      setProject((prev) => {
        const next = { ...prev, currentPhase: phase };
        // 다음 단계 전환 시(앞으로 이동)에만 백엔드 저장
        if (phase > prev.currentPhase) {
          saveToBackend(phase, next);
        }
        return next;
      });
    },

    // 상위 단계 변경 시 하위 산출물 초기화 (기존 동작 유지)
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
    resetAfterMarketReportChange: (marketReport) =>
      setProject((prev) => ({
        ...prev,
        marketReport,
        agents: [],
        meetingTopic: null,
        messages: [],
        minutes: null,
      })),
    resetAfterAgentsChange: (agents) =>
      setProject((prev) => ({
        ...prev,
        agents,
        meetingTopic: null,
        messages: [],
        minutes: null,
      })),
    startMeetingSession: (meetingTopic) =>
      setProject((prev) => ({
        ...prev,
        meetingTopic,
        messages: [],
        minutes: null,
      })),

    resetProject: () => {
      setProject(defaultProject);
      setProjectId(null);
      projectIdRef.current = null;
      setSaveError(null);
      sessionStorage.removeItem(STORAGE_KEY);
      sessionStorage.removeItem(PROJECT_ID_KEY);
    },

    loadProjectFromBackend,
  };

  return (
    <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>
  );
}

// ── Hook ──────────────────────────────────────────────────────────────────

export function useProject(): ProjectContextValue {
  const ctx = useContext(ProjectContext);
  if (!ctx) throw new Error('useProject는 ProjectProvider 안에서 사용해야 합니다');
  return ctx;
}
