'use client';

import { Gauge } from './Gauge';
import { ScoreBadge } from './ScoreBadge';

interface V1GaugeProps {
  /** sync 점수 0~1. null 이면 평가 전. */
  sync: number | null | undefined;
  /** N=평가된 자극 개수 (예: 3). */
  nEval?: number | null;
  size?: number;
}

/**
 * V1 응답 동기화율 게이지. EVAL_SPEC.md §1 임계 (≥0.80 / 0.60~0.80 / <0.60)
 * 를 ScoreBadge·Gauge 가 SSOT 로 공유한다.
 */
export function V1Gauge({ sync, nEval, size = 220 }: V1GaugeProps) {
  if (sync == null) {
    return (
      <div className="flex flex-col items-center gap-2 py-6">
        <div
          className="rounded-full border-4 border-dashed border-border flex items-center justify-center"
          style={{ width: size * 0.62, height: size * 0.62 }}
        >
          <span className="text-xs text-text-muted">평가 전</span>
        </div>
        <span className="text-xs text-text-muted">V1 응답 동기화율</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-2">
      <Gauge value={sync} display="percent" size={size} label={undefined} />
      <div className="flex items-center gap-2">
        <ScoreBadge score={sync} label="V1" />
        {nEval != null && (
          <span className="text-xs text-text-muted">n={nEval} 자극</span>
        )}
      </div>
      <span className="text-xs text-text-muted">응답 동기화율 (원문 cosine 평균)</span>
    </div>
  );
}
