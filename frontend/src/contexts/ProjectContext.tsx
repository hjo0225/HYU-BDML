'use client';

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

/**
 * 프로젝트 흐름 컨텍스트.
 *
 * Slice 간 sessionStorage 로만 상태를 전달한다(서버 라운드트립 회피).
 * - projectId: 현재 활성 프로젝트
 * - selectedAgentIds: 카탈로그에서 N명 선택 → 평가/FGI 진입 시 사용
 *
 * sessionStorage 키: 'ditto_project_context'.
 * 탭을 닫으면 자동 만료된다. 영속이 필요한 정보는 backend 에 저장한다.
 */

interface ProjectContextState {
  projectId: string | null;
  selectedAgentIds: string[];
}

interface ProjectContextValue extends ProjectContextState {
  setProjectId: (id: string | null) => void;
  toggleAgent: (id: string) => void;
  setSelectedAgents: (ids: string[]) => void;
  clearSelection: () => void;
  reset: () => void;
}

const STORAGE_KEY = 'ditto_project_context';
const EMPTY: ProjectContextState = { projectId: null, selectedAgentIds: [] };

const ProjectContext = createContext<ProjectContextValue | null>(null);

function loadFromStorage(): ProjectContextState {
  if (typeof window === 'undefined') return EMPTY;
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return EMPTY;
    const parsed = JSON.parse(raw) as Partial<ProjectContextState>;
    return {
      projectId: typeof parsed.projectId === 'string' ? parsed.projectId : null,
      selectedAgentIds: Array.isArray(parsed.selectedAgentIds) ? parsed.selectedAgentIds.filter(s => typeof s === 'string') : [],
    };
  } catch {
    return EMPTY;
  }
}

function persist(state: ProjectContextState) {
  if (typeof window === 'undefined') return;
  if (state.projectId === null && state.selectedAgentIds.length === 0) {
    sessionStorage.removeItem(STORAGE_KEY);
    return;
  }
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

export function ProjectProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<ProjectContextState>(EMPTY);

  // SSR 안전을 위해 마운트 후 sessionStorage 로드
  useEffect(() => {
    setState(loadFromStorage());
  }, []);

  // 상태 변경 시 sessionStorage 동기화
  useEffect(() => {
    persist(state);
  }, [state]);

  const setProjectId = useCallback((id: string | null) => {
    setState(s => {
      // 프로젝트가 바뀌면 선택 초기화 (다른 프로젝트의 agent_id 가 섞이지 않도록)
      if (s.projectId !== id) return { projectId: id, selectedAgentIds: [] };
      return s;
    });
  }, []);

  const toggleAgent = useCallback((id: string) => {
    setState(s => {
      const has = s.selectedAgentIds.includes(id);
      return {
        ...s,
        selectedAgentIds: has
          ? s.selectedAgentIds.filter(a => a !== id)
          : [...s.selectedAgentIds, id],
      };
    });
  }, []);

  const setSelectedAgents = useCallback((ids: string[]) => {
    setState(s => ({ ...s, selectedAgentIds: ids }));
  }, []);

  const clearSelection = useCallback(() => {
    setState(s => ({ ...s, selectedAgentIds: [] }));
  }, []);

  const reset = useCallback(() => setState(EMPTY), []);

  const value = useMemo<ProjectContextValue>(
    () => ({ ...state, setProjectId, toggleAgent, setSelectedAgents, clearSelection, reset }),
    [state, setProjectId, toggleAgent, setSelectedAgents, clearSelection, reset],
  );

  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
}

export function useProjectContext(): ProjectContextValue {
  const ctx = useContext(ProjectContext);
  if (!ctx) throw new Error('useProjectContext must be used within ProjectProvider');
  return ctx;
}
