'use client';

import type { LabConfidence, MemoryCitation } from '@/lib/types';
import { categoryLabel } from './categoryLabels';

const CONFIDENCE_META: Record<
  LabConfidence,
  { dot: string; label: string; description: string }
> = {
  direct:    { dot: '🟢', label: '직접 명시',  description: '페르소나에 명시된 사실/응답을 그대로 반영' },
  inferred:  { dot: '🟡', label: '추론',       description: '페르소나의 가치관·성격 패턴으로 추론' },
  guess:     { dot: '🟠', label: '약한 짐작',  description: '근거가 약한 짐작 — 신뢰도 낮음' },
  unknown:   { dot: '⚪', label: '근거 없음',  description: '페르소나에 단서가 없음' },
};

interface Props {
  citations: MemoryCitation[];
  confidence: LabConfidence;
}

export default function CitationToggle({
  citations,
  confidence,
}: Props) {
  const meta = CONFIDENCE_META[confidence] ?? CONFIDENCE_META.unknown;
  const hasCitations = citations.length > 0;

  return (
    <div className="lab-cite">
      <div className="lab-cite__row">
        <span
          className={`lab-cite__badge lab-cite__badge--${confidence}`}
          title={meta.description}
        >
          {meta.dot} {meta.label}
        </span>
        {hasCitations && (
          <span className="lab-cite__count">🔍 근거 {citations.length}개</span>
        )}
      </div>
      {hasCitations && (
        <ul className="lab-cite__list">
          {citations.map((c, idx) => (
            <li key={`${c.category}-${idx}`} className="lab-cite__item">
              <div className="lab-cite__item-head">
                <span className="lab-cite__cat">{categoryLabel(c.category)}</span>
                <span
                  className="lab-cite__cat-slug"
                  title={`코사인 유사도 ${(c.score * 100).toFixed(0)}% · ${c.via}`}
                >
                  {c.category} · {(c.score * 100).toFixed(0)}%
                </span>
              </div>
              <div className="lab-cite__snippet">{c.snippet_en}</div>
              {c.snippet_ko && (
                <div className="lab-cite__snippet-ko">{c.snippet_ko}</div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
