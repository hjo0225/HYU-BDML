'use client';

import Link from 'next/link';

interface Experiment {
  id: string;
  title: string;
  description: string;
  badge: string;
  href: string;
  status: 'available' | 'coming_soon';
  meta?: string;
}

const EXPERIMENTS: Experiment[] = [
  {
    id: 'twin-chat',
    title: '디지털 트윈 1:1 메신저',
    description:
      'Twin-2K-500 데이터셋(Toubia et al. 2025) 기반 디지털 트윈과 한국어로 1:1 대화. 약 32개 카테고리의 자전적 기억과 빅5 성격을 RAG로 검색해 응답을 생성합니다.',
    badge: 'NEW',
    href: '/lab/twin-chat',
    status: 'available',
    meta: 'Twin-2K-500 · 50명 풀',
  },
  // 추후 추가 예정 — 비활성 카드는 회색 처리되며 클릭 비활성.
  {
    id: 'rag-vs-llm',
    title: 'RAG vs LLM 발화 비교',
    description: '동일 질문에 대해 RAG 패널 발언과 순수 LLM 발언을 좌/우로 비교 — 기억 기반 발언의 차이를 한 화면에서 확인.',
    badge: 'COMING SOON',
    href: '#',
    status: 'coming_soon',
  },
  {
    id: 'memory-explorer',
    title: '패널 메모리 탐색기',
    description: '특정 주제 임베딩으로 어떤 메모리들이 검색되는지 시각화 — RAG 검색 품질을 직접 점검.',
    badge: 'COMING SOON',
    href: '#',
    status: 'coming_soon',
  },
];

export default function LabMenuPage() {
  return (
    <>
      <main className="lab-main">
        <div className="lab-section-head">
          <h1 className="lab-section-title">실험을 선택하세요</h1>
          <p className="lab-section-sub">
            BDML이 진행하는 디지털 트윈·RAG 관련 연구 결과물을 직접 체험할 수 있는 공간입니다.
          </p>
        </div>

        <div className="lab-experiment-grid">
          {EXPERIMENTS.map((exp) => {
            const isAvailable = exp.status === 'available';
            const inner = (
              <>
                <div className="lab-experiment-card__head">
                  <span
                    className={`lab-experiment-card__badge lab-experiment-card__badge--${exp.status}`}
                  >
                    {exp.badge}
                  </span>
                </div>
                <h3 className="lab-experiment-card__title">{exp.title}</h3>
                <p className="lab-experiment-card__desc">{exp.description}</p>
                <div className="lab-experiment-card__footer">
                  {exp.meta && <span className="lab-experiment-card__meta">{exp.meta}</span>}
                  <span className="lab-experiment-card__cta">
                    {isAvailable ? '체험 시작 →' : '준비 중'}
                  </span>
                </div>
              </>
            );
            return isAvailable ? (
              <Link key={exp.id} href={exp.href} className="lab-experiment-card">
                {inner}
              </Link>
            ) : (
              <div key={exp.id} className="lab-experiment-card lab-experiment-card--disabled">
                {inner}
              </div>
            );
          })}
        </div>
      </main>
    </>
  );
}
