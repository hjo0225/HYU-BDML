'use client';

import { Fragment } from 'react';
import { useProject } from '@/contexts/ProjectContext';
import { useRouter, usePathname } from 'next/navigation';

const STEPS = [
  { phase: 1, label: '연구 정보 입력', path: '/phase-1' },
  { phase: 2, label: '시장조사', path: '/phase-2' },
  { phase: 3, label: '에이전트 결정', path: '/phase-3' },
  { phase: 4, label: '회의 시뮬레이션', path: '/phase-4' },
  { phase: 5, label: '회의록 · 내보내기', path: '/phase-5' },
];

export default function Stepper() {
  const { project, setCurrentPhase } = useProject();
  const router = useRouter();
  const pathname = usePathname();

  const handleClick = (phase: number, path: string) => {
    // 미완료 단계 진입 차단
    if (phase > project.currentPhase) return;
    setCurrentPhase(phase);
    router.push(path);
  };

  const getState = (phase: number) => {
    if (phase < project.currentPhase) return 'done';
    if (phase === project.currentPhase) return 'active';
    return '';
  };

  return (
    <div className="stepper-wrap">
      <div className="stepper">
        {STEPS.map((step, i) => (
          <Fragment key={step.phase}>
            <div
              className={`step ${getState(step.phase)}`}
              onClick={() => handleClick(step.phase, step.path)}
              style={step.phase > project.currentPhase ? { opacity: 0.4, cursor: 'not-allowed' } : undefined}
            >
              <div className="step-num">
                {getState(step.phase) === 'done' ? '✓' : step.phase}
              </div>
              <div className="step-label">{step.label}</div>
            </div>
            {i < STEPS.length - 1 && <div className="step-connector" />}
          </Fragment>
        ))}
      </div>
    </div>
  );
}
