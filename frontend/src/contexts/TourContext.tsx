'use client';

// 데모 가이드 투어 상태 (plan 0008 v2 · item 0c).
// 실서비스 라우트를 튜토리얼처럼 순회한다. sessionStorage 로 라우트 이동 간 상태 유지.
import { createContext, useCallback, useContext, useEffect, useState } from 'react';

export interface TourStep {
  key: string;
  title: string;
  desc: string;
  path: (projectId: string) => string;
  /** 스포트라이트로 강조할 요소 셀렉터. 미발견 시 화면 중앙 말풍선으로 폴백. */
  target: string;
  /** false 면 스포트라이트(딤) 없이 말풍선만. 모달처럼 자체 딤이 있는 화면용. */
  spotlight?: boolean;
  /** 말풍선 위치 힌트. 'left' = 강조 영역 왼쪽. 미지정 시 아래(공간 부족 시 위). */
  bubblePos?: 'left';
}

// 프로젝트 생성(버튼) → 의뢰서 → 프로젝트 → 설문 → 에이전트(평가·대화) → FGI(보고서) 순서.
export const TOUR_STEPS: TourStep[] = [
  {
    key: 'create',
    title: '1 · 새 프로젝트 만들기',
    desc: '여기서 모든 조사가 시작됩니다. "+ 새 프로젝트" 버튼을 눌러 의뢰서를 작성해보세요. 데모에는 "포토이즘" 의뢰서가 미리 채워져 있어요.',
    path: () => '/projects',
    target: '[data-tour="create-project"]',
  },
  {
    key: 'brief',
    title: '2 · 프로젝트 의뢰서',
    desc: '조사 목적·타겟·활용 방안을 적어 프로젝트를 만듭니다. 내용을 살펴보고 "프로젝트 생성"을 눌러보세요.',
    path: () => '/projects',
    target: '[data-tour="brief-modal"]',
    spotlight: false,  // 모달이 자체 딤을 제공
  },
  {
    key: 'projects',
    title: '3 · 리서치 프로젝트',
    desc: '방금 만든 "포토이즘 재방문율 진단" 프로젝트입니다. 카드를 열어보거나 다음으로 진행하세요.',
    path: () => '/projects',
    target: '[data-tour="projects"]',
  },
  {
    key: 'survey-tab',
    title: '4 · 질문 관리',
    desc: '프로젝트 대시보드에 들어왔어요. "질문 관리" 카드를 눌러 이 조사에 쓸 질문지를 확인해보세요. (사이드바에서도 이동할 수 있어요.)',
    path: (pid) => `/projects/${pid}`,
    target: '[data-tour="card-questions"]',
  },
  {
    key: 'survey',
    title: '5 · 질문지 구성',
    desc: '처음엔 조사 정보를 입력해 질문지를 만듭니다. 생성되면 공통 설문·도메인 특화·인터뷰가 종류별 탭으로 나뉘고, 문항을 수정·추가·삭제할 수 있어요.',
    path: (pid) => `/projects/${pid}/questions`,
    target: '[data-tour="survey-panel"]',
    bubblePos: 'left',
  },
  {
    key: 'quality',
    title: '6 · 품질 평가',
    desc: 'AI 소비자가 진짜 사람과 얼마나 닮았는지(닮음), 서로 얼마나 다양한지(다양성)를 평가합니다. "품질 평가 실행"을 누르면 통계와 분포도가 나타나요.',
    path: (pid) => `/projects/${pid}/quality`,
    target: '[data-tour="quality-run"]',
  },
  {
    key: 'agents',
    title: '7 · AI 소비자 선택',
    desc: '수집한 응답으로 만든 AI 소비자입니다. 연령·성별로 필터링해 원하는 소비자를 고르고 "선택 저장"하면 1:1 채팅·FGI에 참여합니다.',
    path: (pid) => `/projects/${pid}/agents`,
    target: '[data-tour="agents"]',
  },
  {
    key: 'fgi',
    title: '8 · FGI 진행 · 인사이트 보고서',
    desc: 'AI 소비자들이 모더레이터 진행으로 다자 토론을 하고, 중간에 직접 개입할 수 있습니다. 종료되면 인사이트 보고서가 생성됩니다.',
    path: (pid) => `/projects/${pid}/fgi`,
    target: '[data-tour="fgi"]',
  },
];

interface TourState {
  active: boolean;
  step: number;
  projectId: string | null;
}

interface TourValue extends TourState {
  start: (projectId: string) => void;
  setStep: (i: number) => void;
  end: () => void;
}

const KEY = 'mb_tour';
const TourContext = createContext<TourValue | null>(null);

export function TourProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<TourState>({ active: false, step: 0, projectId: null });

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(KEY);
      if (raw) setState(JSON.parse(raw));
    } catch {}
  }, []);

  const persist = useCallback((s: TourState) => {
    setState(s);
    try { sessionStorage.setItem(KEY, JSON.stringify(s)); } catch {}
  }, []);

  const start = useCallback((projectId: string) => persist({ active: true, step: 0, projectId }), [persist]);
  const setStep = useCallback((i: number) => setState((s) => {
    const next = { ...s, step: Math.max(0, Math.min(TOUR_STEPS.length - 1, i)) };
    try { sessionStorage.setItem(KEY, JSON.stringify(next)); } catch {}
    return next;
  }), []);
  const end = useCallback(() => persist({ active: false, step: 0, projectId: null }), [persist]);

  return (
    <TourContext.Provider value={{ ...state, start, setStep, end }}>
      {children}
    </TourContext.Provider>
  );
}

export function useTour(): TourValue {
  const ctx = useContext(TourContext);
  if (!ctx) throw new Error('useTour must be used within TourProvider');
  return ctx;
}
