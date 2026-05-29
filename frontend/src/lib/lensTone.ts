// 6-Lens 닮은정도(agreement) → 색상 티어. 대시보드·카드·미니막대가 공유하는 단일 진실 공급원.
// 임계값: ≥80 파랑 / ≥60 초록 / ≥40 주황 / <40 빨강
export type LensTone = 'blue' | 'green' | 'orange' | 'red';

export function lensTone(agreement: number): LensTone {
  if (agreement >= 0.8) return 'blue';
  if (agreement >= 0.6) return 'green';
  if (agreement >= 0.4) return 'orange';
  return 'red';
}

// 단색 배경 (미니 막대)
export const LENS_TONE_BG: Record<LensTone, string> = {
  blue: 'bg-info',
  green: 'bg-success',
  orange: 'bg-warning',
  red: 'bg-error',
};

// 텍스트 색 (퍼센트 라벨)
export const LENS_TONE_TEXT: Record<LensTone, string> = {
  blue: 'text-info',
  green: 'text-success',
  orange: 'text-warning',
  red: 'text-error',
};

// 세로 그라데이션 (큰 막대 차트)
export const LENS_TONE_GRADIENT: Record<LensTone, string> = {
  blue: 'linear-gradient(180deg, var(--info), #2563eb)',
  green: 'linear-gradient(180deg, var(--success), #059669)',
  orange: 'linear-gradient(180deg, var(--warning), #d97706)',
  red: 'linear-gradient(180deg, var(--error), #dc2626)',
};
