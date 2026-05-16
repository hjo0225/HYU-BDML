'use client';

import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';
import { scoreStatus, statusColorVar } from './score';

interface GaugeProps {
  /** 0~1 정규화 점수 */
  value: number;
  /** 게이지 아래 라벨 (예: "V1 응답 동기화율") */
  label?: string;
  /** 컨테이너 px (가로 기준, 세로는 자동 절반+여백) */
  size?: number;
  /** 중앙 표시 단위. 'percent' 면 ×100, 'raw' 면 그대로 */
  display?: 'percent' | 'raw';
}

export function Gauge({ value, label, size = 220, display = 'percent' }: GaugeProps) {
  const clamped = Math.max(0, Math.min(1, value));
  const status = scoreStatus(clamped);
  const data = [{ value: clamped }, { value: 1 - clamped }];
  const center = display === 'percent'
    ? Math.round(clamped * 100).toString()
    : clamped.toFixed(2);

  return (
    <div
      className="relative"
      style={{ width: size, height: Math.round(size * 0.62) }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="95%"
            startAngle={180}
            endAngle={0}
            innerRadius="68%"
            outerRadius="100%"
            dataKey="value"
            stroke="none"
            isAnimationActive
          >
            <Cell fill={statusColorVar[status]} />
            <Cell fill="var(--border)" />
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <div className="absolute inset-0 flex flex-col items-center justify-end pb-1 pointer-events-none">
        <span
          className="text-score font-bold leading-none"
          style={{ color: statusColorVar[status] }}
        >
          {center}
        </span>
        {label && (
          <span className="text-xs text-text-muted mt-2 text-center px-2">
            {label}
          </span>
        )}
      </div>
    </div>
  );
}
