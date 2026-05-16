import { cn } from '@/components/ui/cn';
import { scoreStatus, statusBadgeClass, type ScoreStatus } from './score';

interface ScoreBadgeProps {
  /** 0~1 정규화 점수 */
  score: number;
  /** 점수 뒤에 붙는 작은 라벨 (예: 'V1', 'sync') */
  label?: string;
  /** 소수점 자릿수 (기본 2) */
  decimals?: number;
  className?: string;
}

const DOT_CLASS: Record<ScoreStatus, string> = {
  success: 'bg-success',
  warning: 'bg-warning',
  error: 'bg-error',
};

export function ScoreBadge({
  score,
  label,
  decimals = 2,
  className,
}: ScoreBadgeProps) {
  const status = scoreStatus(score);
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium',
        statusBadgeClass[status],
        className,
      )}
    >
      <span className={cn('w-1.5 h-1.5 rounded-full', DOT_CLASS[status])} />
      <span>{score.toFixed(decimals)}</span>
      {label && (
        <span className="text-text-muted ml-0.5 font-normal">{label}</span>
      )}
    </span>
  );
}
