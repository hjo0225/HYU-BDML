// 평가 점수 → 상태 색상 매핑.
// 임계값은 docs/EVAL_SPEC.md §V1 의 정식 SSOT 를 따른다.
//   ≥ 0.80 : Excellent  → success
//   0.60~0.80 : Acceptable → warning
//   < 0.60 : Insufficient  → error
export type ScoreStatus = 'success' | 'warning' | 'error';

export function scoreStatus(score: number): ScoreStatus {
  if (score >= 0.8) return 'success';
  if (score >= 0.6) return 'warning';
  return 'error';
}

// 상태 → CSS 변수 (게이지 채움색 등 SVG fill 에 직접 사용)
export const statusColorVar: Record<ScoreStatus, string> = {
  success: 'var(--success)',
  warning: 'var(--warning)',
  error: 'var(--error)',
};

// 상태 → 옅은 배경 + 텍스트색 Tailwind 클래스 (배지 등)
// Tailwind 기본 색 스케일(emerald/amber/red)의 -50 단계를 soft bg 로 채택.
export const statusBadgeClass: Record<ScoreStatus, string> = {
  success: 'bg-emerald-50 text-success',
  warning: 'bg-amber-50 text-warning',
  error: 'bg-red-50 text-error',
};
