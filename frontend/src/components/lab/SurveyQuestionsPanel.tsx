'use client';

import { useMemo } from 'react';
import type { LabProbeQuestion } from '@/lib/types';
import { categoryLabel } from './categoryLabels';

interface Props {
  probeQuestions: LabProbeQuestion[];
  onSelect: (question: string) => void;
  disabled?: boolean;
}

export default function SurveyQuestionsPanel({
  probeQuestions,
  onSelect,
  disabled = false,
}: Props) {
  // 백엔드가 이미 의미 그룹 순서로 정렬해서 보내주므로 그대로 사용.
  // 카테고리 라벨로 그룹핑(현재는 카테고리당 1문항이라 사실상 1:1).
  const grouped = useMemo(() => {
    const groups: { label: string; slug: string; questions: string[] }[] = [];
    const indexBySlug = new Map<string, number>();
    for (const pq of probeQuestions) {
      let idx = indexBySlug.get(pq.category);
      if (idx === undefined) {
        idx = groups.length;
        indexBySlug.set(pq.category, idx);
        groups.push({ label: categoryLabel(pq.category), slug: pq.category, questions: [] });
      }
      groups[idx].questions.push(pq.question);
    }
    return groups;
  }, [probeQuestions]);

  if (probeQuestions.length === 0) {
    return (
      <aside className="lab-survey">
        <div className="lab-survey__header">
          <div className="lab-survey__title">설문 기반 질문</div>
        </div>
        <div className="lab-survey__empty">
          이 트윈은 아직 질문 데이터가 준비되지 않았어요.
        </div>
      </aside>
    );
  }

  return (
    <aside className="lab-survey">
      <div className="lab-survey__header">
        <div className="lab-survey__title">설문 기반 질문</div>
        <div className="lab-survey__hint">
          클릭하면 입력창에 채워져요. 그대로 보내거나 편집해서 보낼 수 있어요.
        </div>
      </div>
      <ul className="lab-survey__list">
        {grouped.map((g) => (
          <li key={g.slug} className="lab-survey__group">
            <div className="lab-survey__group-header" title={g.slug}>{g.label}</div>
            {g.questions.map((q, i) => (
              <button
                key={`${g.slug}-${i}`}
                type="button"
                className="lab-survey__item"
                onClick={() => onSelect(q)}
                disabled={disabled}
              >
                {q}
              </button>
            ))}
          </li>
        ))}
      </ul>
    </aside>
  );
}
