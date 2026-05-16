'use client';

import {
  RadarChart as RechartsRadar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';

export interface RadarPoint {
  axis: string;   // "sync" | "stability" | "distinct" | "humanity" | "reasoning_delta" 등
  value: number;  // 0~1 정규화
}

interface RadarChartProps {
  data: RadarPoint[];
  /** 컨테이너 높이 px */
  height?: number;
}

export function RadarChart({ data, height = 280 }: RadarChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <RechartsRadar data={data} outerRadius="80%">
        <PolarGrid stroke="var(--border)" />
        <PolarAngleAxis
          dataKey="axis"
          tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
        />
        <PolarRadiusAxis
          domain={[0, 1]}
          tick={false}
          axisLine={false}
        />
        <Radar
          dataKey="value"
          stroke="var(--indigo)"
          fill="var(--indigo)"
          fillOpacity={0.15}
          isAnimationActive
        />
        <Tooltip
          contentStyle={{
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 8,
            fontSize: 12,
          }}
          formatter={(value) =>
            typeof value === 'number' ? value.toFixed(2) : String(value ?? '')
          }
        />
      </RechartsRadar>
    </ResponsiveContainer>
  );
}
